# Getting Started

## Requirements

- **Python 3.12+**
- **[Ollama](https://ollama.com/)** running locally with the default models (`nomic-embed-text`, `llama3.2`)

## Installation

=== "PyPI (recommended)"

    ```bash
    python3.12 -m pip install recall-py
    recall-py onboard
    ```

=== "pipx"

    ```bash
    pipx install recall-py
    recall-py onboard
    ```

=== "uv"

    ```bash
    uv pip install recall-py
    recall-py onboard
    ```

=== "From source"

    ```bash
    git clone https://github.com/rehanpunjwani/recall-py
    cd recall-py
    python3.12 -m venv .venv
    source .venv/bin/activate
    python3.12 -m pip install -e .
    recall-py onboard
    ```

## First-time setup

Run `recall-py onboard` to:

1. Create a personal config file at `~/.config/recall-py/config.yaml`
2. Migrate the SQLite database to the latest schema
3. Check that Ollama is reachable
4. Optionally pull the default models
5. Print an MCP snippet for your IDE

For non-interactive setups (CI):

```bash
recall-py onboard -y --skip-pull
```

## Verify the installation

```bash
recall-py doctor
```

This checks:

- Database path and schema version
- Ollama reachability at the configured URL

## Next steps

- Run **`recall-py serve`** to start the HTTP API
- Configure **MCP tools** in your IDE (see [MCP Tools](mcp-tools.md))
- Index your workspace: **`recall-py index`**
- Check token savings: **`recall-py metrics`**
