# Configuration settings
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
if not load_dotenv():
    logger.warning("No .env file found or failed to load it. Using environment variables.")

# Required environment variables
REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "PLEX_TOKEN",
    "PLEX_SERVER_URL",
    "QBITTORRENT_HOST",
    "QBITTORRENT_USERNAME",
    "QBITTORRENT_PASSWORD"
]

# Optional environment variables with defaults
OPTIONAL_VARS = {
    "ALLOWED_USER_IDS": "",
    "ADMIN_USER_IDS": "",
    "LOG_LEVEL": "INFO"
}

def get_env_var(name: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Get an environment variable with validation.
    
    Args:
        name: Name of the environment variable
        default: Default value if not set
        required: Whether the variable is required
        
    Returns:
        The environment variable value or default
        
    Raises:
        ValueError: If the variable is required but not set
    """
    value = os.getenv(name, default)
    if required and not value:
        error_msg = f"Required environment variable {name} is not set"
        logger.error(error_msg)
        raise ValueError(error_msg)
    return value

# Check for required environment variables
missing_vars = []
for var in REQUIRED_VARS:
    if not os.getenv(var):
        missing_vars.append(var)

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    logger.error("Please set these variables in your .env file or environment")
    sys.exit(1)

# Set optional variables with defaults
for var, default in OPTIONAL_VARS.items():
    if not os.getenv(var):
        logger.info(f"Optional variable {var} not set, using default")
        os.environ[var] = default

# Bot configuration
TELEGRAM_BOT_TOKEN = get_env_var("TELEGRAM_BOT_TOKEN", required=True)
QBITTORRENT_HOST = get_env_var("QBITTORRENT_HOST", required=True)
QBITTORRENT_USERNAME = get_env_var("QBITTORRENT_USERNAME", required=True)
QBITTORRENT_PASSWORD = get_env_var("QBITTORRENT_PASSWORD", required=True)
PLEX_SERVER_URL = get_env_var("PLEX_SERVER_URL", required=True)
PLEX_TOKEN = get_env_var("PLEX_TOKEN", required=True)

# Parse user IDs from comma-separated strings
def parse_user_ids(env_var: str) -> List[int]:
    """
    Parse a comma-separated string of user IDs into a list of integers.
    
    Args:
        env_var: Environment variable name containing comma-separated IDs
        
    Returns:
        List of integer user IDs
    """
    try:
        return [int(id.strip()) for id in get_env_var(env_var, "").split(",") if id.strip()]
    except ValueError as e:
        logger.error(f"Error parsing {env_var}: {e}")
        return []

ALLOWED_USER_IDS = parse_user_ids("ALLOWED_USER_IDS")
ADMIN_USER_IDS = parse_user_ids("ADMIN_USER_IDS")

# Set log level from environment
LOG_LEVEL = get_env_var("LOG_LEVEL", "INFO").upper()
try:
    logging.getLogger().setLevel(getattr(logging, LOG_LEVEL))
    logger.info(f"Log level set to {LOG_LEVEL}")
except AttributeError:
    logger.warning(f"Invalid log level: {LOG_LEVEL}, using INFO")
    logging.getLogger().setLevel(logging.INFO)

# Validate configuration
if not ALLOWED_USER_IDS and not ADMIN_USER_IDS:
    logger.warning("No allowed users or admins specified. Bot will not be accessible to anyone.")

# Log configuration summary
logger.info("Configuration loaded successfully")
logger.info(f"Allowed users: {len(ALLOWED_USER_IDS)}")
logger.info(f"Admin users: {len(ADMIN_USER_IDS)}")
logger.debug(f"Plex server: {PLEX_SERVER_URL}")
logger.debug(f"qBittorrent host: {QBITTORRENT_HOST}")

# Additional configuration settings
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
LOG_DIR = "logs"

# Create required directories if they don't exist
for directory in [DOWNLOAD_DIR, EXTRACT_DIR, LOG_DIR]:
    if not os.path.exists(directory):
        logger.info(f"Creating directory: {directory}")
        os.makedirs(directory, exist_ok=True)
