# Library API

TokenGuard is first and foremost a Python library. It exposes a clean, async API that you can import directly.

## Core functions

### `handle_query`

The primary entry point for processing a user query. It ingests the message, retrieves relevant context, drafts a local answer, and returns structured results.

```python
import sqlite3
from tokenguard.engine import handle_query
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings

settings = AppSettings.load()
conn = sqlite3.connect(settings.resolved_db_path())
ollama = OllamaClient(settings.ollama)

result = await handle_query(
    conn, settings, ollama,
    query="What is the database schema?",
    thread_id=None,
    workspace_fingerprint="",
    provider="my-app",
    ingest_assistant=None,
)
```

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | `str` | Stable thread ID for the workspace |
| `workspace_fingerprint` | `str` | Workspace identifier |
| `context_pack` | `dict` | Citations and formatted context |
| `policy` | `dict` | Usage guidance for the agent |
| `ingest` | `dict` | Whether user message was ingested |
| `answer` | `dict` | Local draft or escalation decision |
| `assistant_ingest` | `dict\|None` | Assistant message ingest result |
| `metrics` | `dict` | Token savings and usage stats |

### `ingest_turn`

Store a conversation turn (user or assistant) in the database and index it for retrieval.

```python
from tokenguard.engine import ingest_turn

out = await ingest_turn(
    conn, settings, ollama,
    thread_id=tid,
    role="assistant",
    content="Your reply here...",
    title="my-thread",
    workspace_fingerprint=fp,
    provider="my-app",
    model="gpt-4",
)
```

### `answer`

Generate a local draft answer using Ollama, with optional escalation.

```python
from tokenguard.engine import answer

result = await answer(
    conn, settings, ollama,
    query="What does the config do?",
    thread_id=tid,
    workspace_fingerprint=fp,
)
```

### `answer_stream`

Stream a local draft answer token by token.

```python
from tokenguard.engine import answer_stream

async for token in answer_stream(
    conn, settings, ollama,
    query="Explain the architecture",
    thread_id=tid,
):
    print(token, end="", flush=True)
```

### `escalate_pack`

Build a compact JSON pack (RAG context + recent turns) for cloud model reasoning.

```python
from tokenguard.engine import escalate_pack

pack = await escalate_pack(
    conn, settings, ollama,
    query="Complex multi-step task",
    thread_id=tid,
    recent_message_limit=12,
)
pack_json = pack["pack_json"]
```

## Context retrieval

### `retrieve_context`

Retrieve semantically relevant chunks for a query.

```python
from tokenguard.context import retrieve_context

rag = await retrieve_context(
    conn, settings, ollama,
    query="What is the schema?",
    thread_id=tid,
)
# rag["citations"] -> list of (score, text) tuples
# rag["context"] -> concatenated text
# rag["formatted"] -> Markdown-formatted context
```

### `build_agent_context_message`

Format a context message for agent prompts.

```python
from tokenguard.context import build_agent_context_message

msg = build_agent_context_message(
    thread_id=tid,
    workspace_fingerprint=fp,
    user_query=query,
    citations=[(0.95, "relevant text")],
    top_score=0.95,
)
```

## Metrics

```python
from tokenguard.metrics import summary

data = summary(conn, thread_id=tid)
print(f"Tokens saved: {data['totals']['tokens_saved']}")
```

## Settings

```python
from tokenguard.settings import AppSettings

config = AppSettings.load()                        # default chain
config = AppSettings.load(Path("/path/to/cfg.yaml"))  # explicit
print(config.ollama.base_url)
print(config.storage.db_path)
print(config.proxy.enabled)
```

See [Configuration](configuration.md) for all available options.
