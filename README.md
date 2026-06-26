<p align="center">
  <img src="docs/assets/logo.svg" alt="TokenGuard" width="480" />
</p>

<p align="center">
  <a href="https://pypi.org/project/tokenguard/"><img src="https://img.shields.io/pypi/v/tokenguard?style=flat&label=PyPI" alt="PyPI" /></a>
  <a href="https://pypi.org/project/tokenguard/"><img src="https://img.shields.io/pypi/pyversions/tokenguard?style=flat&label=Python" alt="Python versions" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat" alt="License" /></a>
  <a href="https://github.com/rehanpunjwani/TokenGuard/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/rehanpunjwani/TokenGuard/ci.yml?style=flat&label=CI" alt="CI" /></a>
  <a href="https://rehanpunjwani.github.io/TokenGuard"><img src="https://img.shields.io/badge/docs-mkdocs-4F46E5?style=flat" alt="Docs" /></a>
</p>

---

**TokenGuard** is a Python library and CLI that helps you cut cloud LLM costs by caching conversations, retrieving relevant context via RAG, and routing queries to local models when appropriate. It integrates natively with Cursor, Claude Code, and any OpenAI-compatible client.

## Key features

- **RAG memory** — every conversation is chunked, embedded, and stored in SQLite for semantic retrieval
- **Local draft answering** — uses a cheap local model (Ollama) to answer common questions
- **Intelligent routing** — auto-escalates to cloud models when local confidence is low
- **OpenAI-compatible proxy** — drop-in caching + compression for existing clients
- **IDE-native MCP tools** — `handle_query`, `ingest_turn`, `escalate_pack` for Cursor / Claude Code
- **Token savings tracking** — see exactly how many cloud tokens you avoided

## Quick start

```bash
python3.12 -m pip install tokenguard
tokenguard onboard
tokenguard doctor
```

## Library usage

```python
import sqlite3
from tokenguard.engine import handle_query, ingest_turn
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings

settings = AppSettings.load()
conn = sqlite3.connect(settings.resolved_db_path())
ollama = OllamaClient(settings.ollama)

result = await handle_query(
    conn, settings, ollama,
    query="How does the routing policy work?",
    thread_id=None,
)

# result.context_pack.citations has the relevant context

await ingest_turn(
    conn, settings, ollama,
    thread_id=result["thread_id"],
    role="assistant",
    content="The routing policy...",
    title="my-session",
    workspace_fingerprint=result["workspace_fingerprint"],
    provider="my-app",
)
```

## CLI

| Command | Purpose |
|---------|---------|
| `tokenguard onboard` | First-time setup: config, DB, Ollama, MCP snippet |
| `tokenguard serve` | HTTP API (health + optional proxy) |
| `tokenguard mcp-stdio` | MCP server for IDE integration |
| `tokenguard doctor` | Check DB, migrations, Ollama |
| `tokenguard metrics` | Token savings overview |
| `tokenguard index` | Index workspace docs into RAG memory |

## Documentation

Full documentation is available at **[rehanpunjwani.github.io/TokenGuard](https://rehanpunjwani.github.io/TokenGuard/)**.

## Installation options

See the [Getting Started guide](https://rehanpunjwani.github.io/TokenGuard/getting-started/) for pipx, uv, and source installs.

## Requirements

- Python 3.12+
- [Ollama](https://ollama.com/) with `nomic-embed-text` and `llama3.2` (configurable)

## Architecture

TokenGuard stores every user and assistant message in SQLite, chunks them, and embeds each chunk via Ollama. On each query, it retrieves the most semantically relevant chunks and optionally drafts a local answer. When the local draft is too uncertain, it signals escalation — you paste the context pack into your cloud model instead. All token operations are tracked for savings reporting.

[Read the architecture docs](https://rehanpunjwani.github.io/TokenGuard/architecture/)

## Docker

```bash
bash scripts/docker-up.sh
```

Starts TokenGuard + Ollama with a single command. See [docker-compose.yml](docker-compose.yml).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and the [Development guide](https://rehanpunjwani.github.io/TokenGuard/development/) for technical setup.

## License

MIT
