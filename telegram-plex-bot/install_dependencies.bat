@echo off
echo Installing dependencies for Telegram Plex Bot...

:: Check if Python is installed
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

:: Check Python version
for /f "tokens=2" %%V in ('python -c "import sys; print(sys.version.split()[0])"') do (
    set PYTHON_VERSION=%%V
)
echo Python version: %PYTHON_VERSION%

:: Create virtual environment if it doesn't exist
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

:: Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install dependencies
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

echo.
echo Dependencies installed successfully!
echo.
echo You can now run the bot using start_bot.bat
echo.
pause 