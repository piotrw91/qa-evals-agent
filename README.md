QA Agent — Quickstart
=====================

A minimal FastAPI server that serves a static chat UI for the QA Assistant Agent.

Prerequisites
-------------

- Python 3.10+ (check your version):

```bash
python3 --version
```

- If you need Python: see `https://www.python.org/downloads/`
- Install uv (package/dependency manager):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```
  - macOS alternative: `brew install uv`

Environment
-----------

1. Copy `.env.example` to `.env`

```bash
cp .env.example .env
```

2. Edit `.env` and add the following (replace placeholders with your real values):

```bash
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

Install dependencies
--------------------

```bash
uv sync
```

Notes:
- `uv` will create and manage a virtual environment (typically `.venv`) automatically.


Run
---

```bash
uv run uvicorn server:app --reload
```

Open the UI at `http://127.0.0.1:8000`.

Mock data
---------

The `data/` folder contains JSON fixtures used by the QA Agent:
- `project_description.json`: high-level context about the Aurora Market e‑commerce platform (domains, flows, environments, risks).
- `bugs.json`: a small catalog of realistic historical bug reports for Aurora Market.
- `features.json`: a small catalog of feature / epic descriptions for Aurora Market.

Observability (optional)
------------------------

If Langfuse keys are configured in `.env`, tracing initializes automatically (see `observability.py`).  
On startup you should see: “Langfuse client authenticated and ready”.
