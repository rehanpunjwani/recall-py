# Configuration

TokenGuard loads configuration from multiple sources, each overriding the previous:

1. **Shipped defaults** — `src/tokenguard/config/default.yaml`
2. **User config** — `~/.config/tokenguard/config.yaml` (when `TOKENGUARD_CONFIG` is unset)
3. **`TOKENGUARD_CONFIG` env var** — points to an explicit YAML file
4. **`--config` CLI flag** — explicit path (highest file priority)
5. **Environment variable overlays** — for Docker/k8s deployments

## Default configuration

```yaml
ollama:
  base_url: "http://127.0.0.1:11434"
  embed_model: "nomic-embed-text"
  chat_model: "llama3.2"
  timeout_seconds: 30.0

storage:
  db_path: "~/.local/share/tokenguard/tokenguard.db"

limits:
  chunk_size_chars: 1200
  chunk_overlap_chars: 150
  max_local_answer_tokens: 256

policy:
  always_escalate_keywords:
    - "deploy"
    - "security audit"
    - "vulnerability"
    - "production"
  auto_escalate: true
  confidence_threshold: 0.4
  redact_patterns: []

proxy:
  enabled: false
  upstream_base_url: "https://api.openai.com"
  upstream_api_key_env: "OPENAI_API_KEY"
  try_local_first: false

api:
  listen_host: "127.0.0.1"
  listen_port: 8766

provider:
  type: "ollama"
```

## Environment variable overlays

For containerized deployments, each config field has a matching env var:

| Env var | Config field | Example |
|---------|-------------|---------|
| `TOKENGUARD_OLLAMA_BASE_URL` | `ollama.base_url` | `http://ollama:11434` |
| `TOKENGUARD_DB_PATH` | `storage.db_path` | `/data/tokenguard.db` |
| `TOKENGUARD_API_LISTEN_HOST` | `api.listen_host` | `0.0.0.0` |
| `TOKENGUARD_API_LISTEN_PORT` | `api.listen_port` | `8766` |

## All config sections

### `ollama`

| Key | Default | Description |
|-----|---------|-------------|
| `base_url` | `http://127.0.0.1:11434` | Ollama server URL |
| `embed_model` | `nomic-embed-text` | Model for text embeddings |
| `chat_model` | `llama3.2` | Model for local draft generation |
| `timeout_seconds` | `30.0` | HTTP client timeout |

### `storage`

| Key | Default | Description |
|-----|---------|-------------|
| `db_path` | `~/.local/share/tokenguard/tokenguard.db` | SQLite database path |

### `limits`

| Key | Default | Description |
|-----|---------|-------------|
| `chunk_size_chars` | `1200` | Max characters per text chunk |
| `chunk_overlap_chars` | `150` | Overlap between consecutive chunks |
| `max_local_answer_tokens` | `256` | Max tokens for local Ollama draft |

### `policy`

| Key | Default | Description |
|-----|---------|-------------|
| `always_escalate_keywords` | `[deploy, security audit, vulnerability, production]` | Keywords that force escalation |
| `auto_escalate` | `true` | Auto-escalate when draft confidence is low |
| `confidence_threshold` | `0.4` | Minimum confidence for local draft |
| `redact_patterns` | `[]` | Regex patterns to redact from stored content |

### `proxy`

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `false` | Enable OpenAI-compatible proxy |
| `upstream_base_url` | `https://api.openai.com` | Upstream API base URL |
| `upstream_api_key_env` | `OPENAI_API_KEY` | Env var holding the API key |
| `try_local_first` | `false` | Try local RAG draft before proxying |

### `api`

| Key | Default | Description |
|-----|---------|-------------|
| `listen_host` | `127.0.0.1` | HTTP API bind address |
| `listen_port` | `8766` | HTTP API port |

### `provider`

| Key | Default | Description |
|-----|---------|-------------|
| `type` | `ollama` | Provider type (`ollama` or `openai_compat`) |
