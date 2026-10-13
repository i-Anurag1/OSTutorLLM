@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  OSTutorLLM acceptance tests (run RUN.bat first)
echo ============================================================
docker compose ps
if errorlevel 1 goto fail
echo.
echo [1/3] Backend test-suite inside the API container (unit + API integration)...
docker compose exec -T api pytest -q tests
if errorlevel 1 goto fail
echo.
echo [2/3] Checking the web UI responds...
docker compose exec -T web wget -q -O - http://localhost:3000 >nul
if errorlevel 1 goto fail
echo.
echo [3/3] Service status
docker compose ps
echo ============================================================
echo  ALL ACCEPTANCE TESTS PASSED
echo ============================================================
exit /b 0
:fail
echo ============================================================
echo  ACCEPTANCE TEST FAILED  -  docker compose logs api --tail=100
echo ============================================================
exit /b 1
