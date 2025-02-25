@echo off
setlocal enabledelayedexpansion

:: Create logs directory if it doesn't exist
if not exist logs mkdir logs

:: Set the log file path
set LOG_FILE=logs\bot_startup.log

:: Clear previous log
echo Starting Telegram Plex Bot at %date% %time% > %LOG_FILE%
echo Starting Telegram Plex Bot at %date% %time%

:: Set UTF-8 code page for console
chcp 65001 > nul
echo Console set to UTF-8 encoding >> %LOG_FILE%
echo Console set to UTF-8 encoding

:: Check if Python is installed
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH. Please install Python 3.8 or higher. >> %LOG_FILE%
    echo ERROR: Python is not installed or not in PATH. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

:: Check if virtual environment exists
if not exist .venv (
    echo ERROR: Virtual environment not found. Please run install_dependencies.bat first. >> %LOG_FILE%
    echo ERROR: Virtual environment not found. Please run install_dependencies.bat first.
    pause
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate

:: Check Python version
for /f "tokens=2" %%V in ('python -c "import sys; print(sys.version.split()[0])"') do (
    set PYTHON_VERSION=%%V
)
echo Python version: %PYTHON_VERSION% >> %LOG_FILE%
echo Python version: %PYTHON_VERSION%

:: Verify environment setup
echo Running verification script... >> %LOG_FILE%
echo Running verification script...
python verify_bot.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: Verification failed. Check logs/verify_output.txt for details. >> %LOG_FILE%
    echo ERROR: Verification failed. Check logs/verify_output.txt for details.
    type logs\verify_output.txt
    pause
    exit /b 1
)
echo Verification completed successfully. >> %LOG_FILE%
echo Verification completed successfully.

:: Check connections
echo Checking connections to external services... >> %LOG_FILE%
echo Checking connections to external services...
python check_connections.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: Connection check failed. Check logs/connections_output.txt for details. >> %LOG_FILE%
    echo ERROR: Connection check failed. Check logs/connections_output.txt for details.
    type logs\connections_output.txt
    pause
    exit /b 1
)
echo All connections verified successfully. >> %LOG_FILE%
echo All connections verified successfully.

:: Create logs directory if it doesn't exist
if not exist logs mkdir logs

:: Start the bot with automatic restart on crash
echo Starting the bot... >> %LOG_FILE%
echo Starting the bot...
echo Bot is now running. Press Ctrl+C to stop.
echo If the bot crashes, it will automatically restart after 5 seconds.

:loop
echo [%date% %time%] Bot instance started >> %LOG_FILE%
echo [%date% %time%] Bot instance started

:: Run the bot
python bot.py
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% neq 0 (
    echo [%date% %time%] Bot crashed with exit code %EXIT_CODE%. Restarting in 5 seconds... >> %LOG_FILE%
    echo [%date% %time%] Bot crashed with exit code %EXIT_CODE%. Restarting in 5 seconds...
    timeout /t 5 /nobreak > nul
    goto loop
) else (
    echo [%date% %time%] Bot shut down gracefully with exit code 0. >> %LOG_FILE%
    echo [%date% %time%] Bot shut down gracefully with exit code 0.
)

echo Bot has stopped. Check %LOG_FILE% for details.
pause 