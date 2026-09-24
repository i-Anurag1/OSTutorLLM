@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo OSTutorLLM - Option 1: RAG + Qwen3 14B
 echo ============================================================
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama is not installed or not in PATH.
  echo Install Ollama from https://ollama.com/download and run this file again.
  pause
  exit /b 1
)
echo Pulling/verifying local Qwen3 14B model...
ollama pull qwen3:14b
if errorlevel 1 (
  echo Failed to pull qwen3:14b.
  pause
  exit /b 1
)
echo Starting PostgreSQL, Redis, API, background ingestion worker and web UI...
docker compose up --build
pause
