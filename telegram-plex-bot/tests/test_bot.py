import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Import handlers from your bot module.
from bot import start, search_movie, cancel, select_torrent_callback

# --- Dummy Classes to Simulate Telegram Objects ---

class DummyMessage:
    def __init__(self, text=None, chat_id="test_chat"):
        self.text = text
        self.chat_id = chat_id
        self.sent_messages = []

    async def reply_text(self, text, **kwargs):
        self.sent_messages.append(text)

class DummyCallbackQuery:
    def __init__(self, data, message):
        self.data = data
        self.message = message

    async def answer(self):
        # Simulate acknowledging the callback.
        pass

    async def edit_message_text(self, text, **kwargs):
        # Simulate editing the original message.
        self.message.sent_messages.append(text)

class DummyBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append(text)

class DummyUpdate:
    def __init__(self, message=None, callback_query=None):
        self.message = message
        self.callback_query = callback_query

class DummyContext:
    def __init__(self):
        self.user_data = {}
        self.bot = DummyBot()

# --- Test Cases ---

@pytest.mark.asyncio
async def test_start_handler():
    """Test that the start handler sends the welcome message and returns the correct state."""
    dummy_message = DummyMessage()
    update = DummyUpdate(message=dummy_message)
    context = DummyContext()

    state = await start(update, context)
    # The start handler should return MOVIE (typically 0)
    assert state == 0
    # Check if a welcome message is sent.
    assert any("Hello!" in msg for msg in dummy_message.sent_messages)

@pytest.mark.asyncio
async def test_cancel_handler():
    """Test that the cancel handler sends the cancellation message and returns ConversationHandler.END."""
    dummy_message = DummyMessage()
    update = DummyUpdate(message=dummy_message)
    context = DummyContext()

    state = await cancel(update, context)
    # Check that the cancellation message is sent.
    assert any("Operation cancelled" in msg for msg in dummy_message.sent_messages)
    # Optionally, if you rely on ConversationHandler.END, check state. For now, we assume it returns a value.

@pytest.mark.asyncio
async def test_search_movie_handler():
    """Test that search_movie calls search_tpb and sends the torrent results message."""
    dummy_message = DummyMessage(text="Fake Movie Title")
    update = DummyUpdate(message=dummy_message)
    context = DummyContext()

    # Create a fake torrent list.
    fake_torrents = [
        {"name": "Torrent 1", "size": "104857600", "seeders": "50", "info_hash": "hash1", "magnet": "magnet:?xt=urn:btih:hash1"},
        {"name": "Torrent 2", "size": "209715200", "seeders": "100", "info_hash": "hash2", "magnet": "magnet:?xt=urn:btih:hash2"},
    ]
    with patch("bot.search_tpb", return_value=fake_torrents):
        state = await search_movie(update, context)
        # search_movie should return the SELECT state (typically 1)
        assert state == 1
        # Check that a message with torrent details was sent.
        assert any("Found these torrents" in msg for msg in dummy_message.sent_messages)
        # Verify that the user_data was updated.
        assert "torrent_results" in context.user_data
        assert len(context.user_data["torrent_results"]) == len(fake_torrents[:5])

@pytest.mark.asyncio
async def test_select_torrent_callback_handler():
    """Test that select_torrent_callback processes a valid selection correctly."""
    # Prepare a dummy message and callback query with chat_id defined.
    dummy_message = DummyMessage(chat_id="test_chat")
    callback_query = DummyCallbackQuery(data="1", message=dummy_message)
    update = DummyUpdate(callback_query=callback_query)
    context = DummyContext()
    context.bot = DummyBot()
    # Pre-populate user_data with one fake torrent.
    fake_torrents = [
        {"name": "Torrent 1", "size": "104857600", "seeders": "50", "info_hash": "hash1", "magnet": "magnet:?xt=urn:btih:hash1"}
    ]
    context.user_data["torrent_results"] = fake_torrents

    # Patch add_torrent to simulate a successful addition.
    with patch("bot.add_torrent", return_value="hash1"):
        # Patch asyncio.create_task so we can verify it is called.
        with patch("bot.asyncio.create_task") as mock_create_task:
            state = await select_torrent_callback(update, context)
            # Verify that a task was scheduled to process the torrent.
            mock_create_task.assert_called_once()
            # Verify that a success message was sent via bot.send_message.
            assert any("Torrent added successfully" in msg for msg in context.bot.sent_messages)
            # Verify that the handler returns ConversationHandler.END.
            assert state == -1



