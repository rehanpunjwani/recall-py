# Architecture

TokenGuard is a local-first RAG system designed to reduce cloud LLM spend. Here is how it works.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  User / IDE / App                                                │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ MCP Tools │  │ CLI       │  │ HTTP API │  │ Library import │ │
│  └─────┬────┘  └─────┬─────┘  └────┬─────┘  └───────┬────────┘ │
└────────┼──────────────┼─────────────┼──────────────────┼─────────┘
         │              │             │                  │
         ▼              ▼             ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│  Engine (orchestration layer)                                    │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────────────┐│
│  │ ingest_turn│  │ handle_query │  │ escalate_pack             ││
│  │ (store +   │  │ (ingest,     │  │ (build context pack for   ││
│  │  embed +   │  │  retrieve,   │  │  cloud model)             ││
│  │  chunk)    │  │  answer)     │  │                           ││
│  └─────┬──────┘  └──────┬───────┘  └────────────┬──────────────┘│
└────────┼─────────────────┼──────────────────────┼───────────────┘
         │                 │                      │
         ▼                 ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│  Services                                                        │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐  │
│  │ OllamaClient │  │ Context (RAG) │  │ Metrics & Routing    │  │
│  │ ┌──────────┐ │  │ ┌───────────┐ │  │ ┌──────────────────┐ │  │
│  │ │ embed    │ │  │ │ retrieve  │ │  │ │ token counting   │ │  │
│  │ │ chat     │ │  │ │ format    │ │  │ │ confidence score │ │  │
│  │ │ health   │ │  │ │ citations │ │  │ │ escalation       │ │  │
│  │ └──────────┘ │  │ └───────────┘ │  │ └──────────────────┘ │  │
│  └──────┬───────┘  └───────┬───────┘  └──────────────────────┘  │
└─────────┼──────────────────┼────────────────────────────────────┘
          │                  │
          ▼                  ▼
┌──────────────────────────────────────────────────────────────────┐
│  Data layer                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ SQLite (DB)  │  │ Repository   │  │ Text processing      │  │
│  │ ┌──────────┐ │  │ (CRUD for    │  │ ┌──────────────────┐ │  │
│  │ │ threads  │ │  │  threads,    │  │ │ chunk_text       │ │  │
│  │ │ messages │ │  │  messages,   │  │ │ redact_text      │ │  │
│  │ │ chunks   │ │  │  chunks,     │  │ └──────────────────┘ │  │
│  │ │ cache    │ │  │  cache...)   │  │                      │  │
│  │ │ usage    │ │  └──────────────┘  │                      │  │
│  │ └──────────┘ │                     │                      │  │
│  └──────────────┘                     └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │ External: Ollama server  │
                    │ (embeddings + chat)     │
                    └─────────────────────────┘
```

## Data flow: handling a user query

1. **Ingest** — The user message is stored in the `messages` table, then chunked (1200 chars with 150 overlap) and embedded via Ollama's embedding model. Each chunk + embedding is stored in the `chunks` table.

2. **Retrieve** — The query is embedded using the same model, and cosine similarity is computed against all stored chunk embeddings. The top-k most relevant chunks are returned along with a similarity score.

3. **Answer** — A local model (Ollama) generates a draft answer using the retrieved context as a prompt. The system prompt instructs it to say "escalate" if context is insufficient.

4. **Route** — The draft is scored for confidence. If the score is below the threshold, or if the query matches an escalation keyword, the system returns an escalation signal instead of the draft.

5. **Store reply** — The assistant's final response (from cloud or local) can be ingested back into the database for future retrieval.

## Database schema

### `schema_meta`
| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | Setting key |
| `value` | TEXT | Setting value |

### `threads`
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `title` | TEXT | Thread title |
| `workspace_fingerprint` | TEXT | Stable workspace identifier |
| `provider` | TEXT | Source (e.g. `cursor`, `cli`) |
| `created_at` | TEXT (ISO-8601) | Creation timestamp |
| `updated_at` | TEXT (ISO-8601) | Last update timestamp |

### `messages`
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `thread_id` | TEXT | FK → threads.id |
| `role` | TEXT | `user` or `assistant` |
| `content` | TEXT | Message body (redacted) |
| `provider` | TEXT | Source identifier |
| `model` | TEXT | Model used (for assistant messages) |
| `tokens_in` | INTEGER | Estimated tokens in |
| `created_at` | TEXT | Timestamp |

### `chunks`
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `message_id` | TEXT | FK → messages.id |
| `thread_id` | TEXT | FK → threads.id |
| `text` | TEXT | Chunk content |
| `embedding` | BLOB | float32 embedding vector |
| `embedding_dim` | INTEGER | Vector dimension |
| `created_at` | TEXT | Timestamp |

### `proxy_cache`
| Column | Type | Description |
|--------|------|-------------|
| `hash` | TEXT (SHA256) | Primary key |
| `response` | TEXT | Cached JSON response |
| `model` | TEXT | Model name |
| `created_at` | TEXT | Timestamp |

### `usage_events`
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto) |
| `thread_id` | TEXT | FK → threads.id |
| `event_type` | TEXT | Event category |
| `provider` | TEXT | Source identifier |
| `tokens_saved` | INTEGER | Estimated savings |
| `tokens_local_in` | INTEGER | Local input tokens |
| `tokens_local_out` | INTEGER | Local output tokens |
| `metadata` | TEXT | JSON metadata |
| `created_at` | TEXT | Timestamp |

## Embedding storage

Embeddings are stored as raw float32 byte blobs in the `chunks.embedding` column. At query time, all embeddings for a thread are loaded into memory and cosine similarity is computed directly. For threads with more than 200 chunks, a `usearch` approximate nearest-neighbor index is used instead of brute-force search.
