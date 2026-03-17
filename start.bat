@echo off
cd /d "%~dp0"
title Now Playing - OBS Overlay
color 0F

echo.
echo   ======================================
echo     Now Playing - OBS Overlay
echo   ======================================
echo.

REM -- Detect mode: .exe build or Python source ----------------------
if exist "NowPlaying.exe" goto :exe_mode

REM ================================================================
REM   Python / source mode
REM ================================================================

REM -- Preflight: find Python ----------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo   [!] Python is not in your PATH.
    echo       Download it from https://python.org and make sure
    echo       "Add Python to PATH" is checked during install.
    echo.
    pause
    exit /b 1
)

REM -- Preflight: check Python version >= 3.10 -----------------------
for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set PYVER=%%V
for /f "tokens=1,2 delims=." %%A in ("%PYVER%") do (
    if %%A LSS 3 (
        echo   [!] Python %PYVER% is too old. You need 3.10 or newer.
        pause
        exit /b 1
    )
    if %%A EQU 3 if %%B LSS 10 (
        echo   [!] Python %PYVER% is too old. You need 3.10 or newer.
        pause
        exit /b 1
    )
)
echo   Python %PYVER% found.

REM -- Preflight: check if port 8000 is free -------------------------
netstat -an | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   [!] Port 8000 is already in use.
    echo       Close whatever is using it, or start the server
    echo       manually with a different port:
    echo         venv\Scripts\python server.py 9000
    echo.
    pause
    exit /b 1
)

REM -- Create venv if needed -----------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo   [1/3] Creating virtual environment ...
    python -m venv venv
    if errorlevel 1 (
        echo   [!] Failed to create venv. Check your Python installation.
        pause
        exit /b 1
    )
    echo   [2/3] Installing dependencies ...
    venv\Scripts\pip.exe install -r requirements.txt --quiet
    if errorlevel 1 (
        echo   [!] pip install failed. Check your internet connection.
        pause
        exit /b 1
    )
    echo   [3/3] Ready!
    echo.
) else (
    echo   Virtual environment OK.
    echo.
)

REM -- Verify winrt import works -------------------------------------
venv\Scripts\python.exe -c "from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager" >nul 2>&1
if errorlevel 1 (
    echo   [!] WinRT packages are broken or missing. Reinstalling ...
    venv\Scripts\pip.exe install --force-reinstall -r requirements.txt --quiet
    venv\Scripts\python.exe -c "from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager" >nul 2>&1
    if errorlevel 1 (
        echo   [!] Still can't import winrt. Try deleting the venv folder
        echo       and running start.bat again.
        pause
        exit /b 1
    )
)
echo   WinRT packages OK.

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
echo   :  Diagnostics:                                    :
echo   :  http://127.0.0.1:8000/status.html               :
echo   :                                                  :
echo   :  Recommended OBS size: 480 x 120                 :
echo   :                                                  :
echo   '--------------------------------------------------'
echo.

REM -- Open settings page in default browser -------------------------
start "" "http://127.0.0.1:8000/settings.html"

echo   Press Ctrl+C to stop the server.
echo.

venv\Scripts\python.exe server.py
goto :eof

REM ================================================================
REM   .exe mode (no Python needed)
REM ================================================================
:exe_mode

REM -- Check for updates if requested --------------------------------
if "%1"=="--update" (
    echo   Checking for updates ...
    NowPlaying.exe --update
    echo.
    pause
    exit /b
)

echo   Running from standalone build.
echo.

REM -- Check if port 8000 is free ------------------------------------
netstat -an | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   [!] Port 8000 is already in use.
    echo       Close whatever is using it first.
    echo.
    pause
    exit /b 1
)

echo   .--------------------------------------------------.
echo   :                                                  :
echo   :  OBS Browser Source URL:                         :
echo   :  http://127.0.0.1:8000/overlay.html              :
echo   :                                                  :
echo   :  Settings panel:                                 :
echo   :  http://127.0.0.1:8000/settings.html             :
echo   :                                                  :
echo   :  Diagnostics:                                    :
echo   :  http://127.0.0.1:8000/status.html               :
echo   :                                                  :
echo   :  Recommended OBS size: 480 x 120                 :
echo   :                                                  :
echo   '--------------------------------------------------'
echo.

start "" "http://127.0.0.1:8000/settings.html"

echo   Press Ctrl+C to stop.
echo.

NowPlaying.exe
