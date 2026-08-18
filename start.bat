@echo off
cd /d "%~dp0"
title Now Playing for OBS
color 0F

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python was not found. Install Python 3.10 or newer from python.org.
    echo Enable "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set "NP_PYVER=%%V"
for /f "tokens=1,2 delims=." %%A in ("%NP_PYVER%") do (
    if %%A LSS 3 goto :python_too_old
    if %%A EQU 3 if %%B LSS 10 goto :python_too_old
)

if not exist "venv\Scripts\python.exe" (
    echo Creating the local Python environment...
    python -m venv venv
    if errorlevel 1 goto :setup_failed
    echo Installing dependencies...
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    if errorlevel 1 goto :setup_failed
)

venv\Scripts\python.exe -c "from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager; import pystray; from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo Updating dependencies...
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    if errorlevel 1 goto :setup_failed
)

echo.
echo Starting Now Playing. The settings page opens after the local server is healthy.
echo Closing this window does not quit the tray app. Use its Quit menu item.
echo.
venv\Scripts\python.exe app.py %*
exit /b %errorlevel%

:python_too_old
echo.
echo Python %NP_PYVER% is too old. Python 3.10 or newer is required.
echo.
pause
exit /b 1

:setup_failed
echo.
echo Setup failed. Check your network connection, then run start.bat again.
echo.
pause
exit /b 1
