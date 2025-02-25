import asyncio
import pytest
from unittest.mock import Mock, patch
from telegram import Update, Message, Chat, User, CallbackQuery, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot import (
    help_command, search_movie, select_torrent_callback, process_torrent,
    handle_confirmation, history_command, search_again_command,
    MOVIE, SELECT, CONFIRM
)
from datetime import datetime
import pytest_asyncio

# Helper function to create mock Update and Context objects
async def create_mock_update_context(message_text=None, callback_data=None):
    update = Mock(spec=Update)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.bot = AsyncMock()
    
    # Mock user info
    user = Mock(spec=User)
    user.id = 123
    chat = Mock(spec=Chat)
    chat.id = 123
    
    if message_text is not None:
        # Mock message
        message = Mock(spec=Message)
        message.text = message_text
        message.chat = chat
        message.from_user = user
        message.reply_text = AsyncMock()
        update.message = message
        update.callback_query = None
        update.effective_chat = chat
    
    if callback_data is not None:
        # Mock callback query
        query = Mock(spec=CallbackQuery)
        query.data = callback_data
        query.message = Mock(spec=Message)
        query.message.chat = chat
        query.message.reply_text = AsyncMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        update.message = None
        update.effective_chat = chat
    
    return update, context

# Helper class for mocking async methods
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

# Add this fixture
@pytest_asyncio.fixture
async def cleanup_tasks():
    tasks = []
    yield tasks
    # Cleanup all tasks after test
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

# Test cases
@pytest.mark.asyncio
async def test_help_command():
    update, context = await create_mock_update_context(message_text="/help")
    await help_command(update, context)
    
    # Verify help message was sent
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "Movie Download Bot Help" in args[0]
    assert kwargs.get("parse_mode") == "MarkdownV2"

@pytest.mark.asyncio
async def test_search_movie_empty_title():
    update, context = await create_mock_update_context(message_text="")
    result = await search_movie(update, context)
    
    # Verify error message for empty title
    update.message.reply_text.assert_called_once_with("Please provide a movie title to search for.")
    assert result == MOVIE

@pytest.mark.asyncio
@patch('bot.search_tpb')
async def test_search_movie_no_results(mock_search):
    mock_search.return_value = []
    update, context = await create_mock_update_context(message_text="Nonexistent Movie")
    status_message = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_message)
    
    result = await search_movie(update, context)
    
    # Get the last call's arguments
    last_message = update.message.reply_text.call_args_list[-1][0][0]
    assert "No suitable torrents found" in last_message
    assert result == MOVIE

@pytest.mark.asyncio
@patch('bot.search_tpb')
async def test_search_movie_connection_error(mock_search):
    mock_search.side_effect = ConnectionError("Failed to connect")
    update, context = await create_mock_update_context(message_text="Movie Title")
    status_message = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_message)
    
    await search_movie(update, context)
    
    # Get the last error message
    last_message = update.message.reply_text.call_args_list[-1][0][0]
    assert "Unable to connect to torrent site" in last_message

@pytest.mark.asyncio
async def test_select_torrent_callback_expired():
    update, context = await create_mock_update_context(callback_data="1")
    context.user_data = {}  # Empty user data to simulate expired results
    
    result = await select_torrent_callback(update, context)
    
    # Verify expired results message
    args, _ = update.callback_query.edit_message_text.call_args
    assert "Invalid selection" in args[0]
    assert result == SELECT

@pytest.mark.asyncio
async def test_torrent_confirmation_flow():
    update, context = await create_mock_update_context(callback_data="confirm_yes")
    context.user_data["selected_torrent"] = {
        'name': 'Test Movie',
        'size': '1073741824',
        'seeders': '10'
    }
    
    with patch('bot.add_torrent') as mock_add_torrent, \
         patch('asyncio.create_task') as mock_create_task:  # Add this to prevent task creation
        mock_add_torrent.return_value = "fake_hash"
        result = await handle_confirmation(update, context)
        
        # Get all messages sent
        messages = [call[0][0] for call in update.callback_query.edit_message_text.call_args_list]
        # Verify that one of the messages contains our expected text
        assert any("Starting download process" in msg for msg in messages)
        assert result == ConversationHandler.END

@pytest.mark.asyncio
async def test_search_with_loading_indicator():
    update, context = await create_mock_update_context(message_text="Test Movie")
    context.bot = AsyncMock()
    context.bot.send_chat_action = AsyncMock()
    
    # Mock the status message
    status_message = AsyncMock()
    status_message.edit_text = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_message)
    
    # Create a mock progress task
    async def mock_progress():
        return None
    progress_task = asyncio.create_task(mock_progress())
    
    with patch('bot.search_tpb') as mock_search, \
         patch('asyncio.create_task', return_value=progress_task), \
         patch('asyncio.sleep', new_callable=AsyncMock), \
         patch('bot.process_torrent', new_callable=AsyncMock):
        
        mock_search.return_value = [{'name': 'Test Movie', 'size': '1073741824', 'seeders': '10'}]
        
        try:
            result = await search_movie(update, context)
            
            # Verify loading indicators
            context.bot.send_chat_action.assert_called_once()
            status_message.edit_text.assert_called_with("Found 1 results for 'Test Movie'")
        finally:
            # Clean up the task
            if not progress_task.done():
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass

