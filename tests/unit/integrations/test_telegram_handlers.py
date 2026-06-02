"""
Unit tests for Telegram handlers.
"""

import sys
from pathlib import Path
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


@pytest.mark.asyncio
class TestCmdStart:
    """Test /start command handler."""

    async def test_cmd_start_handles_none_greeting(self):
        """Test that cmd_start handles None greeting gracefully."""
        from integrations.telegram.handlers import cmd_start

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.from_user.username = "testuser"
        mock_message.answer = AsyncMock()

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.start_session = AsyncMock(return_value=None)

        # Patch check_and_handle_prescreening to return False
        with patch("integrations.telegram.handlers.check_and_handle_prescreening", AsyncMock(return_value=False)):
            await cmd_start(mock_message, mock_dialogue_service)

        # Should send fallback message, not crash
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert call_args is not None
        assert isinstance(call_args, str)

    async def test_cmd_start_sends_greeting_when_provided(self):
        """Test that cmd_start sends greeting when provided."""
        from integrations.telegram.handlers import cmd_start

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.from_user.username = "testuser"
        mock_message.answer = AsyncMock()

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.start_session = AsyncMock(return_value="Hello, User!")

        with patch("integrations.telegram.handlers.check_and_handle_prescreening", AsyncMock(return_value=False)):
            await cmd_start(mock_message, mock_dialogue_service)

        mock_message.answer.assert_called_once_with("Hello, User!")


@pytest.mark.asyncio
class TestCmdAnket:
    """Test /anket command handler."""

    async def test_cmd_anket_shows_profile(self):
        """Test that /anket shows user profile."""
        from integrations.telegram.handlers import cmd_anket

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.answer = AsyncMock()

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.get_user_anket = AsyncMock(return_value="📋 Ваша анкета\n\nИмя: Test")

        with patch("integrations.telegram.handlers.check_and_handle_prescreening", AsyncMock(return_value=False)):
            await cmd_anket(mock_message, mock_dialogue_service)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "📋" in call_args[0][0] or "Ваша анкета" in call_args[0][0]
        # Should include reply markup with edit button
        assert "reply_markup" in call_args[1]

    async def test_cmd_anket_triggers_prescreening_when_needed(self):
        """Test that /anket triggers prescreening when user hasn't completed it."""
        from integrations.telegram.handlers import cmd_anket

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.answer = AsyncMock()

        mock_dialogue_service = MagicMock()

        with patch("integrations.telegram.handlers.check_and_handle_prescreening", AsyncMock(return_value=True)):
            await cmd_anket(mock_message, mock_dialogue_service)

        # Should not call get_user_anket when prescreening is triggered
        mock_dialogue_service.get_user_anket.assert_not_called()


@pytest.mark.asyncio
class TestHandleMessage:
    """Test message handler."""

    async def test_handle_message_unified_guard_blocks_incomplete_user(self):
        """Test that unified guard blocks messages from user with incomplete prescreening."""
        from contextlib import asynccontextmanager
        from integrations.telegram.handlers import handle_message

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.text = "Hello"

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.process_message = AsyncMock()

        mock_account = MagicMock()
        mock_account.id = 42

        @asynccontextmanager
        async def fake_session():
            yield MagicMock()

        with patch("integrations.telegram.handlers.is_in_prescreening", return_value=False):
            with patch(
                "integrations.telegram.handlers.get_db_session",
                lambda: fake_session(),
            ):
                with patch("db.repositories.AccountRepository") as AR:
                    with patch("db.repositories.TherapistPreferenceRepository") as TR:
                        AR.return_value.get_by_telegram_id = AsyncMock(
                            return_value=mock_account
                        )
                        TR.return_value.is_prescreening_complete = AsyncMock(
                            return_value=False
                        )
                        with patch(
                            "integrations.telegram.handlers.start_prescreening",
                            AsyncMock(),
                        ) as mock_start_prescreening:
                            await handle_message(mock_message, mock_dialogue_service)
                            mock_start_prescreening.assert_called_once()
                            mock_dialogue_service.process_message.assert_not_called()

    async def test_handle_message_allows_complete_user(self):
        """Test that messages from complete user are processed normally."""
        from contextlib import asynccontextmanager
        from integrations.telegram.handlers import handle_message

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.text = "Hello"
        mock_message.answer = AsyncMock()

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.process_message = AsyncMock(
            return_value={
                "response": "Hi there!",
                "session_ended": False,
            }
        )

        mock_account = MagicMock()
        mock_account.id = 42

        @asynccontextmanager
        async def fake_session():
            yield MagicMock()

        with patch("integrations.telegram.handlers.is_in_prescreening", return_value=False):
            with patch(
                "integrations.telegram.handlers.get_db_session",
                lambda: fake_session(),
            ):
                with patch("db.repositories.AccountRepository") as AR:
                    with patch("db.repositories.TherapistPreferenceRepository") as TR:
                        AR.return_value.get_by_telegram_id = AsyncMock(
                            return_value=mock_account
                        )
                        TR.return_value.is_prescreening_complete = AsyncMock(
                            return_value=True
                        )
                        with patch(
                            "integrations.telegram.handlers.start_prescreening",
                            AsyncMock(),
                        ) as mock_start_prescreening:
                            await handle_message(mock_message, mock_dialogue_service)
                            mock_start_prescreening.assert_not_called()
                            mock_dialogue_service.process_message.assert_called_once()


