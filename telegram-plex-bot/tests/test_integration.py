import asyncio
import os
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
import logging
from datetime import datetime

from telegram import Update, Message, Chat, User, CallbackQuery
from telegram.ext import ContextTypes, ConversationHandler

# Import all major components
from bot import (
    start, search_movie, select_torrent_callback, handle_confirmation,
    process_torrent, cancel, update_plex_command, help_command,
    history_command, search_again_command, MOVIE, SELECT, CONFIRM
)
from downloader import search_tpb, add_torrent, monitor_download
from unpacker import unpack_download_if_needed
from plex_uploader import update_plex_library, get_recent_movies
from user_manager import user_manager, UserRole
from rate_limiter import rate_limit
from security import restricted_access, admin_only, check_file_size_limit

# Disable logging during tests
logging.disable(logging.CRITICAL)

# Helper function to create mock objects
async def create_mock_update_context(message_text=None, callback_data=None, user_id=123, username="testuser"):
    update = Mock(spec=Update)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot = AsyncMock()
    
    # Mock user info
    user = Mock(spec=User)
    user.id = user_id
    user.username = username
    user.first_name = "Test"
    user.last_name = "User"
    
    chat = Mock(spec=Chat)
    chat.id = user_id
    
    # Set effective user
    update.effective_user = user
    update.effective_chat = chat
    
    if message_text is not None:
        # Mock message
        message = Mock(spec=Message)
        message.text = message_text
        message.chat = chat
        message.from_user = user
        message.reply_text = AsyncMock()
        message.reply_html = AsyncMock()
        message.edit_text = AsyncMock()
        update.message = message
        update.callback_query = None
    
    if callback_data is not None:
        # Mock callback query
        query = Mock(spec=CallbackQuery)
        query.data = callback_data
        query.message = Mock(spec=Message)
        query.message.chat = chat
        query.message.reply_text = AsyncMock()
        query.message.reply_html = AsyncMock()
        query.message.edit_text = AsyncMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        update.message = None
    
    return update, context

class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

@pytest_asyncio.fixture
async def cleanup_tasks():
    # Setup - store existing tasks
    existing_tasks = set(asyncio.all_tasks())
    
    yield
    
    # Cleanup - cancel any tasks created during the test
    current_tasks = set(asyncio.all_tasks())
    new_tasks = current_tasks - existing_tasks
    
    for task in new_tasks:
        if not task.done():
            task.cancel()
    
    if new_tasks:
        await asyncio.gather(*new_tasks, return_exceptions=True)

# Test user authentication and registration
@pytest.mark.asyncio
@patch('bot.user_manager.get_user')
@patch('bot.user_manager.add_user')
@patch('bot.user_manager.update_last_active')
async def test_start_command(mock_update_last_active, mock_add_user, mock_get_user):
    # Test new user
    mock_get_user.return_value = None
    update, context = await create_mock_update_context(message_text="/start")
    
    result = await start(update, context)
    
    assert result == MOVIE
    mock_add_user.assert_called_once()
    mock_update_last_active.assert_not_called()
    update.message.reply_text.assert_called_once()
    
    # Test existing user
    mock_get_user.return_value = {"id": 123, "username": "testuser", "role": "user"}
    mock_add_user.reset_mock()
    update, context = await create_mock_update_context(message_text="/start")
    
    result = await start(update, context)
    
    assert result == MOVIE
    mock_add_user.assert_not_called()
    mock_update_last_active.assert_called_once()
    update.message.reply_text.assert_called()

# Test movie search functionality
@pytest.mark.asyncio
@patch('bot.search_tpb')
async def test_search_movie(mock_search_tpb):
    # Setup mock search results
    mock_results = [
        {"title": "Test Movie 1", "size": "1.2 GB", "seeders": 100, "leechers": 10},
        {"title": "Test Movie 2", "size": "2.3 GB", "seeders": 50, "leechers": 5}
    ]
    mock_search_tpb.return_value = mock_results
    
    # Test with valid search query
    update, context = await create_mock_update_context(message_text="Inception")
    
    result = await search_movie(update, context)
    
    assert result == SELECT
    mock_search_tpb.assert_called_with("Inception")
    update.message.reply_text.assert_called()
    assert context.user_data.get("search_results") == mock_results
    
    # Test with empty search query
    update, context = await create_mock_update_context(message_text="")
    
    result = await search_movie(update, context)
    
    assert result == MOVIE
    update.message.reply_text.assert_called()

