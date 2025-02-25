from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable

from telegram import Update
from telegram.ext import ContextTypes

# Define rate limits for different command types
RATE_LIMITS = {
    "search_movie": 15,  # 15 searches per minute
    "select_torrent": 10,  # 10 selections per minute
    "recent": 20,  # 20 recent checks per minute
    "history": 20,  # 20 history checks per minute
    "default": 30,  # 30 other commands per minute
    "inline_search": 20,  # 20 inline searches per minute
}

class RateLimiter:
    """
    Manages rate limiting for bot commands to prevent abuse.
    Tracks command usage per user and enforces limits based on command type.
    """
    
    def __init__(self, time_window_seconds: int = 60):
        """
        Initialize the rate limiter.
        
        Args:
            time_window_seconds: The time window in seconds to track command usage
        """
        # Structure: {user_id: {command: [timestamp1, timestamp2, ...]}}
        self.command_history: Dict[int, Dict[str, List[datetime]]] = {}
        self.time_window = timedelta(seconds=time_window_seconds)
    
    def _clean_old_history(self, user_id: int, command: str) -> None:
        """
        Remove timestamps older than the time window.
        
        Args:
            user_id: The user ID
            command: The command to clean history for
        """
        if user_id in self.command_history and command in self.command_history[user_id]:
            now = datetime.now()
            self.command_history[user_id][command] = [
                timestamp for timestamp in self.command_history[user_id][command]
                if now - timestamp < self.time_window
            ]
    
    def is_rate_limited(self, user_id: int, command: str) -> bool:
        """
        Check if a user has exceeded the rate limit for a command.
        
        Args:
            user_id: The user ID
            command: The command to check
            
        Returns:
            True if rate limited, False otherwise
        """
        # Initialize user's command history if not exists
        if user_id not in self.command_history:
            self.command_history[user_id] = {}
        
        if command not in self.command_history[user_id]:
            self.command_history[user_id][command] = []
        
        # Clean old history
        self._clean_old_history(user_id, command)
        
        # Get rate limit for this command
        rate_limit = RATE_LIMITS.get(command, RATE_LIMITS["default"])
        
        # Check if rate limited
        if len(self.command_history[user_id][command]) >= rate_limit:
            return True
        
        # Add current timestamp
        self.command_history[user_id][command].append(datetime.now())
        return False

# Create global instance
rate_limiter = RateLimiter()

def rate_limit(command_type: str = "default"):
    """
    Decorator to apply rate limiting to bot commands.
    
    Args:
        command_type: The type of command for rate limiting
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Check if rate limited
            if rate_limiter.is_rate_limited(user_id, command_type):
                rate_limit = RATE_LIMITS.get(command_type, RATE_LIMITS["default"])
                
                error_message = (
                    f"⚠️ Rate limit exceeded for this command.\n"
                    f"You can use this command {rate_limit} times per minute.\n"
                    "Please try again later."
                )
                
                if update.callback_query:
                    await update.callback_query.answer(error_message, show_alert=True)
                    return None
                elif update.message:
                    await update.message.reply_text(error_message)
                    return None
                return None
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator 