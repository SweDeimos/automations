#!/usr/bin/env python3
"""
Connection check script for Telegram-Plex Bot
This script checks if all external services are accessible
"""

import os
import sys
import logging
import requests
from dotenv import load_dotenv
import qbittorrentapi
from plexapi.server import PlexServer
import telegram
import asyncio

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging with proper encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/connections_output.txt", mode='w', encoding='utf-8'),
    ]
)

# Add console handler with proper encoding
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def check_telegram_connection():
    """Check if the Telegram bot token is valid"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")
            return False
            
        bot = telegram.Bot(token=bot_token)
        bot_info = await bot.get_me()
        bot_name = bot_info.username
        
        logger.info(f"Successfully connected to Telegram API (Bot: @{bot_name})")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Telegram API: {e}")
        return False

def check_qbittorrent_connection():
    """Check if qBittorrent is accessible"""
    try:
        host = os.getenv("QBITTORRENT_HOST")
        username = os.getenv("QBITTORRENT_USERNAME")
        password = os.getenv("QBITTORRENT_PASSWORD")
        
        if not all([host, username, password]):
            logger.error("qBittorrent environment variables are not set correctly")
            return False
            
        qb = qbittorrentapi.Client(
            host=host,
            username=username,
            password=password
        )
        qb.auth_log_in()
        version = qb.app.version
        
        logger.info(f"Successfully connected to qBittorrent {version}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to qBittorrent: {e}")
        return False

def check_plex_connection():
    """Check if Plex is accessible"""
    try:
        server_url = os.getenv("PLEX_SERVER_URL")
        token = os.getenv("PLEX_TOKEN")
        
        if not all([server_url, token]):
            logger.error("Plex environment variables are not set correctly")
            return False
            
        plex = PlexServer(server_url, token)
        version = plex.version
        
        logger.info(f"Successfully connected to Plex Media Server {version}")
        
        # Check if there are any libraries
        libraries = plex.library.sections()
        if libraries:
            lib_names = [lib.title for lib in libraries]
            logger.info(f"Found {len(libraries)} Plex libraries: {', '.join(lib_names)}")
        else:
            logger.warning("No libraries found in Plex")
            
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Plex: {e}")
        return False

def check_internet_connection():
    """Check if the internet is accessible"""
    try:
        response = requests.get("https://www.google.com", timeout=5)
        response.raise_for_status()
        
        logger.info("Internet connection is working")
        return True
    except Exception as e:
        logger.error(f"Internet connection check failed: {e}")
        return False

def check_pirate_bay_connection():
    """Check if The Pirate Bay API is accessible"""
    try:
        response = requests.get("https://apibay.org/q.php?q=test", timeout=10)
        response.raise_for_status()
        
        # Check if the response is valid JSON
        response.json()
        
        logger.info("Successfully connected to The Pirate Bay API")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to The Pirate Bay API: {e}")
        return False

async def check_connections():
    """Check all connections"""
    logger.info("Starting connection checks for Telegram-Plex Bot")
    
    # Check if .env file exists
    if os.path.exists(".env"):
        logger.info(".env file exists")
    else:
        logger.error(".env file does not exist")
        return False
    
    # Check all connections
    telegram_ok = await check_telegram_connection()
    plex_ok = check_plex_connection()
    qbittorrent_ok = check_qbittorrent_connection()
    internet_ok = check_internet_connection()
    pirate_bay_ok = check_pirate_bay_connection()
    
    # Print summary
    logger.info("\n=== Connection Check Summary ===")
    logger.info(f"Internet: {'OK' if internet_ok else 'FAILED'}")
    logger.info(f"Telegram: {'OK' if telegram_ok else 'FAILED'}")
    logger.info(f"Plex: {'OK' if plex_ok else 'FAILED'}")
    logger.info(f"qBittorrent: {'OK' if qbittorrent_ok else 'FAILED'}")
    logger.info(f"The Pirate Bay: {'OK' if pirate_bay_ok else 'FAILED'}")
    
    # Check if all connections are OK
    all_ok = all([telegram_ok, plex_ok, qbittorrent_ok, internet_ok, pirate_bay_ok])
    if all_ok:
        logger.info("All connections are working!")
    else:
        logger.error("Some connections failed. Please check the logs.")
    
    return all_ok

if __name__ == "__main__":
    success = asyncio.run(check_connections())
    sys.exit(0 if success else 1) 