# Test torrent selection
@pytest.mark.asyncio
async def test_select_torrent():
    # Setup mock data
    search_results = [
        {"title": "Test Movie 1", "size": "1.2 GB", "seeders": 100, "leechers": 10, "info_hash": "hash1"},
        {"title": "Test Movie 2", "size": "2.3 GB", "seeders": 50, "leechers": 5, "info_hash": "hash2"}
    ]
    
    update, context = await create_mock_update_context(callback_data="select_0")
    context.user_data["search_results"] = search_results
    context.user_data["search_query"] = "Test Movie"
    
    with patch('bot.handle_torrent_selection', new_callable=AsyncMock) as mock_handle_selection:
        mock_handle_selection.return_value = CONFIRM
        
        result = await select_torrent_callback(update, context)
        
        assert result == CONFIRM
        mock_handle_selection.assert_called_with(update, context, 0)
        update.callback_query.answer.assert_called_once()

# Test confirmation handling
@pytest.mark.asyncio
async def test_handle_confirmation():
    update, context = await create_mock_update_context(callback_data="confirm")
    context.user_data["selected_torrent"] = {"title": "Test Movie", "info_hash": "hash123"}
    
    with patch('bot.process_torrent', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = None
        
        result = await handle_confirmation(update, context)
        
        assert result == ConversationHandler.END
        mock_process.assert_called_with(update, context, context.user_data["selected_torrent"], "hash123")
        update.callback_query.answer.assert_called_once()

# Test torrent processing
@pytest.mark.asyncio
@patch('bot.add_torrent')
@patch('bot.monitor_download')
@patch('bot.unpack_download_if_needed')
@patch('bot.update_plex_library')
@patch('bot.asyncio.create_task')
async def test_process_torrent_flow(mock_create_task, mock_update_plex, mock_unpack, mock_monitor, mock_add_torrent, cleanup_tasks):
    update, context = await create_mock_update_context()
    context.bot.send_message = AsyncMock()
    selected_torrent = {"title": "Test Movie", "info_hash": "hash123"}
    
    # Mock successful download
    mock_add_torrent.return_value = "hash123"
    mock_monitor.return_value = {"status": "completed", "path": "/downloads/test_movie"}
    mock_unpack.return_value = "/extracted/test_movie"
    mock_update_plex.return_value = True
    
    # Mock the create_task function to return a mock task
    mock_task = Mock()
    mock_task.done = Mock(return_value=False)
    mock_task.cancel = Mock()
    mock_create_task.return_value = mock_task
    
    await process_torrent(update, context, selected_torrent, "hash123")
    
    mock_add_torrent.assert_called_once()
    mock_monitor.assert_called_once()
    mock_unpack.assert_called_once()
    mock_update_plex.assert_called_once()

# Test Plex update command
@pytest.mark.asyncio
@patch('bot.update_plex_library')
async def test_update_plex_command(mock_update_plex):
    update, context = await create_mock_update_context(message_text="/update_plex")
    mock_update_plex.return_value = True
    
    await update_plex_command(update, context)
    
    mock_update_plex.assert_called_once()
    update.message.reply_text.assert_called()

# Test history command
@pytest.mark.asyncio
async def test_history_command_with_data():
    update, context = await create_mock_update_context(message_text="/history")
    context.user_data["search_history"] = [
        {"query": "Inception", "timestamp": datetime.now(), "selected": {"title": "Inception (2010)"}},
        {"query": "Matrix", "timestamp": datetime.now()}
    ]
    
    await history_command(update, context)
    
    update.message.reply_text.assert_called()

# Test search again command
@pytest.mark.asyncio
async def test_search_again_command():
    update, context = await create_mock_update_context(message_text="/search_again")
    
    result = await search_again_command(update, context)
    
    assert result == MOVIE
    update.message.reply_text.assert_called()

# Test cancel command
@pytest.mark.asyncio
async def test_cancel_command():
    update, context = await create_mock_update_context(message_text="/cancel")
    
    result = await cancel(update, context)
    
    assert result == ConversationHandler.END
    update.message.reply_text.assert_called()

# Test help command
@pytest.mark.asyncio
async def test_help_command():
    update, context = await create_mock_update_context(message_text="/help")
    
    await help_command(update, context)
    
    update.message.reply_text.assert_called()

# Test rate limiter
@pytest.mark.asyncio
@patch('rate_limiter.rate_limit')
async def test_rate_limiter(mock_rate_limit):
    # This is a simple test to ensure the rate limiter decorator is applied
    # A more comprehensive test would be in test_rate_limiter.py
    assert hasattr(search_movie, '__wrapped__')
    assert hasattr(select_torrent_callback, '__wrapped__')
    assert hasattr(history_command, '__wrapped__')

# Test security restrictions
@pytest.mark.asyncio
@patch('security.restricted_access')
async def test_security_restrictions(mock_restricted):
    # This is a simple test to ensure the security decorator is applied
    # A more comprehensive test would be in test_security.py
    assert hasattr(start, '__wrapped__')
    assert hasattr(search_movie, '__wrapped__')
    assert hasattr(update_plex_command, '__wrapped__') 