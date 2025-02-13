import asyncio
import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, Message, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, InlineQuery
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    InlineQueryHandler,
)
from config import TELEGRAM_BOT_TOKEN  # Make sure this is correctly configured
from downloader import search_tpb, add_torrent, monitor_download
from unpacker import unpack_download_if_needed
from plex_uploader import update_plex_library, get_recent_movies
from notifier import send_notification
import json
from datetime import datetime
from typing import Dict, List
from rate_limiter import rate_limit
from uuid import uuid4
from security import restricted_access

# Define conversation states
MOVIE, SELECT, CONFIRM, HISTORY_SELECT, FEEDBACK = range(5)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define specific error messages based on the function and error type
error_messages = {
    "default": "An unexpected error occurred. Please try again later.",
    "search_movie": {
        "ConnectionError": "Unable to connect to torrent site. Please try again later.",
        "TimeoutError": "Search request timed out. Please try again.",
        "default": "Failed to search for movies. Please try again later."
    },
    "select_torrent": {
        "ValueError": "Invalid selection. Please choose a number from the list.",
        "KeyError": "Selected torrent information is no longer available. Please search again.",
        "default": "Failed to process your selection. Please try again."
    },
    "process_torrent": {
        "IOError": "Failed to save the downloaded file. Please try again.",
        "default": "Failed to process the download. Please try another torrent."
    },
}

# --- Error Handler Decorator ---
def async_error_handler(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.exception(f"Async error in {func.__name__}: {e}")
            
            # Get function-specific error messages or default ones
            func_errors = error_messages.get(func.__name__, {})
            error_msg = func_errors.get(type(e).__name__, error_messages["default"])
            
            # Send error message to user
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.message.reply_text(error_msg)
            
            # For conversation handlers, return to initial state
            if func.__name__ in ["search_movie", "select_torrent"]:
                return MOVIE
            
    return wrapper

# --- Bot Handlers with Error Handler Decorator ---

@restricted_access()
@async_error_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Hello! Send me a movie title, and I'll search for a torrent.\n\n"
        "Use /help to see all available commands."
    )
    return MOVIE

