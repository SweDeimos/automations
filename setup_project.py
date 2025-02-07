import os

# Define project structure
folders = [
    "telegram-plex-bot",
    "telegram-plex-bot/logs",
    "telegram-plex-bot/downloads",
    "telegram-plex-bot/extracted",
    "telegram-plex-bot/scripts"
]

files = {
    "telegram-plex-bot/bot.py": "# Main bot logic",
    "telegram-plex-bot/config.py": "# Configuration settings",
    "telegram-plex-bot/downloader.py": "# Torrent search and download logic",
    "telegram-plex-bot/unpacker.py": "# Handles file extraction",
    "telegram-plex-bot/plex_uploader.py": "# Uploads media to Plex",
    "telegram-plex-bot/notifier.py": "# Sends Telegram notifications",
    "telegram-plex-bot/requirements.txt": "python-telegram-bot\nrequests\nqbittorrent-api\nplexapi\ndotenv\nrarfile\npatool",
    "telegram-plex-bot/.env": "TELEGRAM_BOT_TOKEN=\nPLEX_TOKEN=\nPLEX_SERVER_URL=\nQBITTORRENT_HOST=\nQBITTORRENT_PORT=",
    "telegram-plex-bot/README.md": "# Telegram to Plex Bot\n\nThis project automates searching, downloading, and uploading movies to Plex."
}

# Create folders
for folder in folders:
    os.makedirs(folder, exist_ok=True)

# Create files
for path, content in files.items():
    with open(path, "w") as f:
        f.write(content)

print("Project structure created successfully!")
