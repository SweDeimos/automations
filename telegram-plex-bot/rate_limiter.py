from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes
import time

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

def rate_limit(command: str):
    """Rate limit decorator for bot commands"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            now = time.time()
            
            # Initialize user's rate limit data if not exists
            if user_id not in rate_limiter.command_history:
                rate_limiter.command_history[user_id] = []
            
            if command not in rate_limiter.command_history[user_id]:
                rate_limiter.command_history[user_id][command] = []
            
            # Clean old timestamps
            rate_limiter.command_history[user_id][command] = [
                ts for ts in rate_limiter.command_history[user_id][command]
                if now - ts < rate_limiter.rate_limits[command][1]
            ]
            
            # Check if user has exceeded rate limit
            if len(rate_limiter.command_history[user_id][command]) >= rate_limiter.rate_limits[command][0]:
                error_message = (
                    "⚠️ You're making too many requests.\n"
                    f"Please wait {rate_limiter.rate_limits[command][1]} seconds before trying again."
                )
                
                # Handle both message and callback query updates
                if update.callback_query:
                    await update.callback_query.answer(error_message, show_alert=True)
                    return
                elif update.message:
                    await update.message.reply_text(error_message)
                    return
                return
            
            # Add current timestamp
            rate_limiter.command_history[user_id][command].append(now)
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator 