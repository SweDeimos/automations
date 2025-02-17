from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        # Store user's command history: {user_id: [(command, timestamp), ...]}
        self.command_history: Dict[int, List[Tuple[str, datetime]]] = {}
        
        # Define rate limits for different commands: {command: (max_calls, time_window_seconds)}
        self.rate_limits = {
            'search_movie': (5, 60),    # 5 searches per minute
            'select_torrent': (3, 60),  # 3 selections per minute
            'recent': (10, 60),         # 10 recent checks per minute
            'history': (10, 60),        # 10 history checks per minute
            'default': (20, 60),        # Default limit for other commands
            'inline_search': (10, 60),  # 10 inline searches per minute
        }
    
    def _clean_old_history(self, user_id: int, command: str) -> None:
        """Remove commands older than the time window"""
        if user_id not in self.command_history:
            return
            
        time_window = self.rate_limits.get(command, self.rate_limits['default'])[1]
        cutoff_time = datetime.now() - timedelta(seconds=time_window)
        
        self.command_history[user_id] = [
            (cmd, timestamp) 
            for cmd, timestamp in self.command_history[user_id] 
            if timestamp > cutoff_time
        ]
    
    def is_rate_limited(self, user_id: int, command: str) -> bool:
        """Check if user has exceeded rate limit for the command"""
        self._clean_old_history(user_id, command)
        
        if user_id not in self.command_history:
            self.command_history[user_id] = []
        
        # Get rate limit settings for the command
        max_calls, time_window = self.rate_limits.get(command, self.rate_limits['default'])
        
        # Count recent commands
        command_count = sum(1 for cmd, _ in self.command_history[user_id] if cmd == command)
        
        # Add current command to history
        self.command_history[user_id].append((command, datetime.now()))
        
        return command_count >= max_calls

# Create a global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(command_name: str):
    """Decorator to apply rate limiting to bot commands"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            if rate_limiter.is_rate_limited(user_id, command_name):
                limit, window = rate_limiter.rate_limits.get(command_name, rate_limiter.rate_limits['default'])
                await update.message.reply_text(
                    f"⚠️ Rate limit exceeded. You can use this command {limit} times per {window} seconds.\n"
                    "Please try again later."
                )
                logger.warning(f"Rate limit exceeded for user {user_id} on command {command_name}")
                return
                
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator 