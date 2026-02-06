@echo off
cd /d "%~dp0"
title Now Playing — OBS Overlay
color 0F

echo.
echo   ======================================
echo     Now Playing — OBS Overlay
echo   ======================================
echo.

REM ── Check Python ──────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found in PATH.
    echo   Install from https://python.org
    echo.
    pause
    exit /b 1
)

REM ── Create venv if needed ─────────────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo   [1/3] Creating virtual environment ...
    python -m venv venv
    echo   [2/3] Installing dependencies ...
    venv\Scripts\pip.exe install -r requirements.txt --quiet
    echo   [3/3] Ready!
    echo.
) else (
    echo   Virtual environment OK.
    echo.
)

echo   Starting media extractor ...
start "NowPlaying-Extractor" /min venv\Scripts\python.exe nowplaying.py

REM Give the extractor a moment to write the first JSON
timeout /t 2 /nobreak >nul

echo   Starting HTTP server ...
echo.
echo   .--------------------------------------------------.
echo   :                                                  :
echo   :  OBS Browser Source URL:                         :
echo   :  http://127.0.0.1:8000/overlay.html              :
echo   :                                                  :
echo   :  Settings panel:                                 :
echo   :  http://127.0.0.1:8000/settings.html             :
echo   :                                                  :
echo   :  Preview (dark bg):                              :
echo   :  http://127.0.0.1:8000/overlay.html?debug        :
echo   :                                                  :
echo   :  Recommended OBS size: 480 x 120                 :
echo   :                                                  :
echo   '--------------------------------------------------'
echo.
echo   Press Ctrl+C to stop the server.
echo.

venv\Scripts\python.exe server.py
