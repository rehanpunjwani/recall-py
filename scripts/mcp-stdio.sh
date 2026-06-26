#!/usr/bin/env bash
# Portable MCP launcher for Cursor/Claude: repo .venv first, then PATH, then python -m.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$ROOT/.venv/bin/tokenguard" ]]; then
  exec "$ROOT/.venv/bin/tokenguard" mcp-stdio "$@"
fi

if command -v tokenguard >/dev/null 2>&1; then
  exec tokenguard mcp-stdio "$@"
fi

for py in python3.12 python3; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import tokenguard" 2>/dev/null; then
    exec "$py" -m tokenguard mcp-stdio "$@"
  fi
done

echo "TokenGuard MCP: could not start. From repo root run: python3 -m pip install -e ." >&2
exit 1
