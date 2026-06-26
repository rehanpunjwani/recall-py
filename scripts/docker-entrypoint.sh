#!/usr/bin/env sh
set -e
BASE="${TOKENGUARD_OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
BASE="${BASE%/}"
echo "TokenGuard: waiting for Ollama at ${BASE} ..."
i=0
while [ "$i" -lt 120 ]; do
  if python - <<PY
import sys, urllib.request
base = "${BASE}"
try:
    urllib.request.urlopen(f"{base}/api/tags", timeout=3)
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
  then
    echo "Ollama is up."
    exec tokenguard serve "$@"
  fi
  i=$((i + 1))
  sleep 1
done
echo "Timeout waiting for Ollama at ${BASE}" >&2
exit 1
