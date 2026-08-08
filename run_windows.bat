@echo off
setlocal

REM ============================================================
REM   Hospital Appointment Management System - Windows launcher
REM   Double-click this file to set up and start the server.
REM ============================================================

cd /d "%~dp0"

echo ==========================================
echo    Hospital System - Starting up
echo ==========================================
echo.

REM --- Pick an available Python launcher -----------------------
set "PY_CMD="
where py >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>&1 && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [X] Python was not found on this system.
    echo     Install Python 3.13 or later from https://www.python.org/downloads/
    echo     and make sure "Add Python to PATH" is checked during setup.
    echo.
    pause
    exit /b 1
)

REM --- Create the virtual environment if it is missing ---------
if not exist "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating it now...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo [X] Failed to create the virtual environment.
        pause
        exit /b 1
    )
    call "venv\Scripts\activate.bat"
    echo [-] Installing dependencies, please wait...
    python -m pip install --upgrade pip >nul
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [X] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    call "venv\Scripts\activate.bat"
)

echo [OK] Virtual environment is active.
echo [-]  Opening the API documentation in your browser...

REM --- Open /docs once the server has had time to boot ---------
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8000/docs'"

echo [-]  Starting the server (Uvicorn) on port 8000...
echo ------------------------------------------
echo Note: press Ctrl+C or close this window to stop the server.
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

echo.
echo Server stopped.
pause
