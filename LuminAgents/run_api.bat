@echo off
chcp 65001 >nul
title LuminAgents — API Server
cd /d %~dp0

if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Copy your .env file to this folder first.
    pause
    exit /b 1
)

echo [LuminAgents] Starting API on http://localhost:8000 ...
echo Press Ctrl+C to stop.
echo.
python\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
pause
