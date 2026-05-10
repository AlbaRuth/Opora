"""
Prompt templates for IntakeAgent.
All control instructions are in English; patient-facing text is Russian.
"""

import json


class IntakePrompts:
    """Prompts for initial intake stage and background card updates."""

    @staticmethod
    def get_system_message() -> str:
        return (
            "You are an intake assistant for a psychological counseling bot. "
            "You do not provide diagnosis or treatment plans. "
            "You collect intake information, build a concise preliminary clinical hypothesis, "
            "and ask focused follow-up questions. "
            "CRITICAL: Any patient-facing text MUST be in Russian."
        )

    @staticmethod
    def get_intake_turn_prompt(
        patient_message: str,
        patient_name: str,
        patient_age: int | None,
        current_card: dict[str, str],
        min_user_turns: int,
        current_user_turns: int,
        required_fields: list[str],
        max_question_words: int,
        summary_max_words: int,
    ) -> str:
        required_fields_json = json.dumps(required_fields, ensure_ascii=False)
        card_json = json.dumps(current_card, ensure_ascii=False)
        age_text = str(patient_age) if patient_age is not None else ""
        return f"""You are processing an intake turn.

Return JSON ONLY with this exact schema:
{{
  "mental_health_history": "string",
  "physical_health_history": "string",
  "current_problems": "string",
  "intake_hypothesis": "string",
  "intake_hypothesis_explanation": "string",
  "missing_fields": ["string"],
  "is_intake_complete": true_or_false,
  "patient_response_ru": "string"
}}

Rules:
1) Update fields only when patient provided enough new evidence; otherwise keep previous values.
2) Keep hypothesis as preliminary and uncertain; never claim official diagnosis.
3) Intake can be complete only if:
   - user_turns_after_processing >= {min_user_turns}
   - all required fields are filled: {required_fields_json}
4) If intake is NOT complete:
   - patient_response_ru must be one short empathic sentence + one focused follow-up question in Russian.
   - Question should help fill one missing field.
   - Keep question concise (about <= {max_question_words} words).
5) If intake IS complete:
   - patient_response_ru must be in Russian and include:
     - direct address to patient name when available
     - phrase equivalent to \"now I know enough information about you\"
     - concise summary of what was learned
     - preliminary hypothesis + explanation (not diagnosis)
     - transition sentence equivalent to \"now we will work on your problems\"
   - keep full final message concise (about <= {summary_max_words} words).
6) Never output markdown fences, comments, or extra keys.

Patient profile:
- name: {patient_name}
- age: {age_text}

Current card:
{card_json}

Current user turns in intake: {current_user_turns}
This turn patient message:
{patient_message}
"""

    @staticmethod
    def get_background_update_prompt(
        patient_message: str,
        current_card: dict[str, str],
    ) -> str:
        card_json = json.dumps(current_card, ensure_ascii=False)
        return f"""Extract structured updates from a therapy message.

Return JSON ONLY:
{{
  "mental_health_history": "string_or_empty",
  "physical_health_history": "string_or_empty",
  "current_problems": "string_or_empty",
  "intake_hypothesis": "string_or_empty",
  "intake_hypothesis_explanation": "string_or_empty"
}}

Rules:
- Keep existing card values unless message gives explicit new evidence.
- If no update for a field, return empty string for that field.
- No diagnosis claims; keep wording as preliminary hypothesis if applicable.
- No extra keys, no markdown.

Current card:
{card_json}

Patient message:
{patient_message}
"""

    @staticmethod
    def get_fallback_intake_response(patient_name: str = "") -> str:
        name_prefix = f"{patient_name}, " if patient_name else ""
        return (
            f"{name_prefix}спасибо, что делитесь. "
            "Чтобы лучше понять вашу ситуацию, расскажите, пожалуйста, что сейчас беспокоит вас больше всего."
        )
