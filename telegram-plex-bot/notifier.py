# notifier.py
from telegram import Bot
from config import TELEGRAM_BOT_TOKEN
import logging

logger = logging.getLogger(__name__) # Get logger instance

async def send_notification(update, context, message: str):
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        chat_id = update.effective_chat.id
        await bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error(f"Error sending notification: {e}") # Log the error
