import pytest
from unittest.mock import Mock, AsyncMock
from telegram import Update, Message, User
from telegram.ext import ContextTypes
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from security import SecurityManager, restricted_access
from config import ALLOWED_USER_IDS

@pytest.fixture
def security_manager():
    return SecurityManager([123, 456])  # Test user IDs

def test_is_user_allowed(security_manager):
    assert security_manager.is_user_allowed(123) is True
    assert security_manager.is_user_allowed(789) is False

@pytest.mark.asyncio
async def test_restricted_access_allowed():
    @restricted_access()
    async def test_func(update, context):
        return "success"
    
    # Mock allowed user
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = ALLOWED_USER_IDS[0]
    update.message = AsyncMock()
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    result = await test_func(update, context)
    assert result == "success"
    update.message.reply_text.assert_not_called()

@pytest.mark.asyncio
async def test_restricted_access_denied():
    @restricted_access()
    async def test_func(update, context):
        return "success"
    
    # Mock unauthorized user
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 999999  # Unauthorized ID
    update.message = AsyncMock()
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    result = await test_func(update, context)
    assert result is None
    update.message.reply_text.assert_called_once()
    assert "not authorized" in update.message.reply_text.call_args[0][0] 