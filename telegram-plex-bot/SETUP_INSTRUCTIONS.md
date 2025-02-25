# Telegram Plex Bot Setup Instructions

## Issues Fixed

1. **Unicode Encoding Error**: Fixed the issue with Unicode characters (✅, ❌) in the Windows console by modifying the logging setup.
2. **Missing Dependencies**: Created a script to properly install all required dependencies in a virtual environment.

## Setup Steps

1. **Install Python**: Make sure you have Python 3.8 or higher installed.

2. **Install Dependencies**: Run the `install_dependencies.bat` script to create a virtual environment and install all required dependencies.
   ```
   install_dependencies.bat
   ```

3. **Verify Bot**: Run the verification script to ensure all components are working correctly.
   ```
   verify_bot.bat
   ```

4. **Start Bot**: Start the bot using the start_bot script.
   ```
   start_bot.bat
   ```

## Troubleshooting

### Missing Dependencies
If you see errors like `No module named 'telegram'` or `No module named 'qbittorrentapi'`, run the `install_dependencies.bat` script to install all required packages.

### Unicode Encoding Errors
The Unicode encoding errors in the console have been fixed by modifying the logging setup in `verify_bot.py`. If you still see encoding errors, make sure you're using a console that supports UTF-8 encoding.

### Virtual Environment Issues
If you have issues with the virtual environment:
1. Delete the `.venv` directory
2. Run `install_dependencies.bat` again to create a fresh virtual environment

## Required Dependencies
- python-telegram-bot==20.0
- python-dotenv
- qbittorrent-api
- plexapi
- rarfile
- patool
- pytest
- pytest-asyncio
- setuptools
- requests
- aiohttp
- python-telegram-bot[job-queue] 