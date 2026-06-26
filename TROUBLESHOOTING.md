# TokenGuard Troubleshooting Guide

## MCP Integration Issues

### "Invalid JSON: EOF" error when running `tokenguard mcp-stdio`

**Problem:** You ran `tokenguard mcp-stdio` directly in your terminal and see JSON parsing errors.

**Solution:** Don't run this command manually! The `mcp-stdio` command is designed to be spawned by your IDE (Cursor, Claude Code, etc.). It communicates via standard input/output with the IDE.

**Correct workflow:**
1. Install TokenGuard: `pip install -e .`
2. Run onboarding: `tokenguard onboard`
3. Configure MCP in your IDE settings (see README.md). If the IDE cannot resolve `tokenguard` on `PATH`, use an absolute path from `command -v tokenguard` or the `python -m tokenguard` pattern in the README.
4. Let the IDE spawn the MCP server automatically

### MCP server not responding or tools failing

**`MCP error -32000: Connection closed`** — the MCP child process exited immediately. Usually the IDE cannot find `tokenguard` on `PATH`. Fix: use [`.cursor/mcp.json`](.cursor/mcp.json) in this repo, run `pip install -e .`, reload Cursor, and remove conflicting manual MCP entries.

**Check 1: Is Ollama running?**
```bash
tokenguard doctor
```
This should report Ollama as reachable. If not:

**If using Docker:**
```bash
cd /path/to/your/tokenguard-clone
bash scripts/docker-up.sh
# Verify containers are up
docker ps
# Check Ollama health
curl http://127.0.0.1:11434/api/tags
```

**If using local Ollama:**
```bash
ollama serve  # Keep this running in a terminal
# In another terminal:
ollama pull nomic-embed-text
ollama pull llama3.2
```

**Check 2: Are the required models available?**
```bash
ollama list
```
You should see `nomic-embed-text` and `llama3.2`.

**Check 3: Can TokenGuard connect to Ollama?**
```bash
tokenguard doctor
```

**Check 4: View MCP server logs**

When your IDE starts the MCP server, it logs diagnostics to stderr. Look for:
- "TokenGuard: Loaded config (Ollama: ...)"
- "TokenGuard: Database ready at ..."
- "TokenGuard WARNING: Ollama not reachable..." (indicates a problem)

In Cursor, these logs may be visible in the developer console or MCP server output panel.

### Docker-specific issues

**Problem:** Docker containers not starting

```bash
cd /path/to/your/tokenguard-clone
docker compose down
docker compose up --build -d
docker compose logs -f
```

**Problem:** Ollama in Docker has no models

```bash
cd /path/to/your/tokenguard-clone
docker compose exec ollama ollama list
# If empty:
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2
```

**Problem:** Can't connect to Ollama from host

The Docker Compose exposes Ollama on `http://127.0.0.1:11434`. Verify:
```bash
curl http://127.0.0.1:11434/api/tags
```

If this works, TokenGuard's MCP server (running on your host) should be able to connect.

## Configuration Issues

### Custom config not loading

Set the environment variable:
```bash
export TOKENGUARD_CONFIG=/path/to/your/config.yaml
```

Or in your IDE's MCP settings:
```json
{
  "mcpServers": {
    "tokenguard": {
      "command": "tokenguard",
      "args": ["mcp-stdio"],
      "env": {
        "TOKENGUARD_CONFIG": "/path/to/your/config.yaml"
      }
    }
  }
}
```

### Database errors

The default database path is `~/.local/share/tokenguard/tokenguard.db`. Ensure:
1. The directory exists and is writable
2. Run `tokenguard migrate` to apply schema updates
3. If corrupted, delete the DB file and run `tokenguard migrate` again

## Performance Issues

### Embeddings/queries are slow

- Check your Ollama models are running locally (not being downloaded on each request)
- Verify `ollama list` shows your models
- Consider using a smaller chat model if `llama3.2` is too slow (edit config)

### Memory usage

- Ollama models consume RAM (typically 2-8GB depending on model size)
- SQLite database grows with conversation history
- Consider clearing old data: delete chunks/messages from the database

## Getting Help

1. Run diagnostics: `tokenguard doctor`
2. Check Ollama: `ollama list` and `curl http://127.0.0.1:11434/api/tags`
3. Verify Docker (if using): `docker ps` and `docker compose logs`
4. Review MCP server stderr logs in your IDE
5. Check your IDE's MCP settings match the README example

## Common Workflows

### Fresh start after Docker restart

```bash
cd /path/to/your/tokenguard-clone
bash scripts/docker-up.sh
# Wait for models to pull (first time only)
# Then use your IDE normally - MCP will connect automatically
```

### Using TokenGuard without Docker

```bash
# Terminal 1: Run Ollama
ollama serve

# Terminal 2: Pull models (first time)
ollama pull nomic-embed-text
ollama pull llama3.2

# Configure MCP in your IDE
# Let IDE spawn tokenguard mcp-stdio
```

### Testing MCP tools manually (for debugging)

You can test the underlying functions without MCP:
```bash
tokenguard doctor  # Health check
# Or use Python REPL:
python
>>> from tokenguard.settings import AppSettings
>>> from tokenguard.ollama_client import OllamaClient
>>> import asyncio
>>> s = AppSettings.load()
>>> o = OllamaClient(s.ollama)
>>> asyncio.run(o.health())
True
```
