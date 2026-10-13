#!/usr/bin/env bash
# Import your fine-tuned GGUF into Ollama and switch the app to it.  Usage: scripts/use-finetuned.sh <folder with Modelfile + .gguf>
set -euo pipefail
[ $# -ge 1 ] || { echo "Usage: $0 <folder containing Modelfile and the .gguf>"; exit 1; }
(cd "$1" && ollama create ostutor-qwen3 -f Modelfile)
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
sed -i.bak 's/^LLM_MODEL=.*/LLM_MODEL=ostutor-qwen3/' .env && rm -f .env.bak
docker compose up -d api worker
echo "Done. The app now uses ostutor-qwen3 (check Knowledge > System)."
