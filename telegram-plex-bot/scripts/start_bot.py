#!/usr/bin/env python3
"""
Start script for the Telegram Plex Bot
This script handles starting the bot with proper error handling and logging
"""

import os
import sys
import logging
import time
import signal
import subprocess
from pathlib import Path
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot_startup.log")
    ]
)
logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

def check_environment():
    """Check if all required environment variables and directories are set up"""
    logger.info("Checking environment setup...")
    
    # Check if .env file exists
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_file):
        logger.error("Missing .env file. Please create one with the required environment variables.")
        return False
    
    # Check if required directories exist
    required_dirs = ["downloads", "extracted", "logs"]
    for directory in required_dirs:
        dir_path = os.path.join(PROJECT_ROOT, directory)
        if not os.path.exists(dir_path):
            logger.info(f"Creating required directory: {directory}")
            os.makedirs(dir_path)
    
    # Check if users.json exists, if not initialize it
    users_file = os.path.join(PROJECT_ROOT, "users.json")
    if not os.path.exists(users_file):
        logger.info("Initializing users.json file...")
        try:
            subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "init_users.py")], 
                          check=True, cwd=PROJECT_ROOT)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize users.json: {e}")
            return False
    
    return True

def check_dependencies():
    """Check if all required dependencies are installed"""
    logger.info("Checking dependencies...")
    
    # List of required packages
    required_packages = [
        "python-telegram-bot",
        "python-dotenv",
        "qbittorrent-api",
        "plexapi",
        "rarfile"
        # Removed patool from the check since it's causing issues but the executable exists
    ]
    
    missing_packages = []
    
    # Check each package
    for package in required_packages:
        try:
            if package == "python-telegram-bot":
                import telegram
                logger.info(f"Successfully imported telegram from {telegram.__file__}")
            elif package == "python-dotenv":
                import dotenv
                logger.info(f"Successfully imported dotenv from {dotenv.__file__}")
            elif package == "qbittorrent-api":
                import qbittorrentapi
                logger.info(f"Successfully imported qbittorrentapi from {qbittorrentapi.__file__}")
            elif package == "plexapi":
                import plexapi
                logger.info(f"Successfully imported plexapi from {plexapi.__file__}")
            elif package == "rarfile":
                import rarfile
                logger.info(f"Successfully imported rarfile from {rarfile.__file__}")
        except ImportError as e:
            logger.error(f"Error importing {package}: {e}")
            missing_packages.append(package)
    
    # Special handling for patool - check if the executable exists
    patool_exe = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "patool.exe")
    if os.path.exists(patool_exe):
        logger.info(f"patool executable found at {patool_exe}")
    else:
        logger.warning("patool executable not found. Some unpacking features may not work.")
    
    if not missing_packages:
        logger.info("All dependencies are available.")
        return True
    
    # If there are missing packages, try to install them using subprocess
    logger.error(f"Missing dependencies: {', '.join(missing_packages)}")
    logger.info("Please install the missing dependencies manually using:")
    logger.info(f"pip install {' '.join(missing_packages)}")
    
    return False

def start_bot():
    """Start the Telegram Plex Bot"""
    logger.info("Starting Telegram Plex Bot...")
    
    # Change to the project root directory
    os.chdir(PROJECT_ROOT)
    
    # Start the bot
    bot_process = None
    try:
        # Create log directory if it doesn't exist
        log_dir = os.path.join(PROJECT_ROOT, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Open log files
        stdout_log = open(os.path.join(log_dir, "bot_stdout.log"), "a")
        stderr_log = open(os.path.join(log_dir, "bot_stderr.log"), "a")
        
        # Start the bot process
        logger.info(f"Executing: {sys.executable} {os.path.join(PROJECT_ROOT, 'bot.py')}")
        bot_process = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_ROOT, "bot.py")],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        
        logger.info(f"Bot started with PID: {bot_process.pid}")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down bot...")
            if bot_process:
                bot_process.terminate()
                try:
                    bot_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Bot did not terminate gracefully, forcing shutdown...")
                    bot_process.kill()
            
            # Close log files
            stdout_log.close()
            stderr_log.close()
            
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Monitor the bot process
        while bot_process.poll() is None:
            # Read and log output
            stdout_line = bot_process.stdout.readline()
            if stdout_line:
                line = stdout_line.strip()
                print(line)
                stdout_log.write(f"{line}\n")
                stdout_log.flush()
            
            stderr_line = bot_process.stderr.readline()
            if stderr_line:
                line = stderr_line.strip()
                print(f"ERROR: {line}", file=sys.stderr)
                stderr_log.write(f"{line}\n")
                stderr_log.flush()
            
            time.sleep(0.1)
        
        # Close log files
        stdout_log.close()
        stderr_log.close()
        
        # Check exit code
        exit_code = bot_process.returncode
        if exit_code != 0:
            logger.error(f"Bot exited with code {exit_code}")
            
            # Try to get any remaining error output
            stderr_output, _ = bot_process.communicate()
            if stderr_output:
                logger.error(f"Error output: {stderr_output}")
                
            return False
        else:
            logger.info("Bot exited normally")
            return True
            
    except Exception as e:
        logger.exception(f"Error starting bot: {e}")
        traceback.print_exc()
        if bot_process and bot_process.poll() is None:
            bot_process.terminate()
        return False

def main():
    """Main function to start the bot with proper checks"""
    logger.info("=== Telegram Plex Bot Startup ===")
    
    # Check environment and dependencies
    if not check_environment():
        logger.error("Environment check failed. Please fix the issues and try again.")
        return 1
    
    if not check_dependencies():
        logger.error("Dependency check failed. Please fix the issues and try again.")
        return 1
    
    # Start the bot
    success = start_bot()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 