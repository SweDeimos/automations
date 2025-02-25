from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import logging
from typing import List, Set, Dict, Any, Callable, Optional
from config import ALLOWED_USER_IDS, ADMIN_USER_IDS
from user_manager import user_manager, UserRole

logger = logging.getLogger(__name__)

# Error messages for security-related issues
ERROR_MESSAGES = {
    "unauthorized": "⛔ Sorry, you are not authorized to use this bot.\nPlease contact the administrator for access.",
    "admin_only": "⛔ This command is only available to administrators.",
    "size_limit": "⚠️ This file exceeds your size limit ({size_limit:.2f} GB).\nPlease choose a smaller file or contact an administrator."
}

class SecurityManager:
    """
    Manages security and access control for the bot.
    Handles user authorization and permission checks.
    """
    def __init__(self, allowed_users: List[int], admin_users: List[int]):
        """
        Initialize the security manager with allowed and admin users.
        
        Args:
            allowed_users: List of user IDs allowed to use the bot
            admin_users: List of user IDs with admin privileges
        """
        self.allowed_users: Set[int] = set(allowed_users)
        self.admin_users: Set[int] = set(admin_users)
        
        # Add admin users to allowed users automatically
        self.allowed_users.update(self.admin_users)
        
        logger.info(f"Security initialized with {len(self.allowed_users)} allowed users and {len(self.admin_users)} admins")
    
    def is_user_allowed(self, user_id: int) -> bool:
        """
        Check if a user is allowed to use the bot.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            True if the user is allowed, False otherwise
        """
        # First check our internal list
        if user_id in self.allowed_users:
            return True
            
        # Then check the user manager (which might have been updated at runtime)
        if user := user_manager.get_user(user_id):
            return True
            
        return False
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if a user has admin privileges.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            True if the user is an admin, False otherwise
        """
        # First check our internal list
        if user_id in self.admin_users:
            return True
            
        # Then check the user manager
        return user_manager.is_admin(user_id)
    
    async def send_error_message(self, update: Update, message: str) -> None:
        """
        Send an error message to the user.
        
        Args:
            update: The update object
            message: The error message to send
        """
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=True)
        elif update.message:
            await update.message.reply_text(message)

# Create global instance
security = SecurityManager(ALLOWED_USER_IDS, ADMIN_USER_IDS)

def restricted_access():
    """
    Decorator to restrict bot access to allowed users only.
    
    Returns:
        Decorated function that checks user permissions before execution
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            if not security.is_user_allowed(user_id):
                logger.warning(f"Unauthorized access attempt by user {user_id} ({username})")
                await security.send_error_message(update, ERROR_MESSAGES["unauthorized"])
                return None
                
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator 

def admin_only():
    """
    Decorator to restrict access to admin users only.
    
    Returns:
        Decorated function that checks admin permissions before execution
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            
            if not security.is_admin(user_id):
                logger.warning(f"Unauthorized admin access attempt by user {user_id} ({username})")
                await security.send_error_message(update, ERROR_MESSAGES["admin_only"])
                return None
            
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def check_file_size_limit():
    """
    Decorator to check file size limits for users.
    
    Returns:
        Decorated function that checks file size limits before execution
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Get the torrent size from context if available
            if torrent := context.user_data.get('selected_torrent'):
                try:
                    size = int(torrent.get('size', 0))
                    
                    # Get user's max file size
                    user = user_manager.get_user(user_id)
                    if not user:
                        logger.warning(f"User {user_id} not found in user manager")
                        return await func(update, context, *args, **kwargs)
                    
                    max_size = user.max_file_size
                    max_size_gb = max_size / (1024 * 1024 * 1024)
                    
                    if not user_manager.can_access_file_size(user_id, size):
                        logger.info(f"User {user_id} exceeded file size limit: {size} > {max_size}")
                        error_message = ERROR_MESSAGES["size_limit"].format(size_limit=max_size_gb)
                        await security.send_error_message(update, error_message)
                        return None
                except (ValueError, TypeError) as e:
                    logger.error(f"Error checking file size: {e}")
                    # Continue with the function if we can't check the size
            
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator 