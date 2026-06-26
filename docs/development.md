# Development

## Setup

```bash
git clone https://github.com/rehanpunjwani/TokenGuard
cd TokenGuard
python3.12 -m venv .venv
source .venv/bin/activate
python3.12 -m pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

All tests use `tmp_path`-scoped databases and mock external services where needed. No real Ollama server is required.

## Code style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

Type checking with [pyright](https://github.com/microsoft/pyright):

```bash
pyright src/ tests/
```

## Project structure

```
src/tokenguard/
├── __init__.py          # Package version
├── __main__.py          # python -m tokenguard
├── app.py               # FastAPI application factory
├── cli.py               # Typer CLI entrypoints
├── config/
│   └── default.yaml     # Shipped default configuration
├── context.py           # RAG retrieval and context formatting
├── engine.py            # Orchestration (ingest, answer, escalate)
├── hooks.py             # Cursor hook handlers
├── indexing.py          # Workspace document indexing
├── mcp_server.py        # MCP tool server
├── metrics.py           # Token savings estimation
├── ollama_client.py     # Ollama provider facade
├── onboard.py           # First-time setup wizard
├── providers/
│   ├── base.py          # LLMProvider abstract base
│   ├── ollama.py        # Ollama HTTP provider
│   └── openai_compat.py # OpenAI-compatible provider
├── proxy/
│   ├── cache.py         # Request hashing, compression
│   └── streaming.py     # Streaming proxy forwarder
├── retrieve.py          # ANN index and similarity search
├── router.py            # Escalation policy and confidence
├── settings.py          # Pydantic config models
├── store/
│   ├── db.py            # SQLite connection and migrations
│   └── repository.py    # Data access layer
├── text/
│   ├── chunking.py      # Text chunking with overlap
│   └── redact.py        # Secret redaction
└── threads.py           # Workspace thread ID generation
```

## Making a release

1. Update version in `src/tokenguard/__init__.py`
2. Commit and tag: `git tag v0.x.x && git push --tags`
3. GitHub Actions will build and publish to PyPI automatically
4. Update the docs site: `mkdocs gh-deploy`
