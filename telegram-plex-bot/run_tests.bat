@echo off
echo ===== Telegram Plex Bot Tests =====
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

echo Running tests...
python tests\test_all.py
if %ERRORLEVEL% EQU 0 (
    echo All tests passed!
) else (
    echo Some tests failed. Please check the output above.
)

pause 