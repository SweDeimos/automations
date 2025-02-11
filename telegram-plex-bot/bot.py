import asyncio
import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
from config import TELEGRAM_BOT_TOKEN  # Make sure this is correctly configured
from downloader import search_tpb, add_torrent, monitor_download
from unpacker import unpack_download_if_needed
from plex_uploader import update_plex_library, get_recent_movies
from notifier import send_notification
import json

# Define conversation states
MOVIE, SELECT = range(2)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Error Handler Decorator ---
def async_error_handler(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.exception(f"Async error in {func.__name__}: {e}")
            # Attempt to send error message to user, if possible.
            if update.message:
                await update.message.reply_text("An error occurred. Please try again later.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("An error occurred. Please try again later.")
    return wrapper

# --- Bot Handlers with Error Handler Decorator ---

@async_error_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Hello! Send me a movie title, and I'll search for a torrent.")
    return MOVIE

@async_error_handler
async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    movie_title = update.message.text.strip()
    logger.info(f"Searching for '{movie_title}'...")
    await update.message.reply_text(f"Searching for torrents for '{movie_title}' ...")
    
    torrents = search_tpb(movie_title)
    if torrents:
        top_5_torrents = torrents[:5]
        message = "Found these torrents:\n"
        for idx, torrent in enumerate(top_5_torrents, start=1):
            try:
                size_bytes = int(torrent['size'])  # Convert size to integer
                size_mb = size_bytes / (1024 * 1024)
                size_gb = size_bytes / (1024 * 1024 * 1024)
                size_str = f"{size_gb:.2f} GB" if size_gb > 1 else f"{size_mb:.2f} MB"
                message += f"{idx}. {torrent['name']} | Size: {size_str} | Seeds: {torrent.get('seeders', 'N/A')}\n"
            except (ValueError, TypeError) as e:
                logger.warning(f"Error converting size for torrent {torrent['name']}: {e}. Size: {torrent.get('size')}")
                message += f"{idx}. {torrent['name']} | Size: N/A | Seeds: {torrent.get('seeders', 'N/A')}\n"
        message += "\nType a number to choose a torrent."

        # Create inline keyboard buttons with numbers
        keyboard = [
            [InlineKeyboardButton(f"{idx}. {torrent['name']}", callback_data=str(idx))]
            for idx, torrent in enumerate(top_5_torrents, start=1)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["torrent_results"] = top_5_torrents
        await update.message.reply_text(message, reply_markup=reply_markup)
        return SELECT
    else:
        await update.message.reply_text("No torrents found for that title. Please try another one.")
        context.user_data.clear()
        return MOVIE

@async_error_handler
async def select_torrent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # In case of text-based selection (if used)
    try:
        idx = int(update.message.text) - 1
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
        return SELECT

    torrents = context.user_data.get("torrent_results")
    if torrents and 0 <= idx < len(torrents):
        selected = torrents[idx]
        await update.message.reply_text(
            f"You selected: {selected['name']}\nAdding torrent to qBittorrent..."
        )
        info_hash = add_torrent(selected)
        if info_hash:
            await update.message.reply_text("Torrent added successfully. Monitoring download...")
            asyncio.create_task(process_torrent(update, context, selected, info_hash))
            return ConversationHandler.END
        else:
            await update.message.reply_text("Failed to add torrent.")
            return ConversationHandler.END
    else:
        await update.message.reply_text("Invalid selection. Please try again.")
        return SELECT

@async_error_handler
async def select_torrent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # Acknowledge the callback query
    selection = query.data  # This will be the number as a string
    try:
        idx = int(selection) - 1
    except ValueError:
        await query.edit_message_text("Invalid selection. Please try again.")
        return SELECT

    torrents = context.user_data.get("torrent_results")
    if torrents and 0 <= idx < len(torrents):
        selected = torrents[idx]
        await query.edit_message_text(
            f"You selected: {selected['name']}\nAdding torrent to qBittorrent..."
        )
        logger.info(f"Selected torrent: {selected['name']}")
        info_hash = add_torrent(selected)
        if info_hash:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Torrent added successfully. Monitoring download..."
            )
            asyncio.create_task(process_torrent(update, context, selected, info_hash))
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Failed to add torrent."
            )
        return ConversationHandler.END
    else:
        await query.edit_message_text("Invalid selection. Please try again.")
        return SELECT

@async_error_handler
async def process_torrent(update: Update, context: ContextTypes.DEFAULT_TYPE, selected: dict, info_hash: str):
    download_success = await monitor_download(info_hash)
    if download_success:
        file_path = f"downloads/{selected['name']}"  # Adjust path as needed
        new_path = unpack_download_if_needed(file_path)
        final_path = new_path if new_path else file_path

        plex_message = update_plex_library(final_path)
        await send_notification(update, context, f"Movie '{selected['name']}' is now on Plex. {plex_message}")
    else:
        await update.message.reply_text(f"Download failed for '{selected['name']}'.")
        await send_notification(update, context, f"Download failed for '{selected['name']}'.")
        await update.message.reply_text("You can search for another movie by sending its title:")

@async_error_handler
async def recent_movies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    movies = get_recent_movies(limit=5)
    if movies:
        message = "Last 5 updated movies in Plex:\n"
        for movie in movies:
            message += f"{movie.title} - Updated at: {movie.updatedAt}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("No movies found in Plex.")

@async_error_handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

@async_error_handler
async def update_plex_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received command to update Plex library.")
    plex_message = update_plex_library("")  # Pass an empty string if not needed
    await update.message.reply_text(plex_message)

@async_error_handler
async def recent_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await recent_movies(update, context)
    return ConversationHandler.END

def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MOVIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie)],
            SELECT: [CallbackQueryHandler(select_torrent_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("recent", recent_movies))
    application.run_polling()

if __name__ == '__main__':
    main()
