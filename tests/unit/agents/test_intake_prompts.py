"""Unit tests for IntakePrompts."""

import sys
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

class TestIntakePrompts:
    def test_system_message_contains_language_rule(self):
        from agents.prompts.intake_prompts import IntakePrompts
        message = IntakePrompts.get_system_message()
        assert "Russian" in message or "russian" in message.lower()
        assert "Опора" in message
        assert "Never say you are an AI" in message or "Never say you are" in message
        assert "ИИ-ассистент" in message

    def test_system_message_custom_therapist_with_styles(self):
        """Test system message with new styles (NEW)."""
        from agents.prompts.intake_prompts import IntakePrompts
        message = IntakePrompts.get_system_message(
            therapist_name="Доктор Анна",
            therapist_gender="female",
            therapist_styles=["friendly", "soft"],  # NEW: styles instead of traits
        )
        assert "Доктор Анна" in message
        # NEW: Check for style guidelines
        assert "friendly" in message.lower() or "дружелюбный" in message.lower()
        assert "soft" in message.lower() or "мягкий" in message.lower()
        # Check for dynamic switching instructions
        assert "DYNAMIC STYLE SWITCHING" in message or "динамический" in message.lower()

    def test_intake_turn_prompt_contains_completion_rules(self):
        """Test intake turn prompt with new styles (NEW)."""
        from agents.prompts.intake_prompts import IntakePrompts
        prompt = IntakePrompts.get_intake_turn_prompt(
            patient_message="Мне тяжело спать.",
            patient_name="Анна",
            patient_age=28,
            patient_sex="prefer_not_to_say",
            address_mode="formal",
            current_card={
                "mental_health_history": "",
                "physical_health_history": "",
                "current_problems": "",
                "intake_hypothesis": "",
                "intake_hypothesis_explanation": "",
            },
            min_user_turns=6,
            current_user_turns=3,
            required_fields=["current_problems"],
            therapist_styles=["business", "soft"],  # NEW: styles parameter
        )
        assert "Return JSON ONLY" in prompt
        assert "is_intake_complete" in prompt
        assert "current_problems" in prompt
        assert "Опора" in prompt
        assert "Counselor display name" in prompt
        # NEW: Check for active style in prompt
        assert "ACTIVE STYLE" in prompt

    def test_intake_turn_prompt_contains_anti_repetition_rules(self):
        from agents.prompts.intake_prompts import IntakePrompts
        prompt = IntakePrompts.get_intake_turn_prompt(
            patient_message="Мне тяжело спать.",
            patient_name="Анна",
            patient_age=28,
            patient_sex="prefer_not_to_say",
            address_mode="formal",
            current_card={},
            min_user_turns=6,
            current_user_turns=3,
            required_fields=["current_problems"],
        )
        # Check for anti-repetition rules
        assert "ANTI-REPETITION" in prompt or "AVOID" in prompt
        assert "Я понимаю" in prompt or "avoid" in prompt.lower()
        assert "varied language" in prompt.lower() or "Vary your" in prompt

    def test_intake_turn_prompt_contains_adaptive_length_rules(self):
        from agents.prompts.intake_prompts import IntakePrompts
        prompt = IntakePrompts.get_intake_turn_prompt(
            patient_message="Мне тяжело спать.",
            patient_name="Анна",
            patient_age=28,
            patient_sex="prefer_not_to_say",
            address_mode="formal",
            current_card={},
            min_user_turns=6,
            current_user_turns=3,
            required_fields=["current_problems"],
        )
        # Check for adaptive length instructions
        assert "ADAPTIVE LENGTH" in prompt or "adaptive" in prompt.lower()
        assert "emotional depth" in prompt.lower() or "emotional" in prompt.lower()
        assert "NEVER force a fixed length" in prompt or "fixed length" in prompt.lower()

    def test_intake_turn_prompt_with_context_window(self):
        from agents.prompts.intake_prompts import IntakePrompts
        recent_dialogue = [
            {"role": "user", "content": "Привет, я чувствую тревогу."},
            {"role": "assistant", "content": "Здравствуйте. Расскажите подробнее."},
        ]
        prompt = IntakePrompts.get_intake_turn_prompt(
            patient_message="Мне тяжело спать по ночам.",
            patient_name="Анна",
            patient_age=28,
            patient_sex="prefer_not_to_say",
            address_mode="formal",
            current_card={},
            min_user_turns=6,
            current_user_turns=2,
            required_fields=["current_problems"],
            max_user_turns=12,
            recent_dialogue=recent_dialogue,
        )
        # Check for context window in prompt
        assert "Recent intake dialogue" in prompt
        assert "Patient: Привет" in prompt
        assert "Counselor" in prompt
        assert "Intake turn limit" in prompt

    def test_intake_turn_prompt_avoid_patterns_included(self):
        from agents.prompts.intake_prompts import IntakePrompts
        avoid_patterns = ["Я понимаю", "Я вас услышал"]
        prompt = IntakePrompts.get_intake_turn_prompt(
            patient_message="Тест",
            patient_name="Тест",
            patient_age=25,
            patient_sex="prefer_not_to_say",
            address_mode="formal",
            current_card={},
            min_user_turns=6,
            current_user_turns=1,
            required_fields=["current_problems"],
            avoid_patterns=avoid_patterns,
        )
        # Check that avoid patterns are in the prompt
        assert "AVOID using these repetitive phrases" in prompt
        for pattern in avoid_patterns:
            assert pattern in prompt

    def test_background_update_prompt_structure(self):
        from agents.prompts.intake_prompts import IntakePrompts
        prompt = IntakePrompts.get_background_update_prompt(
            patient_message="Последнюю неделю еще сложнее засыпать.",
            current_card={
                "mental_health_history": "Тревожность",
                "physical_health_history": "Головные боли",
                "current_problems": "Бессонница",
                "intake_hypothesis": "",
                "intake_hypothesis_explanation": "",
            },
        )
        assert "Extract structured updates" in prompt
        assert "string_or_empty" in prompt
