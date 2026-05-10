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
        assert "intake assistant" in message.lower()
        assert "Russian" in message or "russian" in message.lower()

    def test_intake_turn_prompt_contains_completion_rules(self):
        from agents.prompts.intake_prompts import IntakePrompts
        prompt = IntakePrompts.get_intake_turn_prompt(
            patient_message="Мне тяжело спать.",
            patient_name="Анна",
            patient_age=28,
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
            max_question_words=35,
            summary_max_words=180,
        )
        assert "Return JSON ONLY" in prompt
        assert "is_intake_complete" in prompt
        assert "current_problems" in prompt

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
