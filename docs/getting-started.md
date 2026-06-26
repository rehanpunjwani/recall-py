# Getting Started

## Requirements

- **Python 3.12+**
- **[Ollama](https://ollama.com/)** running locally with the default models (`nomic-embed-text`, `llama3.2`)

## Installation

=== "PyPI (recommended)"

    ```bash
    python3.12 -m pip install tokenguard
    tokenguard onboard
    ```

=== "pipx"

    ```bash
    pipx install tokenguard
    tokenguard onboard
    ```

=== "uv"

    ```bash
    uv pip install tokenguard
    tokenguard onboard
    ```

=== "From source"

    ```bash
    git clone https://github.com/rehanpunjwani/TokenGuard
    cd TokenGuard
    python3.12 -m venv .venv
    source .venv/bin/activate
    python3.12 -m pip install -e .
    tokenguard onboard
    ```

## First-time setup

Run `tokenguard onboard` to:

1. Create a personal config file at `~/.config/tokenguard/config.yaml`
2. Migrate the SQLite database to the latest schema
3. Check that Ollama is reachable
4. Optionally pull the default models
5. Print an MCP snippet for your IDE

For non-interactive setups (CI):

```bash
tokenguard onboard -y --skip-pull
```

## Verify the installation

```bash
tokenguard doctor
```

This checks:

- Database path and schema version
- Ollama reachability at the configured URL

## Next steps

- Run **`tokenguard serve`** to start the HTTP API
- Configure **MCP tools** in your IDE (see [MCP Tools](mcp-tools.md))
- Index your workspace: **`tokenguard index`**
- Check token savings: **`tokenguard metrics`**
