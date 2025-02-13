from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import logging
from typing import List, Set
from config import ALLOWED_USER_IDS  # Add this to your config.py

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