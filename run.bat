@echo off
cd /d "%~dp0"

:: TradeMind Signal Bot - Windows Launcher

echo ============================================
echo   TradeMind Signal Bot
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Create virtual environment if missing
if not exist ".venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Install requirements
echo [*] Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Check .env
if not exist ".env" (
    echo [WARN] No .env file found. Copying from .env.example...
    copy .env.example .env >nul
    echo [WARN] Please edit .env and set your BOT_TOKEN before running.
    notepad .env
    pause
)

echo [*] Starting TradeMind Signal Bot...
echo.
python bot.py

pause
