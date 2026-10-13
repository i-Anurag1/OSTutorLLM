@echo off
rem Import your fine-tuned GGUF into Ollama and switch the app to it.
rem Usage: scripts\use-finetuned.bat path\to\folder-with-Modelfile-and-gguf
setlocal
if "%~1"=="" ( echo Usage: %~nx0 ^<folder containing Modelfile and the .gguf^> & exit /b 1 )
pushd "%~1"
ollama create ostutor-qwen3 -f Modelfile || ( popd & exit /b 1 )
popd
cd /d "%~dp0.."
if not exist .env copy /y .env.example .env >nul
powershell -NoProfile -Command "(Get-Content .env) -replace '^LLM_MODEL=.*','LLM_MODEL=ostutor-qwen3' | Set-Content .env"
docker compose up -d api worker
echo Done. The app now uses ostutor-qwen3 (check Knowledge ^> System).