@pytest.mark.asyncio
class TestCmdReset:
    """Test /reset command handler."""

    async def test_cmd_reset_sends_initial_message_with_button(self):
        """Test that /reset sends initial message with reset button."""
        from integrations.telegram.handlers import cmd_reset

        mock_message = MagicMock()
        mock_message.from_user.id = 12345
        mock_message.answer = AsyncMock()

        mock_dialogue_service = MagicMock()

        await cmd_reset(mock_message, mock_dialogue_service)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        # Check message text contains reset description
        assert "Сброс данных" in call_args[0][0]
        # Check reply markup is present
        assert "reply_markup" in call_args[1]


@pytest.mark.asyncio
class TestResetCallbacks:
    """Test reset confirmation callbacks."""

    async def test_on_reset_confirm_open_edits_message_to_confirmation(self):
        """Test that confirm_open callback edits message to show Yes/No buttons."""
        from integrations.telegram.handlers import on_reset_confirm_open

        mock_callback = MagicMock()
        mock_callback.from_user.id = 12345
        mock_callback.data = "reset:confirm_open"
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        await on_reset_confirm_open(mock_callback)

        # Should edit message to show confirmation warning
        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        # Check for confirmation text
        assert "уверены" in call_args[0][0] or "необратимо" in call_args[0][0]
        # Check reply markup has Yes/No buttons
        assert "reply_markup" in call_args[1]
        mock_callback.answer.assert_called_once()

    async def test_on_reset_confirm_no_edits_message_to_cancelled(self):
        """Test that No button edits message to show cancellation."""
        from integrations.telegram.handlers import on_reset_confirm_no

        mock_callback = MagicMock()
        mock_callback.from_user.id = 12345
        mock_callback.data = "reset:confirm_no"
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        await on_reset_confirm_no(mock_callback)

        mock_callback.message.edit_text.assert_called_once()
        call_args = mock_callback.message.edit_text.call_args
        # Check for cancellation message
        assert "Отменено" in call_args[0][0] or "не удалены" in call_args[0][0]
        mock_callback.answer.assert_called_once_with("Отменено")

    async def test_on_reset_confirm_yes_deletes_user_data_and_clears_prescreening(self):
        """Test that Yes button deletes data and clears prescreening state."""
        from integrations.telegram.handlers import on_reset_confirm_yes

        mock_callback = MagicMock()
        mock_callback.from_user.id = 12345
        mock_callback.data = "reset:confirm_yes"
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.reset_user_data = AsyncMock(return_value=True)

        with patch("integrations.telegram.prescreening.clear_prescreening_state") as mock_clear:
            await on_reset_confirm_yes(mock_callback, mock_dialogue_service)

            # Should clear prescreening state
            mock_clear.assert_called_once_with(12345)
            # Should call reset_user_data
            mock_dialogue_service.reset_user_data.assert_awaited_once_with(telegram_id=12345)
            # Should edit message to show success
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            assert "удалены" in call_args[0][0] or "start" in call_args[0][0].lower()
            mock_callback.answer.assert_called_once_with("Готово")

    async def test_on_reset_confirm_yes_shows_not_found_when_no_data(self):
        """Test that Yes button shows appropriate message when user not found."""
        from integrations.telegram.handlers import on_reset_confirm_yes

        mock_callback = MagicMock()
        mock_callback.from_user.id = 12345
        mock_callback.data = "reset:confirm_yes"
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_dialogue_service = MagicMock()
        mock_dialogue_service.reset_user_data = AsyncMock(return_value=False)

        with patch("integrations.telegram.prescreening.clear_prescreening_state"):
            await on_reset_confirm_yes(mock_callback, mock_dialogue_service)

            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            # Should show "no data" or "not found" message
            assert "не найдены" in call_args[0][0] or "не существовали" in call_args[0][0] or "start" in call_args[0][0].lower()
