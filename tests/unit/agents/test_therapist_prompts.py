"""
Unit tests for TherapistPrompts with prescreening personalization.
"""

import pytest

from agents.prompts.therapist_prompts import TherapistPrompts


class TestTherapistPromptsPersonalization:
    """Test personalized prompts."""

    def test_get_system_message_default(self):
        """Test system message with default values."""
        message = TherapistPrompts.get_system_message()

        assert "Опора" in message
        assert "female" in message
        assert "psychological counselor" in message
        # Check for language instruction
        assert "CRITICAL INSTRUCTION" in message
        assert "SAME LANGUAGE" in message

    def test_get_system_message_custom(self):
        """Test system message with custom values and new styles."""
        message = TherapistPrompts.get_system_message(
            therapist_name="Доктор Иван",
            therapist_gender="male",
            therapist_styles=["business", "motivating"],  # NEW: styles instead of traits
        )

        assert "Доктор Иван" in message
        assert "male" in message
        # NEW: Check for style guidelines in the message
        assert "business" in message.lower() or "деловой" in message.lower()
        assert "motivating" in message.lower() or "мотивирующий" in message.lower()
        # Check for language instruction
        assert "CRITICAL INSTRUCTION" in message
        assert "SAME LANGUAGE" in message

    def test_get_system_message_with_styles(self):
        """Test system message includes style guidelines (NEW: 4 styles)."""
        message = TherapistPrompts.get_system_message(
            therapist_styles=["soft", "friendly"],  # NEW: styles instead of traits
        )

        # NEW: Check for style descriptions
        assert "мягкий" in message.lower() or "soft" in message.lower()
        assert "дружелюбный" in message.lower() or "friendly" in message.lower()
        # Check for dynamic switching instructions when multiple styles
        assert "DYNAMIC STYLE SWITCHING" in message or "dynamic" in message.lower()
        # Check for language instruction
        assert "CRITICAL INSTRUCTION" in message
        assert "SAME LANGUAGE" in message

    def test_get_system_message_language_instruction(self):
        """Test system message includes language matching instruction."""
        message = TherapistPrompts.get_system_message()

        # Check that language instruction is present
        assert "CRITICAL INSTRUCTION" in message
        assert "SAME LANGUAGE" in message
        assert "patient's message" in message.lower() or "patient's input" in message.lower()
        assert "Detect the language" in message or "detect the language" in message.lower()

    def test_get_response_prompt_default(self):
        """Test response prompt with default values."""
        prompt = TherapistPrompts.get_response_prompt(
            patient_input="I'm feeling anxious",
            memory_result="",
            primary_emotion="anxiety",
            emotional_intensity=0.7,
            current_therapy="CBT",
            current_stage="initial",
            current_strategy="validation",
            current_strategy_text="Validate the patient's feelings",
            session_memory={"dialogs": []},
        )

        assert "I'm feeling anxious" in prompt
        assert "anxiety" in prompt
        assert "Опора" in prompt
        assert "60 words" in prompt

    def test_get_response_prompt_with_styles(self):
        """Test response prompt includes styles personalization (NEW)."""
        prompt = TherapistPrompts.get_response_prompt(
            patient_input="Hello",
            memory_result="",
            primary_emotion="neutral",
            emotional_intensity=0.5,
            current_therapy="general",
            current_stage="beginning",
            current_strategy="greeting",
            current_strategy_text="Greet the patient warmly",
            session_memory={"dialogs": []},
            therapist_name="Анна",
            patient_display_name="Максим",
            patient_age=25,
            therapist_styles=["friendly", "soft"],  # NEW: styles instead of traits
        )

        assert "Анна" in prompt
        assert "Максим" in prompt
        assert "25 years old" in prompt or "25" in prompt
        # NEW: Check for active style selection
        assert "ACTIVE STYLE" in prompt
        assert "friendly" in prompt.lower() or "дружелюбный" in prompt.lower()

    def test_get_first_session_greeting_russian_default(self):
        """Test first session greeting in Russian (default)."""
        greeting = TherapistPrompts.get_first_session_greeting()

        assert "Опора" in greeting
        assert "Здравствуйте" in greeting
        assert "психолог" in greeting

    def test_get_first_session_greeting_russian_personalized(self):
        """Test first session greeting in Russian with personalization."""
        greeting = TherapistPrompts.get_first_session_greeting(
            therapist_name="Доктор Анна",
            patient_display_name="Алексей",
            language="ru",
        )

        assert "Доктор Анна" in greeting
        assert "Алексей" in greeting
        assert "Здравствуйте, Алексей" in greeting
        assert "Рада знакомству" in greeting

    def test_get_first_session_greeting_english(self):
        """Test first session greeting in English."""
        greeting = TherapistPrompts.get_first_session_greeting(
            therapist_name="Dr. Smith",
            patient_display_name="Alex",
            language="en",
        )

        assert "Dr. Smith" in greeting
        assert "Alex" in greeting
        assert "Hello, Alex" in greeting
        assert "Nice to meet you" in greeting

    def test_get_return_session_greeting_russian_default(self):
        """Test return session greeting in Russian (default)."""
        greeting = TherapistPrompts.get_return_session_greeting()

        assert "Опора" in greeting
        assert "Здравствуйте" in greeting
        assert "Рада вас видеть" in greeting

    def test_get_return_session_greeting_russian_personalized(self):
        """Test return session greeting in Russian with personalization."""
        greeting = TherapistPrompts.get_return_session_greeting(
            therapist_name="Доктор Анна",
            patient_display_name="Мария",
            language="ru",
        )

        assert "Доктор Анна" in greeting
        assert "Мария" in greeting
        assert "Здравствуйте, Мария" in greeting
        assert "Это снова Доктор Анна" in greeting

    def test_get_return_session_greeting_english(self):
        """Test return session greeting in English."""
        greeting = TherapistPrompts.get_return_session_greeting(
            therapist_name="Dr. Smith",
            patient_display_name="Maria",
            language="en",
        )

        assert "Dr. Smith" in greeting
        assert "Maria" in greeting
        assert "Hello, Maria" in greeting
        assert "Nice to see you again" in greeting

    def test_style_guidelines_exist(self):
        """Test that all 4 new styles have guidelines with detailed markers."""
        required_styles = ["friendly", "soft", "business", "motivating"]

        for style in required_styles:
            assert style in TherapistPrompts.STYLE_GUIDELINES
            sg = TherapistPrompts.STYLE_GUIDELINES[style]
            assert "description" in sg
            assert "language_markers" in sg
            assert "when_to_use" in sg
            assert len(sg["language_markers"]) > 0

    def test_fallback_response_russian(self):
        """Test fallback response in Russian (default)."""
        fallback = TherapistPrompts.get_fallback_response()

        assert len(fallback) > 0
        assert "Извините" in fallback or "временно" in fallback

    def test_fallback_response_english(self):
        """Test fallback response in English."""
        fallback = TherapistPrompts.get_fallback_response(language="en")

        assert len(fallback) > 0
        assert "Sorry" in fallback or "temporarily" in fallback

    def test_get_response_prompt_with_empty_styles(self):
        """Test response prompt with empty styles list (NEW)."""
        prompt = TherapistPrompts.get_response_prompt(
            patient_input="Test",
            memory_result="",
            primary_emotion="neutral",
            emotional_intensity=0.5,
            current_therapy="general",
            current_stage="beginning",
            current_strategy="test",
            current_strategy_text="Test strategy",
            session_memory={"dialogs": []},
            therapist_styles=[],  # NEW: empty styles
        )

        # Should not include styles section when empty
        assert "Your available communication styles" not in prompt

    def test_get_response_prompt_includes_language_instruction(self):
        """Test that response prompt includes language matching instruction."""
        prompt = TherapistPrompts.get_response_prompt(
            patient_input="Привет",
            memory_result="",
            primary_emotion="neutral",
            emotional_intensity=0.5,
            current_therapy="general",
            current_stage="beginning",
            current_strategy="greeting",
            current_strategy_text="Greet warmly",
            session_memory={"dialogs": []},
        )

        assert "EXACT SAME LANGUAGE" in prompt
        assert "##CRITICAL RULES" in prompt
        assert "patient's input" in prompt.lower() or "patient's message" in prompt.lower()
