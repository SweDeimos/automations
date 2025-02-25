# notifier.py
from telegram import Bot, Update
from telegram.ext import ContextTypes
from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_IDS
import logging
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

async def send_notification(
    update: Optional[Update] = None, 
    context: Optional[ContextTypes.DEFAULT_TYPE] = None, 
    message: str = "",
    chat_id: Optional[int] = None,
    parse_mode: str = "HTML"
) -> bool:
    """
    Sends a notification message to a Telegram chat.
    
    Args:
        update: The update object from the handler
        context: The context object from the handler
        message: The message to send
        chat_id: Optional chat ID to send to (if not using update)
        parse_mode: Message parse mode (HTML, Markdown, etc.)
        
    Returns:
        True if the message was sent successfully, False otherwise
    """
    if not message:
        logger.warning("Empty message provided to send_notification")
        return False
        
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Determine chat_id from update if not provided
        if not chat_id and update:
            chat_id = update.effective_chat.id
            
        if not chat_id:
            logger.error("No chat_id provided or available in update")
            return False
            
        await bot.send_message(
            chat_id=chat_id, 
            text=message,
            parse_mode=parse_mode
        )
        logger.debug(f"Notification sent to chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

async def notify_admins(message: str, parse_mode: str = "HTML") -> bool:
    """
    Sends a notification to all admin users.
    
    Args:
        message: The message to send
        parse_mode: Message parse mode (HTML, Markdown, etc.)
        
    Returns:
        True if at least one message was sent successfully, False otherwise
    """
    if not message:
        logger.warning("Empty message provided to notify_admins")
        return False
        
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        success = False
        
        for admin_id in ADMIN_USER_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id, 
                    text=message,
                    parse_mode=parse_mode
                )
                success = True
                logger.debug(f"Admin notification sent to {admin_id}")
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")
                
        return success
    except Exception as e:
        logger.error(f"Error in notify_admins: {e}")
        return False
