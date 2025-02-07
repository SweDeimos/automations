import os
from dotenv import load_dotenv

load_dotenv()

print("TELEGRAM_BOT_TOKEN:", os.getenv("TELEGRAM_BOT_TOKEN"))
print("PLEX_TOKEN:", os.getenv("PLEX_TOKEN"))
print("PLEX_SERVER_URL:", os.getenv("PLEX_SERVER_URL"))
print("QBITTORRENT_HOST:", os.getenv("QBITTORRENT_HOST"))
print("QBITTORRENT_PORT:", os.getenv("QBITTORRENT_PORT"))
print("QBITTORRENT_USERNAME:", os.getenv("QBITTORRENT_USERNAME"))
print("QBITTORRENT_PASSWORD:", os.getenv("QBITTORRENT_PASSWORD"))
# This script loads the environment variables from the .env file and prints the values of specific variables used in the Telegram-Plex bot project. You can use this script to verify that the environment variables are correctly loaded and accessible within the project.