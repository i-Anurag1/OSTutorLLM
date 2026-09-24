$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot/..
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw 'Ollama is not installed or not in PATH. Install it from https://ollama.com/download.' }
ollama pull qwen3:14b
docker compose up --build
