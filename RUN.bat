@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo ============================================================
echo  OSTutorLLM - hybrid RAG tutor with a local LLM
echo ============================================================
if not exist .env copy /y .env.example .env >nul
set MODEL=qwen3:14b
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"LLM_MODEL=" .env') do set MODEL=%%b
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is required: https://www.docker.com/products/docker-desktop
  pause
  exit /b 1
)
where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama was not found. The app will still start and answer from your notes
  echo in "extractive" mode. Install Ollama from https://ollama.com/download for full answers.
) else (
  echo !MODEL! | findstr /b /i "ostutor" >nul
  if errorlevel 1 (
    echo Pulling/verifying !MODEL! ...
    ollama pull !MODEL!
  ) else (
    echo Using your local fine-tuned model !MODEL! - skipping pull.
  )
)
echo Starting PostgreSQL, Redis, API, worker and web UI...
echo Open http://localhost:3000 once the web container is up.
docker compose up --build
pause
