@echo off
echo ===== Telegram Plex Bot Verification =====
echo.

cd /d %~dp0

echo Checking for required directories...
if not exist logs mkdir logs
if not exist downloads mkdir downloads
if not exist extracted mkdir extracted

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

echo Running verification...
python verify_bot.py
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===== Verification Successful =====
    echo All components are working correctly!
    echo You can now run the bot using start_bot.bat
) else (
    echo.
    echo ===== Verification Failed =====
    echo Some components are not working correctly.
    echo Please check the output above for details.
)

pause 