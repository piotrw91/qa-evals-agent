QA Agent – Web UI + API
========================

A minimal FastAPI server that serves a static chat UI for the QA Assistant Agent. The UI shows left/right chat bubbles, a typing indicator, and live tool call notifications via SSE.

Requirements
------------

- Python 3.10+
- Dependencies in `pyproject.toml` (install with your preferred tool: `uv`, `pip`, `pipx`)

Run (Web UI)
------------

1. Create a `.env` if needed (API keys, etc.).
2. Start the server:

```bash
uvicorn server:app --reload
```

3. Open the UI at `http://localhost:8000/`.

Run (CLI chat – optional)
-------------------------

```bash
python main.py
```

API
---

- POST `/api/chat`
  - Request JSON:

    ```json
    { "sessionId": "string", "message": "string" }
    ```

  - Response JSON:

    ```json
    { "assistantMessage": "string" }
    ```

- GET `/api/events?sessionId=...` (SSE)
  - Emits events:
    - `typing_start`
    - `typing_end`
    - `tool_call` with `{ name, args }`
    - `final` with `{ assistantMessage }`
  - UI behavior: tool-call popup stays visible for ~5 seconds after the last `tool_end`.
  - Heartbeat: `ping {}` every ~15s

Project layout
--------------

- `server.py` – FastAPI app, SSE event bus, endpoints
- `web/` – static UI (no build)
  - `index.html` – chat layout
  - `styles.css` – styling
  - `app.js` – client logic (SSE + POST)
- `main.py` – CLI chat (unchanged)
- `data/` – mock JIRA data files

Hosting
-------

Deploy as a single service (Render/Fly/Railway/Docker). UI and API are same origin, so no CORS needed. Example container command:

```bash
uvicorn server:app --host 0.0.0.0 --port 8080
```


Observability & Tracing (Langfuse)
----------------------------------

This project is instrumented for Langfuse using OpenTelemetry via OpenInference's OpenAI Agents integration.

Setup (.env):

```
# Langfuse Cloud (EU by default). For US, set LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
# Optional: override region base url (defaults to https://cloud.langfuse.com)
# LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

# Optional: set your own service name/environment for filtering in Langfuse
# OTEL_RESOURCE_ATTRIBUTES=service.name=qa-agent,deployment.environment=dev
```

Notes:
- Tracing is initialized via `observability.py`: it instruments OpenAI Agents and initializes the Langfuse client (`get_client()`), which attaches its exporter/processor.
- You should see a startup log: "Langfuse client authenticated and ready" after correct configuration.
- Ensure your `OPENAI_API_KEY` is set for model calls.

Sessions in Langfuse
--------------------

- Each web request uses a Langfuse span with `session_id` set to the `sessionId` passed to `/api/chat`.
- The CLI uses a long-lived Langfuse span that wraps the entire conversation (`{agent.name.lower()}-session`).
- You can filter/group by `session_id` in Langfuse traces for full-session visibility.


