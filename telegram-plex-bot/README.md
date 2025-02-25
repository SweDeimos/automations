# Telegram-Plex Bot

This project automates the following workflow:
1. Receive a movie title on Telegram.
2. Search for torrents on The Pirate Bay.
3. Present a list of torrent options for selection.
4. Add the selected torrent's magnet link to qBittorrent.
5. Wait for download completion and, if needed, extract files.
6. Trigger a Plex library update.
7. Send a notification on Telegram when the movie is available on Plex.

## Project Structure
The project consists of several Python modules that handle different aspects of the workflow:
- `bot.py`: Main Telegram bot implementation
- `downloader.py`: Handles torrent searching and downloading
- `unpacker.py`: Extracts downloaded archives if needed
- `plex_uploader.py`: Updates Plex library and retrieves movie information
- `security.py`: Handles user authentication and access control
- `rate_limiter.py`: Prevents abuse by limiting request rates
- `user_manager.py`: Manages user registration and permissions
- `notifier.py`: Sends notifications to users

## Requirements
- Python 3.8 or higher
- qBittorrent with Web UI enabled
- Plex Media Server
- Telegram Bot Token (from BotFather)

## Setup and Configuration
1. Clone this repository
2. Create a `.env` file with the following variables:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   PLEX_TOKEN=your_plex_token
   PLEX_SERVER_URL=http://your_plex_server:32400
   QBITTORRENT_HOST=http://your_qbittorrent_host:port
   QBITTORRENT_USERNAME=your_qbittorrent_username
   QBITTORRENT_PASSWORD=your_qbittorrent_password
   ALLOWED_USER_IDS=comma_separated_telegram_user_ids
   ADMIN_USER_IDS=comma_separated_admin_user_ids
   ```
3. Install dependencies: `pip install -r requirements.txt`

## Running the Bot
### Windows
Simply double-click the `start_bot.bat` file. This will:
1. Create a virtual environment if it doesn't exist
2. Install all required dependencies
3. Start the bot with proper error handling and logging

### Manual Start
1. Activate your virtual environment
2. Run `python scripts/start_bot.py`

## Verification and Testing
Before running the bot, you can verify that everything is set up correctly:

### Verify Bot Components
Run `verify_bot.bat` to check if all the bot's components are working correctly. This will:
1. Check if all required directories exist
2. Verify that all environment variables are set
3. Test if all modules can be imported

### Check External Connections
Run `check_connections.bat` to verify that the bot can connect to all required external services:
1. Telegram API
2. Plex Media Server
3. qBittorrent

### Run Tests
Run `run_tests.bat` to execute all the automated tests.

## Commands
- `/start` - Start the bot and register your user
- `/help` - Show help information
- `/update_plex` - Manually trigger a Plex library update
- `/history` - Show your search history
- `/search_again` - Start a new search
- `/cancel` - Cancel the current operation

## Troubleshooting
- Check the logs in the `logs` directory for error messages
- Ensure all required services (qBittorrent, Plex) are running
- Verify your `.env` configuration is correct
- Run the tests to verify all components are working properly

## Security
This bot implements several security measures:
- User authentication and authorization
- Rate limiting to prevent abuse
- File size checks to prevent excessive downloads
- Admin-only commands for sensitive operations

## Development
To contribute to this project:
1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Run the tests to ensure everything works
5. Submit a pull request

