$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot/..
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$model = ((Get-Content .env | Where-Object { $_ -like 'LLM_MODEL=*' }) -replace '^LLM_MODEL=', '')
if (-not $model) { $model = 'qwen3:14b' }
if (Get-Command ollama -ErrorAction SilentlyContinue) { if ($model -notlike 'ostutor*') { ollama pull $model } }
else { Write-Warning 'Ollama not found: the app will run in extractive mode until you install it (https://ollama.com/download).' }
docker compose up --build