@pytest.mark.asyncio
async def test_download_progress_updates():
    update, context = await create_mock_update_context(callback_data="confirm_yes")
    status_message = AsyncMock()
    context.bot.send_message = AsyncMock(return_value=status_message)
    
    selected = {'name': 'Test Movie'}
    info_hash = 'fake_hash'
    
    # Create a mock progress task that we can control
    async def mock_progress():
        return None
    progress_task = asyncio.create_task(mock_progress())
    
    with patch('bot.monitor_download') as mock_monitor, \
         patch('bot.unpack_download_if_needed') as mock_unpack, \
         patch('bot.update_plex_library') as mock_plex, \
         patch('asyncio.sleep', new_callable=AsyncMock), \
         patch('asyncio.create_task', return_value=progress_task):
        
        mock_monitor.return_value = True
        mock_unpack.return_value = None
        mock_plex.return_value = "Plex updated successfully"
        
        # Run the process_torrent function
        await process_torrent(update, context, selected, info_hash)
        
        # Verify the messages
        calls = [call[0][0] for call in status_message.edit_text.call_args_list]
        assert any("Processing downloaded files" in msg for msg in calls)
        assert any("Adding to Plex library" in msg for msg in calls)
        assert any("now on Plex" in msg for msg in calls)
        
        # Clean up the task
        if not progress_task.done():
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

@pytest.mark.asyncio
async def test_search_history():
    update, context = await create_mock_update_context(message_text="Test Movie")
    
    # Perform a search
    await search_movie(update, context)
    
    # Verify history was created
    assert 'search_history' in context.user_data
    assert len(context.user_data['search_history']) == 1
    assert context.user_data['search_history'][0]['query'] == "Test Movie"

@pytest.mark.asyncio
async def test_history_command_empty():
    update, context = await create_mock_update_context(message_text="/history")
    
    await history_command(update, context)
    
    # Verify empty history message
    args, _ = update.message.reply_text.call_args
    assert "No search history available" in args[0]

@pytest.mark.asyncio
async def test_history_command():
    update, context = await create_mock_update_context(message_text="/history")
    
    # Add test history
    context.user_data['search_history'] = [
        {
            'timestamp': datetime.now(),
            'query': 'Test Movie',
            'downloaded': True,
            'selected_torrent': {'name': 'Test Movie HD'}
        }
    ]
    
    await history_command(update, context)
    
    # Verify history display
    args, kwargs = update.message.reply_text.call_args
    assert "Your Recent Searches" in args[0]
    assert "Test Movie" in args[0]
    assert kwargs.get('parse_mode') == 'MarkdownV2'

@pytest.mark.asyncio
async def test_search_again_command():
    update, context = await create_mock_update_context(message_text="/search_again")
    
    # Add some test history
    context.user_data['search_history'] = [
        {
            'query': 'Test Movie',
            'timestamp': datetime.now(),
            'downloaded': False
        }
    ]
    
    with patch('bot.search_movie') as mock_search:
        mock_search.return_value = MOVIE
        result = await search_again_command(update, context)
        
        # Verify search was repeated
        mock_search.assert_called_once()
        assert "Repeating search" in update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_process_torrent(cleanup_tasks):
    update, context = await create_mock_update_context(callback_data="confirm_yes")
    context.bot = AsyncMock()
    status_message = AsyncMock()
    context.bot.send_message = AsyncMock(return_value=status_message)
    
    selected = {'name': 'Test Movie'}
    info_hash = 'fake_hash'
    
    # Create a mock progress task
    async def mock_progress():
        return None
    progress_task = asyncio.create_task(mock_progress())
    cleanup_tasks.append(progress_task)  # Add to cleanup list
    
    with patch('bot.monitor_download') as mock_monitor, \
         patch('bot.unpack_download_if_needed') as mock_unpack, \
         patch('bot.update_plex_library') as mock_plex, \
         patch('bot.send_notification', new_callable=AsyncMock) as mock_notify, \
         patch('asyncio.sleep', new_callable=AsyncMock), \
         patch('asyncio.create_task', return_value=progress_task):
        
        mock_monitor.return_value = True
        mock_unpack.return_value = None
        mock_plex.return_value = "Plex updated successfully"
        
        # Start processing with timeout
        try:
            await asyncio.wait_for(
                process_torrent(update, context, selected, info_hash),
                timeout=5.0  # 5 second timeout
            )
        except asyncio.TimeoutError:
            pytest.fail("Test timed out")

if __name__ == "__main__":
    pytest.main([__file__]) 