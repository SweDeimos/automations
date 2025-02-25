@echo off
echo ===== Telegram Plex Bot Connection Check =====
echo.

cd /d %~dp0

echo Checking for virtual environment...
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create virtual environment. Please make sure Python is installed.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install dependencies. Please check your internet connection.
    pause
    exit /b 1
)

echo Running connection checks...
python check_connections.py
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===== Connection Check Successful =====
    echo All external services are accessible!
    echo You can now run the bot using start_bot.bat
) else (
    echo.
    echo ===== Connection Check Failed =====
    echo Some external services are not accessible.
    echo Please check the output above for details.
)

pause 