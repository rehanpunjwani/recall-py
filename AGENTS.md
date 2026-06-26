# TokenGuard — Agent instructions

## Entrypoints

| Entry | Invocation |
|---|---|
| CLI | `tokenguard <command>` or `python -m tokenguard <command>` |
| CLI module | `tokenguard.cli:main` (Typer app) |
| HTTP API | `tokenguard serve` — FastAPI at `127.0.0.1:8766` |
| MCP server | `tokenguard mcp-stdio` — stdio transport (spawned by IDE, never run manually) |
| Package root | `src/tokenguard/` (setuptools `packages.find` with `where = ["src"]`) |

## Key commands

```bash
pip install -e ".[dev]"   # dev install
pytest                    # all tests (asyncio_mode = auto)
tokenguard onboard        # first-time setup (config, DB migration, Ollama check)
tokenguard onboard -y --skip-pull  # non-interactive (CI)
tokenguard doctor         # check DB path, migrations, Ollama reachability
tokenguard metrics        # show token savings
tokenguard migrate        # apply SQLite migrations only
bash scripts/docker-up.sh          # docker compose up --build -d + model pulls
SKIP_MODEL_PULL=1 bash scripts/docker-up.sh  # skip model pulls
```

## Config loading order

1. `src/tokenguard/config/default.yaml` (shipped, bundled via `package-data`)
2. `~/.config/tokenguard/config.yaml` (XDG, only when `TOKENGUARD_CONFIG` unset)
3. `TOKENGUARD_CONFIG` env var → YAML file path
4. `--config` CLI flag
5. Env overlays: `TOKENGUARD_OLLAMA_BASE_URL`, `TOKENGUARD_DB_PATH`, `TOKENGUARD_API_LISTEN_HOST`, `TOKENGUARD_API_LISTEN_PORT`

Each layer deep-merges into the previous.

## Required Ollama models (default config)

- `nomic-embed-text` (embedding)
- `llama3.2` (local chat)

## Architecture

- **SQLite** in `~/.local/share/tokenguard/tokenguard.db` — schema v3 with tables: `threads`, `messages`, `chunks`, `proxy_cache`, `usage_events`. Migrations are imperative (see `store/db.py`), run automatically on first connection.
- **Embeddings** stored as float32 blobs; cosine similarity computed in-process in `retrieve.py`.
- **Chunking** at `1200` chars with `150` char overlap (configurable via `limits`).

## MCP tools (Cursor / Claude Code)

Cursor project config at `.cursor/mcp.json` auto-launches via `scripts/mcp-stdio.sh`.

Always follow the `tokenguard.mdc` rule: call `tokenguard_handle_query` before answering any user question. Then `tokenguard_ingest_turn(role=assistant, ...)` after replying. If local draft is weak, call `tokenguard_escalate_pack` and use your main model.

Cursor hooks (`.cursor/hooks.json`) auto-ingest when enabled in Cursor Settings → Hooks. Hook scripts must be `chmod +x`.

## Docker

- `docker-compose.yml`: ollama service + tokenguard service (HTTP API `tokenguard serve` only, no MCP inside container)
- Entrypoint (`scripts/docker-entrypoint.sh`) waits for Ollama health before starting.
- Env vars for container overrides: `TOKENGUARD_OLLAMA_BASE_URL`, `TOKENGUARD_DB_PATH`, `TOKENGUARD_API_LISTEN_HOST`.

## Testing

- `pytest` runs all tests — no extra flags needed.
- `pytest-asyncio` with `asyncio_mode = auto` (async tests run automatically).
- Test database is `tmp_path`-scoped (no external DB needed).
- Settings env tests use `monkeypatch` — no real Ollama required for unit tests.
