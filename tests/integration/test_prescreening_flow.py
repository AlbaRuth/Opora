"""
Integration tests for prescreening flow.
Tests the complete prescreening wizard in Telegram.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.telegram.prescreening import (
    PrescreeningState,
    get_prescreening_state,
    set_prescreening_state,
    clear_prescreening_state,
    is_in_prescreening,
    handle_prescreening_text,
    build_skip_keyboard,
    build_gender_keyboard,
    build_traits_keyboard,
    THERAPIST_TRAITS,
    DEFAULT_THERAPIST_NAME,
    DEFAULT_THERAPIST_GENDER,
)


class TestPrescreeningState:
    """Test PrescreeningState dataclass."""

    def test_default_state(self):
        """Test default prescreening state."""
        state = PrescreeningState()

        assert state.step == "awaiting_therapist_name"
        assert state.therapist_name == DEFAULT_THERAPIST_NAME
        assert state.therapist_gender == DEFAULT_THERAPIST_GENDER
        assert state.patient_name == ""
        assert state.patient_age is None
        assert state.selected_traits == []

    def test_custom_state(self):
        """Test prescreening state with custom values."""
        state = PrescreeningState(
            step="awaiting_traits_selection",
            therapist_name="Доктор",
            therapist_gender="male",
            patient_name="Иван",
            patient_age=30,
            selected_traits=["calm", "empathetic"],
        )

        assert state.step == "awaiting_traits_selection"
        assert state.therapist_name == "Доктор"
        assert state.therapist_gender == "male"
        assert state.patient_name == "Иван"
        assert state.patient_age == 30
        assert state.selected_traits == ["calm", "empathetic"]


class TestPrescreeningStorage:
    """Test in-memory prescreening state storage."""

    def test_set_and_get_state(self):
        """Test setting and getting prescreening state."""
        user_id = 12345
        state = PrescreeningState(therapist_name="Тест")

        set_prescreening_state(user_id, state)
        retrieved = get_prescreening_state(user_id)

        assert retrieved is not None
        assert retrieved.therapist_name == "Тест"

    def test_clear_state(self):
        """Test clearing prescreening state."""
        user_id = 12345
        state = PrescreeningState()

        set_prescreening_state(user_id, state)
        assert is_in_prescreening(user_id) is True

        clear_prescreening_state(user_id)
        assert is_in_prescreening(user_id) is False
        assert get_prescreening_state(user_id) is None

    def test_is_in_prescreening_false(self):
        """Test is_in_prescreening returns False for unknown user."""
        assert is_in_prescreening(99999) is False


class TestKeyboardBuilders:
    """Test keyboard builders."""

    def test_build_skip_keyboard(self):
        """Test skip keyboard has correct button."""
        keyboard = build_skip_keyboard()

        assert len(keyboard.inline_keyboard) == 1
        assert keyboard.inline_keyboard[0][0].text == "Пропустить"
        assert keyboard.inline_keyboard[0][0].callback_data == "prescreen:skip_name"

    def test_build_gender_keyboard(self):
        """Test gender keyboard has correct buttons."""
        keyboard = build_gender_keyboard()

        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2
        assert keyboard.inline_keyboard[0][0].text == "Мужской"
        assert keyboard.inline_keyboard[0][0].callback_data == "prescreen:gender:male"
        assert keyboard.inline_keyboard[0][1].text == "Женский"
        assert keyboard.inline_keyboard[0][1].callback_data == "prescreen:gender:female"

    def test_build_traits_keyboard_empty(self):
        """Test traits keyboard without selections."""
        keyboard = build_traits_keyboard([])

        # Should have one button per trait, no Done button
        assert len(keyboard.inline_keyboard) == len(THERAPIST_TRAITS)

        # Check first trait button
        first_button = keyboard.inline_keyboard[0][0]
        assert "⬜ " in first_button.text or "✅ " in first_button.text
        assert first_button.callback_data.startswith("prescreen:trait:")

    def test_build_traits_keyboard_with_selections(self):
        """Test traits keyboard with some selections."""
        selected = ["calm", "empathetic"]
        keyboard = build_traits_keyboard(selected)

        # Should have trait buttons + Done button
        assert len(keyboard.inline_keyboard) == len(THERAPIST_TRAITS) + 1

        # Check Done button is last
        last_row = keyboard.inline_keyboard[-1]
        assert len(last_row) == 1
        assert "Готово" in last_row[0].text
        assert last_row[0].callback_data == "prescreen:traits_done"


@pytest.mark.asyncio
class TestPrescreeningTextHandling:
    """Test handling text input during prescreening."""

    async def test_handle_therapist_name_step(self):
        """Test handling therapist name input."""
        from aiogram.types import Message, User as TgUser

        # Create mock message
        mock_user = MagicMock(spec=TgUser)
        mock_user.id = 12345

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.text = "Доктор Анна"
        mock_message.answer = AsyncMock()

        # Set up state
        state = PrescreeningState()
        set_prescreening_state(12345, state)

        # Handle text
        result = await handle_prescreening_text(mock_message)

        assert result is True
        assert state.therapist_name == "Доктор Анна"
        assert state.step == "awaiting_therapist_gender"
        mock_message.answer.assert_called_once()

    async def test_handle_patient_name_step_empty(self):
        """Test handling empty patient name."""
        from aiogram.types import Message, User as TgUser

        mock_user = MagicMock(spec=TgUser)
        mock_user.id = 12345

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.text = "   "
        mock_message.answer = AsyncMock()

        # Set up state at patient name step
        state = PrescreeningState(step="awaiting_patient_name")
        set_prescreening_state(12345, state)

        # Handle text
        result = await handle_prescreening_text(mock_message)

        assert result is True
        # Should stay on same step
        assert state.step == "awaiting_patient_name"
        # Should show error
        call_args = mock_message.answer.call_args[0][0]
        assert "введите" in call_args.lower() or "пожалуйста" in call_args.lower()

    async def test_handle_patient_age_step_valid(self):
        """Test handling valid age input."""
        from aiogram.types import Message, User as TgUser

        mock_user = MagicMock(spec=TgUser)
        mock_user.id = 12345

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.text = "25"
        mock_message.answer = AsyncMock()
        mock_message.edit_reply_markup = AsyncMock()

        # Set up state at age step
        state = PrescreeningState(
            step="awaiting_patient_age",
            therapist_name="Доктор",
            therapist_gender="female",
            patient_name="Иван",
        )
        set_prescreening_state(12345, state)

        # Handle text
        result = await handle_prescreening_text(mock_message)

        assert result is True
        assert state.patient_age == 25
        assert state.step == "awaiting_patient_sex"

    async def test_handle_patient_age_step_invalid(self):
        """Test handling invalid age input."""
        from aiogram.types import Message, User as TgUser

        mock_user = MagicMock(spec=TgUser)
        mock_user.id = 12345

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.text = "abc"
        mock_message.answer = AsyncMock()

        # Set up state at age step
        state = PrescreeningState(step="awaiting_patient_age")
        set_prescreening_state(12345, state)

        # Handle text
        result = await handle_prescreening_text(mock_message)

        assert result is True
        # Should stay on same step
        assert state.step == "awaiting_patient_age"
        # Should show error
        call_args = mock_message.answer.call_args[0][0]
        assert "корректный" in call_args.lower() or "возраст" in call_args.lower()

    async def test_handle_patient_age_step_out_of_range(self):
        """Test handling out of range age."""
        from aiogram.types import Message, User as TgUser

        mock_user = MagicMock(spec=TgUser)
        mock_user.id = 12345

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.text = "150"
        mock_message.answer = AsyncMock()

        # Set up state at age step
        state = PrescreeningState(step="awaiting_patient_age")
        set_prescreening_state(12345, state)

        # Handle text
        result = await handle_prescreening_text(mock_message)

        assert result is True
        # Should stay on same step (invalid age)
        assert state.step == "awaiting_patient_age"

    async def test_handle_not_in_prescreening(self):
        """Test handling when not in prescreening."""
        from aiogram.types import Message, User as TgUser

        uid = 770770
        clear_prescreening_state(uid)

        mock_user = MagicMock(spec=TgUser)
        mock_user.id = uid

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = mock_user
        mock_message.text = "Hello"
        mock_message.answer = AsyncMock()

        result = await handle_prescreening_text(mock_message)

        assert result is False
        mock_message.answer.assert_not_called()


class TestPrescreeningConstants:
    """Test prescreening constants."""

    def test_therapist_traits_defined(self):
        """Test that therapist traits are defined."""
        assert len(THERAPIST_TRAITS) >= 4

        # Check format
        for trait_id, trait_label in THERAPIST_TRAITS:
            assert isinstance(trait_id, str)
            assert isinstance(trait_label, str)
            assert len(trait_id) > 0
            assert len(trait_label) > 0

    def test_default_therapist_name(self):
        """Test default therapist name."""
        assert DEFAULT_THERAPIST_NAME == "Опора"

    def test_default_therapist_gender(self):
        """Test default therapist gender."""
        assert DEFAULT_THERAPIST_GENDER == "female"

    def test_trait_ids_unique(self):
        """Test that trait IDs are unique."""
        trait_ids = [tid for tid, _ in THERAPIST_TRAITS]
        assert len(trait_ids) == len(set(trait_ids))