@restricted_access()
@rate_limit("search_movie")
@async_error_handler
async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    movie_title = update.message.text.strip()
    if not movie_title:
        await update.message.reply_text("Please provide a movie title to search for.")
        return MOVIE
    
    # Add to search history
    add_to_search_history(context, movie_title)
    
    # Show typing indicator while searching
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    logger.info(f"Searching for '{movie_title}'...")
    status_message = await update.message.reply_text("🔍 Searching for torrents...")
    
    try:
        torrents = search_tpb(movie_title)
        # Edit the status message with results
        await status_message.edit_text(f"Found {len(torrents) if torrents else 0} results for '{movie_title}'")
        
        if not torrents:
            await update.message.reply_text(
                "No torrents found for that title.\n"
                "Tips:\n"
                "• Check for typos in the movie title\n"
                "• Try using the original title\n"
                "• Remove special characters\n"
                "Please try another search."
            )
            context.user_data.clear()
            return MOVIE
            
        top_5_torrents = torrents[:5]
        message = "Found these torrents:\n"
        for idx, torrent in enumerate(top_5_torrents, start=1):
            try:
                size_bytes = int(torrent.get('size', 0))  # Use get() with default value
                size_mb = size_bytes / (1024 * 1024)
                size_gb = size_bytes / (1024 * 1024 * 1024)
                size_str = f"{size_gb:.2f} GB" if size_gb > 1 else f"{size_mb:.2f} MB"
                message += f"{idx}. {torrent.get('name', 'Unknown')} | Size: {size_str} | Seeds: {torrent.get('seeders', 'N/A')}\n"
            except (ValueError, TypeError) as e:
                logger.warning(f"Error converting size for torrent {torrent.get('name', 'Unknown')}: {e}. Size: {torrent.get('size')}")
                message += f"{idx}. {torrent.get('name', 'Unknown')} | Size: N/A | Seeds: {torrent.get('seeders', 'N/A')}\n"
        message += "\nType a number to choose a torrent."

        # Create inline keyboard buttons with numbers
        keyboard = [
            [InlineKeyboardButton(f"{idx}. {torrent.get('name', 'Unknown')}", callback_data=str(idx))]
            for idx, torrent in enumerate(top_5_torrents, start=1)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["torrent_results"] = top_5_torrents
        await update.message.reply_text(message, reply_markup=reply_markup)
        return SELECT
    except Exception as e:
        logger.error(f"Error searching for movie: {e}")
        raise  # This will be caught by the error handler decorator

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

@rate_limit("select_torrent")
@async_error_handler
async def select_torrent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    try:
        # Check if this is a confirmation response
        if query.data.startswith('confirm_'):
            return await handle_confirmation(update, context)
            
        idx = int(query.data) - 1
    except ValueError:
        await query.edit_message_text(
            "Invalid selection format.\n"
            "Please select one of the numbered options above."
        )
        return SELECT

    torrents = context.user_data.get("torrent_results")
    if not torrents:
        await query.edit_message_text(
            "Search results expired.\n"
            "Please start a new search with /start"
        )
        return ConversationHandler.END
        
    if not (0 <= idx < len(torrents)):
        await query.edit_message_text(
            "Invalid selection number.\n"
            "Please select one of the available options."
        )
        return SELECT

    selected = torrents[idx]
    
    # Store the selected torrent in user_data for confirmation
    context.user_data['selected_torrent'] = selected
    
    # Create confirmation message with details
    size_bytes = int(selected.get('size', 0))
    size_gb = size_bytes / (1024 * 1024 * 1024)
    safe_name = selected['name'].replace('-', '\\-').replace('.', '\\.').replace('_', '\\_')
    confirm_message = (
        f"📽 *Confirm Download*\n\n"
        f"*Title:* `{safe_name}`\n"
        f"*Size:* `{size_gb:.2f} GB`\n"
        f"*Seeders:* `{selected.get('seeders', 'N/A')}`\n\n"
        "Are you sure you want to download this torrent?"
    )
    
    # Create confirmation buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, download it", callback_data=f"confirm_yes"),
            InlineKeyboardButton("❌ No, cancel", callback_data=f"confirm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        confirm_message,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )
    
    return CONFIRM

@async_error_handler
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    selected = context.user_data.get('selected_torrent')
    if not selected:
        await query.edit_message_text(
            "Session expired. Please start a new search."
        )
        return ConversationHandler.END
        
    if query.data == "confirm_no":
        await query.edit_message_text(
            "Download cancelled.\n"
            "You can search for another movie or select a different option."
        )
        return MOVIE
        
    if query.data == "confirm_yes":
        # Show loading state
        await query.edit_message_text(
            f"⚙️ Starting download process for:\n"
            f"`{selected['name']}`\n\n"
            "Connecting to qBittorrent...",
            parse_mode='Markdown'
        )
        
        logger.info(f"Confirmed torrent download: {selected['name']}")
        info_hash = add_torrent(selected)
        
        if info_hash:
            # Mark as downloaded in history
            mark_history_downloaded(
                context,
                selected.get('search_query', ''),  # We'll add this below
                selected
            )
            
            await query.edit_message_text(
                f"✅ Torrent added successfully!\n\n"
                f"Movie: `{selected['name']}`\n"
                f"Status: Monitoring download...",
                parse_mode='Markdown'
            )
            asyncio.create_task(process_torrent(update, context, selected, info_hash))
        else:
            await query.edit_message_text(
                f"❌ Failed to add torrent.\n\n"
                f"Movie: `{selected['name']}`\n"
                f"Please try again or choose another torrent.",
                parse_mode='Markdown'
            )
        return ConversationHandler.END
        
    return CONFIRM

@async_error_handler
async def process_torrent(update: Update, context: ContextTypes.DEFAULT_TYPE, selected: dict, info_hash: str):
    try:
        # Store the status message in context for updating
        status_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ Initializing download..."
        )
        
        # Update progress periodically
        async def update_progress():
            progress_indicators = ["⏳", "⌛"]
            i = 0
            while True:
                try:
                    await status_message.edit_text(
                        f"{progress_indicators[i]} Downloading: {selected['name']}\n"
                        "Please wait..."
                    )
                    i = (i + 1) % 2
                    await asyncio.sleep(3)
                except Exception:
                    break

        # Start progress updates in background
        progress_task = asyncio.create_task(update_progress())
        
        # Monitor the download
        download_success = await monitor_download(info_hash)
        
        # Cancel progress updates
        progress_task.cancel()
        
        if not download_success:
            error_msg = (
                f"❌ Download failed for '{selected['name']}'.\n"
                "Possible reasons:\n"
                "• No active seeders\n"
                "• Network connection issues\n"
                "• Insufficient disk space\n"
                "Please try another torrent or search again."
            )
            await status_message.edit_text(error_msg)
            await send_notification(update, context, error_msg)
            return

        # Update status for unpacking
        await status_message.edit_text("📦 Processing downloaded files...")
        file_path = f"downloads/{selected['name']}"
        new_path = unpack_download_if_needed(file_path)
        final_path = new_path if new_path else file_path

        # Update status for Plex
        await status_message.edit_text("🎬 Adding to Plex library...")
        plex_message = update_plex_library(final_path)
        
        # Final success message
        success_message = (
            f"✅ Movie '{selected['name']}' is now on Plex!\n"
            f"{plex_message}"
        )
        await status_message.edit_text(success_message)
        await send_notification(update, context, success_message)
        
        # Request feedback after a short delay
        await asyncio.sleep(2)  # Give user time to read success message
        await request_feedback(update, context)
        
    except Exception as e:
        logger.error(f"Error processing torrent: {e}")
        if 'status_message' in locals():
            await status_message.edit_text(
                f"❌ An error occurred while processing '{selected['name']}'"
            )
        raise

@rate_limit("recent")
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

@async_error_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "🎬 *Movie Download Bot Help* 🎬\n\n"
        "*Available Commands:*\n"
        "/start \\- Start the bot and search for movies\n"
        "/help \\- Show this help message\n"
        "/recent \\- Show recently added movies to Plex\n"
        "/history \\- View your recent searches\n"
        "/search\\_again \\<number\\> \\- Repeat a previous search\n"
        "/cancel \\- Cancel current operation\n\n"
        "*How to use:*\n"
        "1\\. Send a movie title to search for torrents\n"
        "2\\. Select from the available options\n"
        "3\\. The bot will download and add it to Plex automatically\n\n"
        "The bot will notify you when the movie is ready to watch on Plex\\."
    )
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')

