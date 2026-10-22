#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || cp .env.example .env
MODEL="$(grep -E '^LLM_MODEL=' .env | cut -d= -f2- || true)"
MODEL="${MODEL:-qwen3:14b}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Install and start Docker before running OSTutorLLM." >&2
  exit 1
fi
if ! command -v ollama >/dev/null 2>&1; then
  echo "ERROR: Ollama is required for LLM_REQUIRED=1. Install it from https://ollama.com/download." >&2
  exit 1
fi
if ! ollama list >/dev/null 2>&1; then
  echo "Ollama is installed but not responding; starting ollama serve..."
  (ollama serve >/tmp/ostutor-ollama.log 2>&1 &) || true
  ready=0
  for _ in $(seq 1 30); do
    if ollama list >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
  done
  if [[ "$ready" != 1 ]]; then
    echo "ERROR: Ollama did not become ready on port 11434. See /tmp/ostutor-ollama.log." >&2
    exit 1
  fi
fi
if ! ollama show "$MODEL" >/dev/null 2>&1; then
  case "$MODEL" in
    ostutor*)
      echo "ERROR: Fine-tuned model $MODEL is not installed locally. Build/import it using training/README.md, or set LLM_MODEL to a stock Qwen model." >&2
      exit 1
      ;;
    *)
      echo "Pulling configured model $MODEL..."
      ollama pull "$MODEL"
      ;;
  esac
fi
ollama show "$MODEL" >/dev/null 2>&1 || {
  echo "ERROR: Model $MODEL is unavailable. Check LLM_MODEL in .env." >&2
  exit 1
}
python3 scripts/live_llm_smoke.py
docker compose up --build -d
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:3000 >/dev/null; then
    echo "OSTutorLLM is live at http://localhost:3000"
    echo "API health: http://localhost:8000/health"
    docker compose ps
    docker compose logs -f --tail=50 api worker web
    exit 0
  fi
  sleep 2
done
echo "ERROR: Frontend did not become healthy within 120 seconds." >&2
docker compose ps
docker compose logs --tail=100 api web
exit 1
