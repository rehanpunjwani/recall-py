# MCP Tools

TokenGuard implements a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes its functionality as tools your IDE's agent can call directly.

## Available tools

### `tokenguard_handle_query` (primary)

Call on every user question. Ingests the query, retrieves context, generates a local draft, and returns a unified `thread_id`.

**Parameters:**

- `query` (str) — the user's question
- `thread_id` (str, optional) — existing thread ID
- `workspace_fingerprint` (str, optional) — workspace identifier

**Returns:** JSON with `thread_id`, `context_pack`, `policy`, and `metrics`.

### `tokenguard_ingest_turn`

Store a message after replying. Use with `role=assistant` to save your response.

**Parameters:**

- `thread_id` (str) — from `handle_query`
- `role` (str) — `"user"` or `"assistant"`
- `content` (str) — the message text
- `provider` (str, optional) — e.g. `"cursor"`, `"claude"`
- `model` (str, optional) — e.g. `"gpt-4"`

### `tokenguard_answer`

Retrieve context and local hint. Prefer `handle_query` for new questions.

**Parameters:** Same as `handle_query`.

### `tokenguard_answer_stream`

Stream a local draft token by token via MCP progress notifications.

### `tokenguard_escalate_pack`

Build a compact JSON pack (RAG context + recent turns) when the local draft is insufficient.

**Parameters:**

- `query` (str) — the complex question
- `thread_id` (str, optional)
- `workspace_fingerprint` (str, optional)

**Returns:** JSON with `pack_json` containing all context for the cloud model.

### `tokenguard_index`

Index README, rules, and docs into RAG memory. Run once per workspace.

**Parameters:**

- `workspace_fingerprint` (str, optional)
- `force` (bool, default: `false`)

### `tokenguard_metrics`

Return estimated token savings and usage breakdown.

**Parameters:**

- `thread_id` (str, optional) — scope to a thread, or global

## IDE setup

### Cursor

This repo includes `.cursor/mcp.json` that auto-launches `tokenguard mcp-stdio`. After install:

1. Run `tokenguard onboard` to verify everything works
2. Reload the Cursor window
3. The agent will automatically call `tokenguard_handle_query` on each question

### Claude Code / Claude Desktop

Add to your MCP settings:

```json
{
  "mcpServers": {
    "tokenguard": {
      "command": "tokenguard",
      "args": ["mcp-stdio"]
    }
  }
}
```

### Troubleshooting

- Run `tokenguard doctor` to check connectivity
- Ensure Ollama is running with the required models
- Check IDE logs for MCP stderr output
- Test with `bash scripts/mcp-stdio.sh` from the repo root
