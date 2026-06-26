#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if command -v tokenguard >/dev/null 2>&1; then
  exec tokenguard hook before-prompt
fi
for py in python3.12 python3; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import tokenguard" 2>/dev/null; then
    exec "$py" -m tokenguard hook before-prompt
  fi
done
if [[ -x "$ROOT/.venv/bin/tokenguard" ]]; then
  exec "$ROOT/.venv/bin/tokenguard" hook before-prompt
fi
echo '{"agent_message":"TokenGuard hook failed: install tokenguard (pip install -e .)"}' >&1
exit 0