@rate_limit("history")
@async_error_handler
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's search and download history"""
    if not context.user_data.get('search_history'):
        await update.message.reply_text(
            "No search history found\\.\n"
            "Start searching for movies with /start"
        )
        return

    # Get search history
    history = context.user_data['search_history']
    message = "🕒 *Your Recent Searches*\n\n"
    
    for idx, entry in enumerate(reversed(history[-10:]), 1):  # Show last 10 searches
        timestamp = entry['timestamp'].strftime("%Y-%m-%d %H:%M")
        status = "✅" if entry.get('downloaded') else "🔍"
        # Escape special characters in query and names
        safe_query = entry['query'].replace('-', '\\-').replace('.', '\\.').replace('_', '\\_')
        message += (
            f"{idx}\\. {status} `{safe_query}`\n"
            f"    📅 {timestamp}\n"
        )
        if entry.get('selected_torrent'):
            safe_name = entry['selected_torrent']['name'].replace('-', '\\-').replace('.', '\\.').replace('_', '\\_')
            message += f"    📥 Selected: `{safe_name}`\n"
        message += "\n"
    
    message += "\nUse /search\\_again \\<number\\> to repeat a search"
    
    await update.message.reply_text(message, parse_mode='MarkdownV2')

@async_error_handler
async def search_again_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Repeat a previous search"""
    try:
        # Extract the history index from command
        args = context.args
        if not args:
            raise ValueError("No search number provided")
            
        idx = int(args[0]) - 1
        history = context.user_data.get('search_history', [])
        
        if not history or idx < 0 or idx >= len(history[-10:]):
            await update.message.reply_text(
                "Invalid search number.\n"
                "Use /history to see available searches."
            )
            return ConversationHandler.END
            
        # Get the search query from history
        search_entry = list(reversed(history[-10:]))[idx]
        query = search_entry['query']
        
        # Perform the search again
        await update.message.reply_text(f"🔄 Repeating search: '{query}'")
        
        # Reuse the search_movie function with a mock message
        mock_update = Update(update.update_id, message=Message(
            message_id=update.message.message_id,
            date=datetime.now(),
            chat=update.message.chat,
            text=query,
            from_user=update.message.from_user
        ))
        return await search_movie(mock_update, context)
        
    except ValueError:
        await update.message.reply_text(
            "Please provide a valid search number.\n"
            "Example: /search_again 1"
        )
        return ConversationHandler.END

def add_to_search_history(context: ContextTypes.DEFAULT_TYPE, query: str, selected_torrent: Dict = None):
    """Add a search to the user's history"""
    if 'search_history' not in context.user_data:
        context.user_data['search_history'] = []
        
    # Add new search entry
    entry = {
        'query': query,
        'timestamp': datetime.now(),
        'selected_torrent': selected_torrent,
        'downloaded': False
    }
    
    history = context.user_data['search_history']
    history.append(entry)
    
    # Keep only last 50 searches
    if len(history) > 50:
        context.user_data['search_history'] = history[-50:]

