import asyncio
import logging
from functools import wraps
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Tuple
from uuid import uuid4
import re
import html
import sys
import os

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)

from config import TELEGRAM_BOT_TOKEN
from downloader import search_tpb, add_torrent, monitor_download, retry_download
from unpacker import unpack_download_if_needed
from plex_uploader import update_plex_library, get_recent_movies
from notifier import send_notification, notify_admins
from rate_limiter import rate_limit
from security import restricted_access, admin_only, check_file_size_limit, security
from user_manager import user_manager, UserRole

# Define conversation states
MOVIE, SELECT, CONFIRM = range(3)

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Set up logging with proper encoding for Windows console
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bot.log", encoding='utf-8'),
    ]
)

# Add console handler with proper encoding
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.info("Bot logging initialized")

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
    """
    Decorator to handle exceptions in async functions.
    Logs the exception and sends an appropriate error message to the user.
    """
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

# --- Helper Functions ---

def format_torrent_message(torrent: Dict[str, Any], idx: int) -> str:
    """Format a single torrent entry for display"""
    try:
        size_bytes = int(torrent.get('size', 0))
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_bytes / (1024 * 1024 * 1024)
        size_str = f"{size_gb:.2f} GB" if size_gb > 1 else f"{size_mb:.2f} MB"
        
        # Include quality score if available
        quality_score = torrent.get('quality_score')
        quality_info = f" | Quality: {quality_score:.1f}/25" if quality_score is not None else ""
        
        return f"{idx}. {torrent.get('name', 'Unknown')} | Size: {size_str} | Seeds: {torrent.get('seeders', 'N/A')}{quality_info}"
    except (ValueError, TypeError) as e:
        logger.warning(f"Error converting size for torrent {torrent.get('name', 'Unknown')}: {e}")
        return f"{idx}. {torrent.get('name', 'Unknown')} | Size: N/A | Seeds: {torrent.get('seeders', 'N/A')}"

def create_torrent_pagination(
    all_results: List[Dict[str, Any]], 
    page: int, 
    items_per_page: int = 5
) -> Tuple[List[Dict[str, Any]], str, InlineKeyboardMarkup]:
    """
    Create pagination for movie torrent results
    
    Args:
        all_results: List of all movie torrent results
        page: Current page number (0-indexed)
        items_per_page: Number of items per page
        
    Returns:
        Tuple of (current_page_items, message_text, reply_markup)
    """
    start_idx = page * items_per_page
    current_page_items = all_results[start_idx:start_idx + items_per_page]
    
    # Create message text
    message = f"Found {len(all_results)} movie torrents (showing {start_idx + 1}-{start_idx + len(current_page_items)}):\n\n"
    for idx, torrent in enumerate(current_page_items, start=1):
        message += format_torrent_message(torrent, idx) + "\n"
    
    # Create selection buttons
    keyboard = [
        [InlineKeyboardButton(f"{idx}. {torrent.get('name', 'Unknown')}", callback_data=f"select_{idx}")]
        for idx, torrent in enumerate(current_page_items, start=1)
    ]
    
    # Add navigation row if there are more results
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
    if (page + 1) * items_per_page < len(all_results):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
    if nav_row:
        keyboard.append(nav_row)
        
    # Add search again button
    keyboard.append([InlineKeyboardButton("🔄 New Search", callback_data="new_search")])
    
    return current_page_items, message, InlineKeyboardMarkup(keyboard)

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

def escape_markdown_v2(text):
    """Escape special characters for Telegram's MarkdownV2 format."""
    if not text:
        return ""
    # Characters that need to be escaped: _ * [ ] ( ) ~ ` > # + - = | { } . !
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

# --- Bot Handlers with Error Handler Decorator ---

@restricted_access()
@async_error_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and register the user if needed"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    # Register user if not exists
    if not user_manager.get_user(user_id):
        user_manager.add_user(user_id, username)
    else:
        user_manager.update_last_active(user_id)
    
    await update.message.reply_text(
        "Hello! Send me a movie title, and I'll search for movie torrents.\n\n"
        "This bot is for movies only and does not support TV series.\n\n"
        "Use /help to see all available commands."
    )
    return MOVIE

