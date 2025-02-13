from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import logging
from typing import List, Set
from config import ALLOWED_USER_IDS  # Add this to your config.py
from user_manager import user_manager, UserRole

logger = logging.getLogger(__name__)

class SecurityManager:
    def __init__(self, allowed_users: List[int]):
        self.allowed_users: Set[int] = set(allowed_users)
    
    def is_user_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_users

# Create global instance
security = SecurityManager(ALLOWED_USER_IDS)

def restricted_access():
    """Decorator to restrict bot access to allowed users only"""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            if not security.is_user_allowed(user_id):
                logger.warning(f"Unauthorized access attempt by user {user_id}")
                await update.message.reply_text(
                    "⛔ Sorry, you are not authorized to use this bot.\n"
                    "Please contact the administrator for access."
                )
                return
                
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator 

def admin_only():
    """Decorator to restrict access to admin users only"""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            if not user_manager.is_admin(user_id):
                logger.warning(f"Unauthorized admin access attempt by user {user_id}")
                await update.message.reply_text(
                    "⛔ This command is only available to administrators."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def check_file_size_limit():
    """Decorator to check file size limits for users"""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Get the torrent size from context if available
            if torrent := context.user_data.get('selected_torrent'):
                size = int(torrent.get('size', 0))
                if not user_manager.can_access_file_size(user_id, size):
                    await update.message.reply_text(
                        "⚠️ This file exceeds your size limit (5GB).\n"
                        "Please choose a smaller file or contact an administrator."
                    )
                    return
            
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator 