#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
MODEL=$(grep -E '^LLM_MODEL=' .env | cut -d= -f2- || true); MODEL=${MODEL:-qwen3:14b}
if command -v ollama >/dev/null 2>&1; then case "$MODEL" in ostutor*) echo "Using local fine-tuned model $MODEL";; *) ollama pull "$MODEL";; esac
else echo "Ollama not found: the app will run in extractive mode until you install it (https://ollama.com/download)."; fi
docker compose up --build
