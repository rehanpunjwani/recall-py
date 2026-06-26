#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
docker compose up --build -d
if [[ "${SKIP_MODEL_PULL:-}" != "1" ]]; then
  echo "Pulling Ollama models (set SKIP_MODEL_PULL=1 to skip)..."
  docker compose exec -T ollama ollama pull nomic-embed-text
  docker compose exec -T ollama ollama pull llama3.2
fi
echo ""
echo "TokenGuard API: http://127.0.0.1:8766/health"
echo "Ollama:         http://127.0.0.1:11434"
