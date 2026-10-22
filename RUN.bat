@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title OSTutorLLM - Local Qwen/Ollama
echo ============================================================
echo  OSTutorLLM - Local Qwen + grounded RAG
echo ============================================================

if not exist .env copy /y .env.example .env >nul
set "MODEL=qwen3:14b"
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"LLM_MODEL=" .env') do set "MODEL=%%b"

where docker >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is required. Install/start Docker Desktop first.
  pause
  exit /b 1
)
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3 is required for the local LLM smoke test.
  pause
  exit /b 1
)
where ollama >nul 2>&1
if errorlevel 1 (
  echo ERROR: Ollama is required for the configured local Qwen model.
  echo Install it from https://ollama.com/download, then reopen this launcher.
  pause
  exit /b 1
)

echo Checking Ollama service...
ollama list >nul 2>&1
if errorlevel 1 (
  echo Ollama CLI is installed but the service is not responding. Starting it...
  start "Ollama service" /min ollama serve
  set "OLLAMA_READY="
  for /L %%i in (1,1,30) do (
    ollama list >nul 2>&1 && set "OLLAMA_READY=1" && goto :ollama_ready
    timeout /t 2 /nobreak >nul
  )
  echo ERROR: Ollama did not become ready at localhost:11434.
  pause
  exit /b 1
)
:ollama_ready

echo Checking configured model: !MODEL!
ollama show "!MODEL!" >nul 2>&1
if errorlevel 1 (
  echo !MODEL! | findstr /b /i "ostutor" >nul
  if not errorlevel 1 (
    echo ERROR: Fine-tuned model !MODEL! is not installed locally.
    echo Build/import it using training\README.md or set LLM_MODEL to a stock Qwen model.
    pause
    exit /b 1
  )
  echo Pulling model !MODEL! (first run might take a while)...
  ollama pull "!MODEL!"
  if errorlevel 1 (
    echo ERROR: Could not pull !MODEL!. Check your network and disk space.
    pause
    exit /b 1
  )
)
ollama show "!MODEL!" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Model !MODEL! is still not available in Ollama.
  echo Check LLM_MODEL in .env. Fine-tuned models must exist locally before startup.
  pause
  exit /b 1
)

echo Verifying a real response from the configured LLM...
python scripts\live_llm_smoke.py
if errorlevel 1 (
  echo ERROR: Ollama did not answer the smoke test. OSTutorLLM was not started.
  echo Check .env: LLM_BASE_URL should be http://host.docker.internal:11434/v1
  pause
  exit /b 1
)

echo Building and starting PostgreSQL, Redis, API, worker and frontend...
docker compose up --build -d
if errorlevel 1 (
  echo ERROR: docker compose failed. Review Docker Desktop and the logs.
  pause
  exit /b 1
)

echo Waiting for frontend health...
set "WEB_READY="
for /L %%i in (1,1,60) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:3000 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1 && set "WEB_READY=1" && goto :web_ready
  timeout /t 2 /nobreak >nul
)
echo ERROR: Frontend did not become ready within 120 seconds.
docker compose ps
docker compose logs --tail=100 api web
pause
exit /b 1

:web_ready
echo.
echo OSTutorLLM is running at http://localhost:3000
echo API health: http://localhost:8000/health
echo Model and RAG status: sign in as faculty, then open Knowledge ^> System.
echo Press Ctrl+C to stop viewing logs. Services stay running in Docker.
docker compose ps
docker compose logs -f --tail=50 api worker web
pause
