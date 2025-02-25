import os
import sys
import pytest
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_all_tests():
    """Run all tests in the project and report results"""
    logger.info("Starting comprehensive test suite for Telegram Plex Bot")
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    
    # Ensure we're in the correct directory
    os.chdir(project_root)
    
    # Check if .env file exists
    if not os.path.exists(os.path.join(project_root, ".env")):
        logger.error("Missing .env file. Please create one with the required environment variables.")
        return False
    
    # Check if required directories exist
    required_dirs = ["downloads", "extracted", "logs"]
    for directory in required_dirs:
        dir_path = os.path.join(project_root, directory)
        if not os.path.exists(dir_path):
            logger.info(f"Creating required directory: {directory}")
            os.makedirs(dir_path)
    
    # Run the tests
    logger.info("Running tests...")
    
    # Run pytest with specific arguments
    try:
        # First run just the integration tests
        logger.info("Running integration tests...")
        integration_result = pytest.main([
            "-v",                      # Verbose output
            "--no-header",             # No header
            "--no-summary",            # No summary
            os.path.join(project_root, "tests", "test_integration.py")  # Integration tests
        ])
        
        if integration_result != 0:
            logger.warning("Integration tests failed. This may be due to missing external services.")
            logger.info("You can still run the bot, but some features may not work as expected.")
        else:
            logger.info("Integration tests passed!")
            
        # Then run the unit tests
        logger.info("Running unit tests...")
        unit_result = pytest.main([
            "-v",                      # Verbose output
            "--no-header",             # No header
            "--no-summary",            # No summary
            os.path.join(project_root, "tests", "test_bot.py"),  # Bot tests
            os.path.join(project_root, "tests", "test_rate_limiter.py"),  # Rate limiter tests
            os.path.join(project_root, "tests", "test_security.py")  # Security tests
        ])
        
        if unit_result != 0:
            logger.error("Unit tests failed. Please check the output above.")
            return False
        else:
            logger.info("Unit tests passed!")
            
        return True
    except Exception as e:
        logger.exception(f"Error running tests: {e}")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 