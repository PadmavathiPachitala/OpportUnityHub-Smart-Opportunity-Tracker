@echo off
echo ============================================
echo  OpportUnity Hub — Backend Startup
echo ============================================
echo.
echo Installing dependencies...
pip install -r backend\requirements.txt -q
echo.
echo Starting FastAPI server on http://localhost:8000
echo Press Ctrl+C to stop.
echo.
cd /d "%~dp0"
python -m uvicorn backend.main:app --reload --port 8000 --host 0.0.0.0
pause