@restricted_access()
@rate_limit("search_movie")
@async_error_handler
async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle movie search requests"""
    user = update.effective_user
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
    
    logger.info(f"👤 User {user.username or user.id} searching for '{movie_title}'")
    status_message = await update.message.reply_text("🔍 Searching for movies...")
    
    try:
        if 'search_page' not in context.user_data:
            # New search
            # search_tpb will return torrents ranked by quality score (seeds, size, trusted status)
            torrents = search_tpb(movie_title)
            if not torrents:
                logger.info(f"❌ No torrents found for '{movie_title}'")
                await status_message.edit_text(
                    f"No movie torrents found for '{movie_title}'.\n"
                    "Please try another search term."
                )
                return MOVIE
                
            user_id = update.effective_user.id
            
            # Filter torrents based on user's size limit
            allowed_torrents = [
                torrent for torrent in torrents 
                if user_manager.can_access_file_size(user_id, int(torrent.get('size', 0)))
            ]
            
            if not allowed_torrents:
                logger.info(f"⚠️ User {user.username or user.id} has no torrents within size limit for '{movie_title}'")
                await update.message.reply_text(
                    "No suitable movie torrents found within your size limit.\n"
                    "Try another search or contact an administrator."
                )
                return MOVIE
            
            # Store all results and current page
            context.user_data['all_results'] = allowed_torrents
            context.user_data['search_page'] = 0
            
            logger.info(f"✅ Found {len(allowed_torrents)} torrents for '{movie_title}' within size limits")
        
        # Get current page of results using the pagination helper
        page = context.user_data['search_page']
        all_results = context.user_data['all_results']
        
        current_page_items, message, reply_markup = create_torrent_pagination(all_results, page)
        
        context.user_data["torrent_results"] = current_page_items
        await status_message.edit_text(message, reply_markup=reply_markup)
        return SELECT
    except Exception as e:
        logger.error(f"Error searching for movie: {e}")
        raise  # This will be caught by the error handler decorator

@check_file_size_limit()
@rate_limit("select_torrent")
@async_error_handler
async def select_torrent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle torrent selection from the search results"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "next_page" or query.data == "prev_page":
            # Update page number
            if query.data == "next_page":
                context.user_data['search_page'] += 1
            else:
                context.user_data['search_page'] -= 1
            
            # Get current page of results using the pagination helper
            page = context.user_data['search_page']
            all_results = context.user_data['all_results']
            
            current_page_items, message, reply_markup = create_torrent_pagination(all_results, page)
            
            context.user_data["torrent_results"] = current_page_items
            await query.edit_message_text(message, reply_markup=reply_markup)
            return SELECT
        elif query.data == "new_search":
            # Clear search data and prompt for new search
            context.user_data.pop('search_page', None)
            context.user_data.pop('all_results', None)
            await query.edit_message_text("Please enter a new movie title to search for.")
            return MOVIE
        elif query.data.startswith('select_'):
            # Handle torrent selection
            idx = int(query.data.split('_')[1]) - 1
            return await handle_torrent_selection(update, context, idx)
        elif query.data.startswith('confirm_'):
            return await handle_confirmation(update, context)
            
    except ValueError:
        await query.edit_message_text(
            "Invalid selection.\n"
            "Please select one of the numbered options above."
        )
        return SELECT

@async_error_handler
async def handle_torrent_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int) -> int:
    """Handle torrent selection and show confirmation"""
    query = update.callback_query
    user = update.effective_user
    torrents = context.user_data.get("torrent_results")
    
    if not torrents or not (0 <= idx < len(torrents)):
        await query.edit_message_text("Invalid selection or expired results. Please try again.")
        return SELECT
    
    selected = torrents[idx]
    context.user_data['selected_torrent'] = selected
    
    # Format size in GB
    size_gb = int(selected['size']) / (1024 * 1024 * 1024)
    size_formatted = f"{size_gb:.2f}"
    
    logger.info(f"👤 User {user.username or user.id} selected torrent: {selected['name']} ({size_formatted} GB)")
    
    # Create confirmation message
    safe_name = html.escape(selected['name'])
    confirm_message = (
        f"<b>Confirm download:</b>\n\n<code>{safe_name}</code>\n\nSize: {size_formatted} GB"
    )
    
    # Create keyboard for confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, download", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ No, cancel", callback_data="confirm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(confirm_message, reply_markup=reply_markup, parse_mode='HTML')
    return CONFIRM

@async_error_handler
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation of torrent download"""
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    
    selected = context.user_data.get('selected_torrent')
    if not selected:
        await query.edit_message_text(
            "Session expired. Please start a new search."
        )
        return ConversationHandler.END
        
    if query.data == "confirm_no":
        logger.info(f"👤 User {user.username or user.id} cancelled download of: {selected['name']}")
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
        
        logger.info(f"👤 User {user.username or user.id} confirmed download of: {selected['name']}")
        info_hash = add_torrent(selected)
        
        if info_hash:
            # Mark as downloaded in history
            mark_history_downloaded(
                context,
                selected.get('search_query', ''),
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
            logger.error(f"❌ Failed to add torrent: {selected['name']}")
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
    """Process the torrent download, extraction, and Plex update"""
    user = update.effective_user
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
        
        # Monitor the download with retry capability
        logger.info(f"🔄 Starting download monitoring for {selected['name']} (hash: {info_hash})")
        download_success = await retry_download(info_hash)
        
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
            logger.error(f"❌ Download failed for {selected['name']} (hash: {info_hash})")
            await status_message.edit_text(error_msg)
            await send_notification(update, context, error_msg)
            return

        # Update status for unpacking
        logger.info(f"📦 Processing downloaded files for {selected['name']}")
        await status_message.edit_text("📦 Processing downloaded files...")
        file_path = f"downloads/{selected['name']}"
        new_path = unpack_download_if_needed(file_path)
        final_path = new_path if new_path else file_path

        # Update status for Plex
        logger.info(f"🎬 Adding {selected['name']} to Plex library")
        await status_message.edit_text("🎬 Adding to Plex library...")
        plex_message = update_plex_library(final_path)
        
        # Final success message
        success_message = (
            f"✅ Movie '{selected['name']}' is now on Plex!\n"
            f"{plex_message}"
        )
        logger.info(f"✅ Successfully added {selected['name']} to Plex")
        await status_message.edit_text(success_message)
        await send_notification(update, context, success_message)
        
        # Notify admins about the successful download
        admin_message = (
            f"✅ New movie added to Plex\n"
            f"Title: {selected['name']}\n"
            f"Added by: {user.username or user.id}"
        )
        await notify_admins(admin_message)
        
    except Exception as e:
        logger.error(f"Error processing torrent: {e}")
        if 'status_message' in locals():
            await status_message.edit_text(
                f"❌ An error occurred while processing '{selected['name']}'"
            )
        raise

@async_error_handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current operation"""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

@restricted_access()
@async_error_handler
async def update_plex_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually update the Plex library"""
    logger.info("Received command to update Plex library.")
    await update.message.reply_text("Updating Plex library...")
    plex_message = update_plex_library("")  # Pass an empty string if not needed
    await update.message.reply_text(plex_message)

@async_error_handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information"""
    user_id = update.effective_user.id
    is_admin = security.is_admin(user_id)
    
    help_text = (
        "<b>🎬 Telegram Plex Movie Bot Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/search - Search for a movie (TV series not supported)\n"
        "/recent - Show recently added movies\n"
        "/history - Show your search history\n"
        "/help - Show this help message\n"
    )
    
    # Add admin commands if the user is an admin
    if is_admin:
        admin_help = (
            "\n<b>Admin Commands:</b>\n"
            "/adduser &lt;user_id&gt; [username] - Add a new user by Telegram ID\n"
            "/update_plex - Force update the Plex library\n"
        )
        help_text += admin_help
    
    help_text += (
        "\n<b>How to use:</b>\n"
        "1. Send a movie title to search for movie torrents\n"
        "2. Select from the available movie options (sorted by quality score)\n"
        "3. The bot will download and add it to Plex automatically\n\n"
        "<b>Features:</b>\n"
        "• Smart quality ranking: Torrents are automatically ranked by a quality score\n"
        "• Automatic retry: Failed downloads are retried with exponential backoff\n"
        "• Size filtering: Only shows torrents within your allowed size limit\n\n"
        "The bot will notify you when the movie is ready to watch on Plex.\n\n"
        "<b>Note:</b> This bot is for movies only and does not support TV series."
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

@rate_limit("recent")
@restricted_access()
@async_error_handler
async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recently added movies to Plex"""
    await update.message.reply_text("Fetching recent movies from Plex...")
    
    recent_movies = get_recent_movies(limit=10)
    if not recent_movies:
        await update.message.reply_text("No recent movies found or unable to connect to Plex.")
        return
        
    message = "🎬 *Recently Added Movies* 🎬\n\n"
    for movie in recent_movies:
        title = html.escape(movie.title)
        year = movie.year if hasattr(movie, 'year') else 'N/A'
        added = movie.addedAt.strftime("%Y-%m-%d") if hasattr(movie, 'addedAt') else 'Unknown'
        
        message += f"🎥 <b>{title}</b> ({year})\n"
        message += f"📅 Added: {added}\n\n"
    
    await update.message.reply_text(message, parse_mode='HTML')

@rate_limit("history")
@async_error_handler
@restricted_access()
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show search history"""
    if not context.user_data.get('search_history'):
        await update.message.reply_text("No search history available.")
        return
        
    history = context.user_data['search_history']
    message = "<b>📖 Your Recent Searches</b>\n\n"
    
    for idx, entry in enumerate(reversed(history[-10:]), start=1):  # Show last 10 searches
        query = html.escape(entry['query'])
        timestamp = entry['timestamp'].strftime("%Y-%m-%d %H:%M")
        
        message += f"{idx}. <b>{query}</b>\n📅 {timestamp}\n"
        
        if entry.get('downloaded'):
            torrent_name = entry.get('selected_torrent', {}).get('name', 'Unknown')
            safe_name = html.escape(torrent_name)
            message += f"✅ Downloaded: <code>{safe_name}</code>\n\n"
        else:
            message += f"❌ Not downloaded\n\n"
    
    message += "<i>Use /search_again &lt;number&gt; to repeat a search</i>"
    
    try:
        await update.message.reply_text(message, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        # Fallback to plain text if HTML fails
        plain_message = "Your recent searches:\n\n"
        for idx, entry in enumerate(reversed(history[-10:]), start=1):
            plain_message += f"{idx}. {entry['query']} - {entry['timestamp'].strftime('%Y-%m-%d %H:%M')}\n"
            if entry.get('downloaded'):
                torrent_name = entry.get('selected_torrent', {}).get('name', 'Unknown')
                plain_message += f"✅ Downloaded: {torrent_name}\n\n"
            else:
                plain_message += f"❌ Not downloaded\n\n"
        await update.message.reply_text(plain_message)

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

@async_error_handler
@admin_only()
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new user to the bot by their Telegram ID. Admin only command."""
    user_id = update.effective_user.id
    logger.info(f"Admin {user_id} is attempting to add a new user")
    
    # Check if the command has the correct format
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ Please provide the Telegram user ID to add.\n"
            "Usage: /adduser <user_id> [username]"
        )
        return
    
    try:
        # Parse the user ID from the first argument
        new_user_id = int(context.args[0])
        
        # Get username if provided, otherwise use "Unknown"
        username = context.args[1] if len(context.args) > 1 else "Unknown"
        
        # Add the user
        user = user_manager.add_user(new_user_id, username, UserRole.USER)
        
        await update.message.reply_text(
            f"✅ User added successfully!\n"
            f"ID: {new_user_id}\n"
            f"Username: {username}\n"
            f"Role: {user.role.value}\n"
            f"Max file size: {user.max_file_size / (1024**3):.2f} GB"
        )
        
        logger.info(f"Admin {user_id} added new user {new_user_id} ({username})")
    except ValueError:
        await update.message.reply_text("⚠️ Invalid user ID. Please provide a valid numeric Telegram ID.")
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text(f"❌ Error adding user: {str(e)}")

def main() -> None:
    """Initialize and start the bot"""
    # Initialize bot with token
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Create conversation handler for the main flow
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("search_again", search_again_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie),
        ],
        states={
            MOVIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie)],
            SELECT: [CallbackQueryHandler(select_torrent_callback)],
            CONFIRM: [CallbackQueryHandler(handle_confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("update_plex", update_plex_command))
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("adduser", add_user_command))

    # Start the bot with proper error handling
    try:
        logger.info("🚀 Starting Telegram Plex Bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()