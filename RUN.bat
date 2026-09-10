@echo off
cd /d "%~dp0"
echo Starting OSTutorLLM 3.0...
docker compose up --build
pause
