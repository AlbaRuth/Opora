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
        """Test system message with custom values."""
        message = TherapistPrompts.get_system_message(
            therapist_name="Доктор Иван",
            therapist_gender="male",
            therapist_traits=["strict", "business"],
        )

        assert "Доктор Иван" in message
        assert "male" in message
        assert "strict" in message or "Maintain professional boundaries" in message
        assert "business" in message or "practical solutions" in message
        # Check for language instruction
        assert "CRITICAL INSTRUCTION" in message
        assert "SAME LANGUAGE" in message

    def test_get_system_message_with_traits(self):
        """Test system message includes trait guidelines."""
        message = TherapistPrompts.get_system_message(
            therapist_traits=["calm", "empathetic"],
        )

        assert "soothing" in message or "measured tone" in message
        assert "validate feelings" in message or "understanding" in message
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

    def test_get_response_prompt_with_personalization(self):
        """Test response prompt includes personalization."""
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
            therapist_traits=["kind", "calm"],
        )

        assert "Анна" in prompt
        assert "Максим" in prompt
        assert "25 years old" in prompt or "25" in prompt
        assert "kind" in prompt or "warmth" in prompt
        assert "calm" in prompt or "soothing" in prompt

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

    def test_trait_guidelines_exist(self):
        """Test that all traits have guidelines."""
        required_traits = ["strict", "business", "calm", "kind", "restrained", "empathetic"]

        for trait in required_traits:
            assert trait in TherapistPrompts.TRAIT_GUIDELINES
            assert len(TherapistPrompts.TRAIT_GUIDELINES[trait]) > 0

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

    def test_get_response_prompt_with_empty_traits(self):
        """Test response prompt with empty traits list."""
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
            therapist_traits=[],
        )

        # Should not include traits section
        assert "Your character traits" not in prompt

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

        assert "CRITICAL RULE - LANGUAGE MATCHING" in prompt
        assert "SAME LANGUAGE" in prompt
        assert "patient's input" in prompt.lower() or "patient's message" in prompt.lower()
