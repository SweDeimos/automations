#!/usr/bin/env python3
"""
Verification script for Telegram-Plex Bot
This script checks if all the core components are working correctly
"""

import os
import sys
import logging
from pathlib import Path
import importlib.util
import traceback

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging with proper encoding for Windows
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/verify_output.txt", mode='w', encoding='utf-8'),
    ]
)

# Add console handler with proper encoding
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)

def check_module(module_name, file_path):
    """Check if a module can be imported"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        logger.info(f"Module {module_name} loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to load module {module_name}: {e}")
        traceback.print_exc()
        return False

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "PLEX_TOKEN",
        "PLEX_SERVER_URL",
        "QBITTORRENT_HOST",
        "QBITTORRENT_USERNAME",
        "QBITTORRENT_PASSWORD",
        "ALLOWED_USER_IDS",
        "ADMIN_USER_IDS"
    ]
    
    from dotenv import load_dotenv
    load_dotenv()
    
    all_vars_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"Environment variable {var} is set")
        else:
            logger.error(f"Environment variable {var} is not set")
            all_vars_present = False
    
    return all_vars_present

def check_directories():
    """Check if all required directories exist"""
    required_dirs = ["downloads", "extracted", "logs"]
    
    all_dirs_exist = True
    for directory in required_dirs:
        if os.path.exists(directory):
            logger.info(f"Directory {directory} exists")
        else:
            logger.warning(f"Directory {directory} does not exist, creating it...")
            os.makedirs(directory)
            all_dirs_exist = False
    
    return all_dirs_exist

def verify_bot():
    """Verify that the bot's core components work correctly"""
    logger.info("Starting verification of Telegram-Plex Bot")
    
    # Get the project root directory
    project_root = Path(__file__).parent
    
    # Ensure we're in the correct directory
    os.chdir(project_root)
    
    # Check if .env file exists
    if os.path.exists(os.path.join(project_root, ".env")):
        logger.info(".env file exists")
    else:
        logger.error(".env file does not exist")
        return False
    
    # Check directories
    check_directories()
    
    # Check environment variables
    if not check_environment():
        return False
    
    # Check core modules
    modules_to_check = {
        "bot": "bot.py",
        "downloader": "downloader.py",
        "unpacker": "unpacker.py",
        "plex_uploader": "plex_uploader.py",
        "security": "security.py",
        "rate_limiter": "rate_limiter.py",
        "user_manager": "user_manager.py",
        "notifier": "notifier.py"
    }
    
    all_modules_ok = True
    for module_name, file_path in modules_to_check.items():
        if not check_module(module_name, file_path):
            all_modules_ok = False
    
    if not all_modules_ok:
        logger.error("Some modules failed to load")
        return False
    
    logger.info("All checks passed!")
    return True

if __name__ == "__main__":
    success = verify_bot()
    sys.exit(0 if success else 1) 