import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from telegram import Update, Message, User
from telegram.ext import ContextTypes
from rate_limiter import RateLimiter, rate_limit
from unittest.mock import patch

DEFAULT_RATE_LIMIT = (20, 60)  # 20 calls per 60 seconds

@pytest.fixture
def rate_limiter() -> RateLimiter:
    return RateLimiter()

@pytest.fixture
def mock_update() -> Update:
    update = Mock(spec=Update)
    user = Mock(spec=User)
    user.id = 123
    update.effective_user = user
    message = Mock(spec=Message)
    message.reply_text = AsyncMock()
    update.message = message
    return update

@pytest.mark.asyncio
async def test_rate_limit_not_exceeded(rate_limiter, mock_update):
    @rate_limit("test_command")
    async def test_func(update, context):
        return "success"
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    result = await test_func(mock_update, context)
    assert result == "success"
    mock_update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_rate_limit_exceeded(rate_limiter, mock_update):
    # Create a test command with a very low limit
    rate_limiter.rate_limits["test_command"] = (1, 60)  # 1 call per minute
    
    @rate_limit("test_command")
    async def test_func(update, context):
        return "success"
    
    # Patch the global rate_limiter in the rate_limit module
    with patch('rate_limiter.rate_limiter', rate_limiter):
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # First call should succeed
        result = await test_func(mock_update, context)
        assert result == "success"
        
        # Second call should trigger rate limit
        result = await test_func(mock_update, context)
        
        # Verify rate limit message
        mock_update.message.reply_text.assert_called_once_with(
            f"⚠️ Rate limit exceeded. You can use this command 1 times per 60 seconds.\n"
            "Please try again later."
        )

@pytest.mark.asyncio
async def test_rate_limit_cleanup(rate_limiter):
    user_id = 123
    command = "test_command"
    
    # Add old command history
    old_time = datetime.now() - timedelta(seconds=61)  # Just over the default window
    rate_limiter.command_history[user_id] = [(command, old_time)]
    
    # Clean up old history
    rate_limiter._clean_old_history(user_id, command)
    
    assert len(rate_limiter.command_history[user_id]) == 0

def test_different_commands_separate_limits(rate_limiter):
    user_id = 123
    
    # Add history for different commands
    rate_limiter.command_history[user_id] = [
        ("cmd1", datetime.now()),
        ("cmd2", datetime.now()),
    ]
    
    assert not rate_limiter.is_rate_limited(user_id, "cmd1")
    assert not rate_limiter.is_rate_limited(user_id, "cmd2") 