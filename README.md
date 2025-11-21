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

Agent capabilities and tools
----------------------------

The QA Assistant Agent can answer QA-focused questions (test cases, test plans, retest steps, risk analysis, environments, data) directly in chat. It also has three built-in tools it can call automatically to fetch structured context from the mock data in `data/`. You do not need to trigger tools manually—when your prompt implies a need for them, the Agent will call them. Data retrievable via these tools is available in @bugs.json (`data/bugs.json`), @features.json (`data/features.json`), and @project_description.json (`data/project_description.json`).

- `get_feature_from_jira(feature_id)`
  - When used: When you ask about test cases for a feature, need context to generate test cases, or want details for a specific feature.
  - Triggered by: Mentioning a feature key like `QA-104`, or asking for feature details or test cases (e.g., “Create test cases for QA-104”).
  - Returns: `{ "title": str, "description": str }` from `data/features.json`.
  - Example prompts: “What does QA-101 cover?”, “Draft acceptance tests for QA-104.”

- `get_bug_from_jira(bug_id)`
  - When used: When you ask how to retest a bug, verify a fix, or need bug details to outline retest steps.
  - Triggered by: Mentioning a bug key like `BUG-201`, or asking about retest/verification for a bug (e.g., “How do I verify the fix for BUG-203?”).
  - Returns: `{ "title": str, "description": str }` from `data/bugs.json`.
  - Example prompts: “Provide retest steps for BUG-201,” “What should we check after BUG-210 is fixed?”

- `get_project_context()`
  - When used: When broader system/domain/QA-process context is needed (e.g., designing a test strategy, listing risk areas, or understanding key flows/environments).
  - Triggered by: Requests that require high-level context, or when you explicitly ask for project context (e.g., “Outline a test strategy for checkout,” “What are key risks in payments?”).
  - Returns: A dictionary loaded from `data/project_description.json` (architecture, flows, environments, risks, data).
  - Example prompts: “Using QA-104, outline a test strategy for multi-currency pricing consistency,” “Combine project context with QA-106 to propose returns eligibility test scenarios.”

Observability (optional)
------------------------

If Langfuse keys are configured in `.env`, tracing initializes automatically (see `observability.py`).  
On startup you should see: “Langfuse client authenticated and ready”.
