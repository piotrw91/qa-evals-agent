import os
import asyncio
import json
import contextvars
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse
from pydantic import BaseModel

import observability  # initialize tracing on import
from agents import Agent, Runner, SQLiteSession, function_tool
from prompts import get_prompt


# Load environment variables from .env file
load_dotenv()
observability.init_observability()

# Read model configuration from environment
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5-mini")

BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR / "web"


app = FastAPI(title="QA Agent Server")


# -----------------------------
# SSE event bus (per-session)
# -----------------------------

SessionId = str
Event = Dict[str, Any]

# Multiple listeners per session (fan-out)
session_event_queues: dict[SessionId, list[asyncio.Queue[Event]]] = {}

current_session_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_session_id", default=None
)


def register_session_listener(session_id: SessionId) -> asyncio.Queue[Event]:
    queue: asyncio.Queue[Event] = asyncio.Queue()
    session_event_queues.setdefault(session_id, []).append(queue)
    return queue


def unregister_session_listener(session_id: SessionId, queue: asyncio.Queue[Event]) -> None:
    listeners = session_event_queues.get(session_id)
    if not listeners:
        return
    try:
        listeners.remove(queue)
    except ValueError:
        pass
    if not listeners:
        del session_event_queues[session_id]


def publish_event(session_id: Optional[SessionId], event_type: str, payload: Dict[str, Any]) -> None:
    if not session_id:
        return
    listeners = session_event_queues.get(session_id, [])
    event = {"type": event_type, "data": payload}
    # Broadcast to all listeners; ignore if queue is closed or full
    for q in list(listeners):
        try:
            q.put_nowait(event)
        except Exception:
            # Remove faulty queue
            try:
                listeners.remove(q)
            except Exception:
                pass


def _format_sse(event_type: str, data: Dict[str, Any]) -> str:
    return f"event: {event_type}\n" f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/events")
async def stream_events(request: Request, sessionId: str = Query(...)) -> StreamingResponse:
    """Server-Sent Events stream for a given session.

    Emits queued events and periodic heartbeats to keep the connection alive.
    """

    queue = register_session_listener(sessionId)
    try:
        print(f"[session] SSE connected for session: {sessionId}")
    except Exception:
        pass

    async def event_generator():
        try:
            while True:
                # If client disconnected, stop the generator
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _format_sse(item.get("type", "message"), item.get("data", {}))
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield _format_sse("ping", {})
        finally:
            # Best-effort: drain remaining items and unregister this listener
            try:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except Exception:
                        break
            finally:
                unregister_session_listener(sessionId, queue)
                try:
                    print(f"[session] SSE disconnected for session: {sessionId}")
                except Exception:
                    pass

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


DATA_DIR = BASE_DIR / "data"
FEATURES_PATH = DATA_DIR / "features.json"
BUGS_PATH = DATA_DIR / "bugs.json"


def _load_jira_records(path: Path) -> dict[str, dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        print(f"[warning] Missing data file: {path}")
        return {}

    records: dict[str, dict[str, str]] = {}
    for key, value in raw.items():
        title = value.get("title", "")
        description = value.get("description", "")
        records[key.upper()] = {"title": title, "description": description}
    return records


FEATURE_RECORDS = _load_jira_records(FEATURES_PATH)
BUG_RECORDS = _load_jira_records(BUGS_PATH)


def log_tool_call(tool_name: str, *, args: dict[str, object]) -> None:
    # Log to stdout (useful for server logs)
    arg_pairs = ", ".join(f"{key}={value}" for key, value in args.items())
    print(f"[tool-call] {tool_name}({arg_pairs})")
    # Publish to SSE stream for current session
    publish_event(current_session_id.get(), "tool_call", {"name": tool_name, "args": args})


@function_tool
def get_feature_from_jira(feature_id: str) -> dict[str, str]:
    """
    Retrieve a feature from JIRA by key.

    When to use:
    - Call this tool when the user asks about test cases for a feature,
      needs context to generate test cases, or wants details about a feature.

    Args:
        feature_id: The JIRA feature key (e.g., "FEAT-123").

    Returns:
        A dict with "title" and "description" for the feature.
    """
    feature_key = feature_id.strip().upper()
    log_tool_call("get_feature_from_jira", args={"feature_id": feature_key})
    try:
        record = FEATURE_RECORDS.get(feature_key)
        if record:
            return record
        return {
            "title": f"Unknown feature {feature_key}",
            "description": "No mock data is available for that feature ID.",
        }
    finally:
        publish_event(current_session_id.get(), "tool_end", {"name": "get_feature_from_jira"})


@function_tool
def get_bug_from_jira(bug_id: str) -> dict[str, str]:
    """
    Retrieve a bug from JIRA by key.

    When to use:
    - Call this tool when the user asks how to retest a bug, verify a fix,
      or needs bug details to outline retest steps.

    Args:
        bug_id: The JIRA bug key (e.g., "BUG-123").

    Returns:
        A dict with "title" and "description" for the bug.
    """
    bug_key = bug_id.strip().upper()
    log_tool_call("get_bug_from_jira", args={"bug_id": bug_key})
    try:
        record = BUG_RECORDS.get(bug_key)
        if record:
            return record
        return {
            "title": f"Unknown bug {bug_key}",
            "description": "No mock data is available for that bug ID.",
        }
    finally:
        publish_event(current_session_id.get(), "tool_end", {"name": "get_bug_from_jira"})


helper = Agent(
    name="QA Assistant Agent",
    instructions=get_prompt("QA Agent main instructions"),
    model=MODEL_NAME,
    tools=[get_feature_from_jira, get_bug_from_jira],
)


class ChatRequest(BaseModel):
    sessionId: str
    message: str


class ChatResponse(BaseModel):
    assistantMessage: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    # Notify UI that we're typing
    publish_event(req.sessionId, "typing_start", {})

    token = current_session_id.set(req.sessionId)
    session = SQLiteSession(session_id=req.sessionId)
    try:
        # Attach Langfuse session to this request's trace
        with observability.langfuse_session_context(req.sessionId) as lf_span:
            response = await Runner.run(helper, req.message, session=session)
            text = response.final_output or ""
            # Set trace-level input/output so Sessions UI shows I/O
            try:
                if lf_span is not None:
                    lf_span.update_trace(
                        input={"message": req.message},
                        output={"assistantMessage": text},
                    )
            except Exception:
                # Best-effort; do not fail request if tracing update fails
                pass
    finally:
        try:
            session.close()
        except Exception:
            pass
        current_session_id.reset(token)

    publish_event(req.sessionId, "typing_end", {})
    publish_event(req.sessionId, "final", {"assistantMessage": text})
    return ChatResponse(assistantMessage=text)


# Serve static frontend (no build step) — mounted last so /api/* routes win
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
