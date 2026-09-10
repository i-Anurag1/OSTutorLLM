@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo OSTutorLLM FULL SYSTEM ACCEPTANCE TEST
echo ============================================================
docker compose ps
if errorlevel 1 goto fail

echo.
echo [1/3] Running backend end-to-end pytest suite...
docker compose exec -T api pytest -q /app/tests/test_full_system.py
if errorlevel 1 goto fail

echo.
echo [2/3] Checking frontend health...
docker compose exec -T web wget -q -O - http://localhost:3000 >nul
if errorlevel 1 goto fail

echo Frontend health: PASS

echo.
echo [3/3] Final service status...
docker compose ps
 echo.
echo ============================================================
echo ALL ACCEPTANCE TESTS PASSED
echo ============================================================
exit /b 0

:fail
echo.
echo ============================================================
echo ACCEPTANCE TEST FAILED
echo ============================================================
echo Run: docker compose logs api --tail=100
exit /b 1