def mark_history_downloaded(context: ContextTypes.DEFAULT_TYPE, query: str, torrent: Dict):
    """Mark a search history entry as downloaded"""
    if 'search_history' not in context.user_data:
        return
        
    history = context.user_data['search_history']
    # Find the most recent matching search
    for entry in reversed(history):
        if entry['query'] == query and not entry['downloaded']:
            entry['downloaded'] = True
            entry['selected_torrent'] = torrent
            break

@async_error_handler
async def request_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Request user feedback after successful download"""
    keyboard = [
        [
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rate_5"),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rate_4"),
        ],
        [
            InlineKeyboardButton("⭐⭐⭐", callback_data="rate_3"),
            InlineKeyboardButton("⭐⭐", callback_data="rate_2"),
            InlineKeyboardButton("⭐", callback_data="rate_1"),
        ],
        [
            InlineKeyboardButton("Skip ➡️", callback_data="rate_skip")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "How was your experience? Please rate the download:\n"
        "(This helps us improve the service)",
        reply_markup=reply_markup
    )
    return FEEDBACK

@rate_limit("feedback")
@async_error_handler
async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's feedback response"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "rate_skip":
        await query.edit_message_text(
            "Thanks for using the bot! Let me know if you need anything else."
        )
        return ConversationHandler.END
        
    rating = int(query.data.split('_')[1])
    
    # Store the rating in user_data
    if 'feedback_history' not in context.user_data:
        context.user_data['feedback_history'] = []
    
    feedback_entry = {
        'timestamp': datetime.now(),
        'rating': rating,
        'movie': context.user_data.get('selected_torrent', {}).get('name', 'Unknown')
    }
    
    context.user_data['feedback_history'].append(feedback_entry)
    
    # For low ratings, ask what went wrong
    if rating <= 3:
        keyboard = [
            [InlineKeyboardButton(reason, callback_data=f"reason_{i}")]
            for i, reason in enumerate([
                "Download too slow",
                "Quality issues",
                "Wrong movie",
                "Other issues"
            ])
        ]
        keyboard.append([InlineKeyboardButton("Skip ➡️", callback_data="reason_skip")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Thanks for your {rating}⭐ rating.\n"
            "Could you tell us what went wrong?",
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            f"Thanks for your {rating}⭐ rating!\n"
            "Let me know if you need anything else."
        )
    
    return ConversationHandler.END

@async_error_handler
async def feedback_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show feedback history for admins"""
    # You might want to add admin check here
    if not context.user_data.get('feedback_history'):
        await update.message.reply_text(
            "No feedback history available."
        )
        return
        
    history = context.user_data['feedback_history']
    message = "📊 *Recent Feedback History*\n\n"
    
    for entry in reversed(history[-10:]):  # Show last 10 feedbacks
        stars = "⭐" * entry['rating']
        movie_name = entry['movie'].replace('-', '\\-').replace('.', '\\.').replace('_', '\\_')
        timestamp = entry['timestamp'].strftime("%Y-%m-%d %H:%M")
        
        message += (
            f"Movie: `{movie_name}`\n"
            f"Rating: {stars}\n"
            f"Date: {timestamp}\n"
            f"{'Reason: ' + entry.get('reason', 'Not provided') if entry.get('reason') else ''}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='MarkdownV2')

@restricted_access()
@rate_limit("inline_search")
@async_error_handler
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries for movie searches"""
    query = update.inline_query.query
    
    if len(query) < 3:
        # Don't search for very short queries
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Enter at least 3 characters",
                input_message_content=InputTextMessageContent(
                    "Please enter at least 3 characters to search for movies."
                ),
                description="Type more to search..."
            )
        ]
    else:
        try:
            # Search for torrents
            torrents = search_tpb(query)[:5]  # Limit to top 5 results
            
            results = []
            for torrent in torrents:
                # Format size
                size_bytes = int(torrent.get('size', 0))
                size_gb = size_bytes / (1024 * 1024 * 1024)
                size_str = f"{size_gb:.2f} GB"
                
                # Create result article
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title=torrent.get('name', 'Unknown'),
                        description=f"💾 {size_str} | 🌱 {torrent.get('seeders', 'N/A')} seeders",
                        input_message_content=InputTextMessageContent(
                            f"🎬 *{torrent.get('name', 'Unknown')}*\n"
                            f"💾 Size: `{size_str}`\n"
                            f"🌱 Seeders: `{torrent.get('seeders', 'N/A')}`\n\n"
                            "Use /start to download this movie",
                            parse_mode='MarkdownV2'
                        ),
                        thumb_url="https://example.com/movie-icon.png",  # Add a movie icon
                    )
                )
            
            if not results:
                results = [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="No results found",
                        input_message_content=InputTextMessageContent(
                            f"No torrents found for '{query}'"
                        ),
                        description="Try a different search term"
                    )
                ]
        
        except Exception as e:
            logger.error(f"Error in inline search: {e}")
            results = [
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="Error occurred",
                    input_message_content=InputTextMessageContent(
                        "Sorry, an error occurred while searching. Please try again later."
                    ),
                    description="Search failed"
                )
            ]
    
    await update.inline_query.answer(results, cache_time=300)

def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("search_again", search_again_command)
        ],
        states={
            MOVIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie)],
            SELECT: [CallbackQueryHandler(select_torrent_callback)],
            CONFIRM: [CallbackQueryHandler(select_torrent_callback)],
            FEEDBACK: [CallbackQueryHandler(handle_feedback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("recent", recent_movies))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("feedback", feedback_history_command))
    application.add_handler(InlineQueryHandler(inline_search))
    application.run_polling()

if __name__ == '__main__':
    main()
