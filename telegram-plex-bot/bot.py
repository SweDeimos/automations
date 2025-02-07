import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
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
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Hello! Send me a movie title, and I'll search for a torrent.")
    return MOVIE

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    movie_title = update.message.text.strip()
    logger.info(f"Searching for '{movie_title}'...")

    try:
        torrents = search_tpb(movie_title)
        if torrents:
            top_5_torrents = torrents[:5]
            message = "Found these torrents:\n"
            for idx, torrent in enumerate(top_5_torrents, start=1):
                try:  # Add a try-except block for size conversion
                    size_bytes = int(torrent['size'])  # Convert size to integer here
                    size_mb = size_bytes / (1024 * 1024)
                    size_gb = size_bytes / (1024 * 1024 * 1024)
                    size_str = f"{size_gb:.2f} GB" if size_gb > 1 else f"{size_mb:.2f} MB"
                    message += f"{idx}. {torrent['name']} | Size: {size_str} | Seeds: {torrent.get('seeders', 'N/A')}\n"
                except (ValueError, TypeError) as e:  # Handle conversion errors
                    logger.warning(f"Error converting size for torrent {torrent['name']}: {e}. Size: {torrent.get('size')}")
                    message += f"{idx}. {torrent['name']} | Size: N/A | Seeds: {torrent.get('seeders', 'N/A')}\n"  # Or some default value like "N/A"
            message += "\nType a number to choose a torrent."
            context.user_data["torrent_results"] = top_5_torrents
            await update.message.reply_text(message)
            return SELECT
        else:
            await update.message.reply_text("No torrents found for that title. Please try another one.")
            context.user_data.clear()  # Clear user data
            return MOVIE  # Return to MOVIE state

    except Exception as e:
        logger.error(f"Error during torrent search: {e}")
        await update.message.reply_text("An error occurred during the search. Please try again later.")
        context.user_data.clear() # Clear user data
        return MOVIE # Return to MOVIE state


async def select_torrent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        idx = int(update.message.text) - 1

        torrents = context.user_data.get("torrent_results")

        if torrents and 0 <= idx < len(torrents):
            selected = torrents[idx]
            await update.message.reply_text(f"You selected: {selected['name']}\nAdding torrent to qBittorrent...")

            info_hash = add_torrent(selected)  # Get the info_hash
            if info_hash:
                await update.message.reply_text("Torrent added successfully. Monitoring download...")
                asyncio.create_task(process_torrent(update, context, selected, info_hash))  # Pass info_hash
                return ConversationHandler.END
            else:
                await update.message.reply_text("Failed to add torrent.")
                return ConversationHandler.END

        else:
            await update.message.reply_text("Invalid selection. Please try again.")
            return SELECT

    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number.")
        return SELECT
    except Exception as e:
        logger.error(f"Error during torrent selection or processing: {e}")
        await update.message.reply_text("An error occurred. Please try again.")
        return ConversationHandler.END


async def process_torrent(update: Update, context: ContextTypes.DEFAULT_TYPE, selected: dict, info_hash: str): # Added info_hash parameter
    try:
        download_success = await monitor_download(info_hash)  # Monitor download with info_hash

        if download_success:
            file_path = f"downloads/{selected['name']}"  # Adjust path as needed
            new_path = unpack_download_if_needed(file_path)
            final_path = new_path if new_path else file_path

            plex_message = update_plex_library(final_path)
            await send_notification(update, context, f"Movie '{selected['name']}' is now on Plex. {plex_message}")

        else:
            await update.message.reply_text(f"Download failed for '{selected['name']}'.")
            await send_notification(update, context, f"Download failed for '{selected['name']}'.")

    except Exception as e:
        logger.error(f"Error during download/processing: {e}")
        await update.message.reply_text("An error occurred during download or processing.")
        await send_notification(update, context, f"Error processing movie '{selected['name']}'.")

async def recent_movies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        movies = get_recent_movies(limit=5)
        if movies:
            message = "Last 5 updated movies in Plex:\n"
            for movie in movies:
                # Format the updatedAt timestamp as needed.
                message += f"{movie.title} - Updated at: {movie.updatedAt}\n"
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("No movies found in Plex.")
    except Exception as e:
        logger.error(f"Error fetching recent movies: {e}")
        await update.message.reply_text("Error fetching recent movies.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def update_plex_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received command to update Plex library.")
    """Updates the Plex library and sends a confirmation message."""
    try:
        plex_message = update_plex_library("")  # Pass an empty string or None as file_path if not needed
        await update.message.reply_text(plex_message)
    except Exception as e:
        logger.error(f"Error updating Plex via command: {e}")
        await update.message.reply_text("Error updating Plex. Check logs for details.")

async def recent_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Process the /recent command even if in conversation
    await recent_movies(update, context)
    return ConversationHandler.END

def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MOVIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie)],
            SELECT: [MessageHandler(filters.TEXT, select_torrent)],
        },
        fallbacks=[CommandHandler("cancel", cancel),
                   CommandHandler("recent", recent_fallback)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("recent_movies", recent_movies))
    application.add_handler(CommandHandler("update_plex", update_plex_command))
    application.run_polling()

if __name__ == '__main__':
    main()