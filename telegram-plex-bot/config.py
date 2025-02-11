# Configuration settings

# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
QBITTORRENT_HOST = os.getenv("QBITTORRENT_HOST")
QBITTORRENT_USERNAME = os.getenv("QBITTORRENT_USERNAME")
QBITTORRENT_PASSWORD = os.getenv("QBITTORRENT_PASSWORD")
PLEX_SERVER_URL = os.getenv("PLEX_SERVER_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
