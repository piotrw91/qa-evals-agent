import os

from dotenv import load_dotenv
from contextlib import contextmanager
from typing import Iterator, Optional


_INSTRUMENTED = False


def _configure_langfuse_env() -> None:
    """Prepare env for Langfuse Python SDK initialization.

    - Support both LANGFUSE_BASE_URL and legacy LANGFUSE_HOST
    - Provide a sane default for OTEL resource attributes
    """

    # Support either variable name for base URL; prefer LANGFUSE_BASE_URL
    if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
        os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST", "").rstrip("/")

    # Helpful default for grouping in Langfuse (can be overridden via env)
    if not os.getenv("OTEL_RESOURCE_ATTRIBUTES"):
        os.environ["OTEL_RESOURCE_ATTRIBUTES"] = "service.name=qa-agent"


def _init_langfuse_client() -> None:
    """Initialize Langfuse client which attaches its OTel exporter/processor.

    Also prints an auth check message for quick diagnostics.
    """
    try:
        from langfuse import get_client
    except Exception as exc:
        print(f"[observability] langfuse SDK not available: {exc}")
        return

    try:
        client = get_client()
        try:
            if client.auth_check():
                print("[observability] Langfuse client authenticated and ready")
            else:
                print("[observability] Langfuse authentication failed — check LANGFUSE_PUBLIC_KEY/SECRET_KEY and LANGFUSE_BASE_URL")
        except Exception:
            # auth_check may not be available on older SDKs
            pass
    except Exception as exc:
        print(f"[observability] failed to initialize Langfuse client: {exc}")


def init_observability() -> None:
    """Initialize environment and instrument OpenAI Agents for tracing."""
    global _INSTRUMENTED
    if _INSTRUMENTED:
        return

    # Make sure .env is loaded before reading keys
    load_dotenv()
    _configure_langfuse_env()

    # Instrument the OpenAI Agents SDK to emit OpenTelemetry spans
    from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor().instrument()
    _init_langfuse_client()
    _INSTRUMENTED = True


# Initialize on import for convenience
try:
    init_observability()
except Exception as exc:
    # Do not crash the app if instrumentation is not available/misconfigured
    print(f"[observability] instrumentation not enabled: {exc}")



@contextmanager
def langfuse_session_context(session_id: str, user_id: Optional[str] = None) -> Iterator[object]:
    """Context manager to attach a Langfuse session to the current trace.

    Usage:
        with langfuse_session_context("session-123", user_id="user-1"):
            await Runner.run(...)
    """
    try:
        from langfuse import get_client
        client = get_client()
    except Exception:
        # If SDK not present, noop
        yield None
        return

    with client.start_as_current_span(name=f"session:{session_id}") as span:
        try:
            span.update_trace(session_id=session_id, user_id=user_id)
        except Exception:
            pass
        yield span

