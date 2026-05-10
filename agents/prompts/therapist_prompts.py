"""
Prompt templates for TherapistAgent.
Original prompts from Opora agent/main.py preserved.
Extended with prescreening personalization and multilingual support.
"""


class TherapistPrompts:
    """Prompts for generating therapist responses."""

    # Mapping of traits to behavioral guidelines (in English - part of system behavior)
    TRAIT_GUIDELINES = {
        "strict": "Maintain professional boundaries and clear structure. Be firm but fair.",
        "business": "Focus on practical solutions and actionable advice. Be concise and goal-oriented.",
        "calm": "Speak in a soothing, measured tone. Create a peaceful atmosphere.",
        "kind": "Show warmth, compassion, and unconditional positive regard.",
        "restrained": "Be reserved and thoughtful. Avoid excessive emotion while staying supportive.",
        "empathetic": "Deeply validate feelings and show understanding of the patient's experience.",
    }

    @staticmethod
    def get_system_message(
        therapist_name: str = "Опора",
        therapist_gender: str = "female",
        therapist_traits: list[str] | None = None,
    ) -> str:
        """
        System message for therapist with personalization.
        All system instructions remain in English to ensure consistent behavior.

        Args:
            therapist_name: How the patient addresses the therapist (may be in Russian)
            therapist_gender: 'female' or 'male'
            therapist_traits: List of selected character traits
        """
        gender_desc = "female" if therapist_gender == "female" else "male"

        # Build traits description
        traits = therapist_traits or []
        trait_instructions = []
        for trait in traits:
            if trait in TherapistPrompts.TRAIT_GUIDELINES:
                trait_instructions.append(TherapistPrompts.TRAIT_GUIDELINES[trait])

        traits_section = ""
        if trait_instructions:
            traits_section = "\nCharacter traits to embody:\n" + "\n".join(
                f"- {instr}" for instr in trait_instructions
            )

        return f"""You are an experienced and empathetic psychological counselor.
Your name is {therapist_name}.
You are a {gender_desc} psychologist.
You provide compassionate, professional support while maintaining appropriate therapeutic boundaries.{traits_section}

CRITICAL INSTRUCTION: You must ALWAYS respond in the SAME LANGUAGE as the patient's message. Detect the language of the patient's input and match it exactly in your response. If the patient writes in Russian, you respond in Russian. If they write in English, you respond in English. If they write in any other language, match that language. Never respond in a different language than the patient used.

Always respond in a way that reflects your chosen character and approach."""

    @staticmethod
    def get_response_prompt(
        patient_input: str,
        memory_result: str,
        primary_emotion: str,
        emotional_intensity: float,
        current_therapy: str,
        current_stage: str,
        current_strategy: str,
        current_strategy_text: str,
        session_memory: dict,
        # Prescreening personalization fields
        therapist_name: str = "Опора",
        patient_display_name: str = "",
        patient_age: int | None = None,
        therapist_traits: list[str] | None = None,
    ) -> str:
        """
        Build response generation prompt with personalization.
        Rules and instructions remain in English; patient data is preserved in original language.
        """
        # Keep Opora-like memory rendering shape while preserving current API.
        session_memory_context = {
            "dialogs": session_memory.get("dialogs", []),
        }

        # Build personalization context (preserving Russian names as provided)
        personalization = f"Your name is {therapist_name}."

        if patient_display_name:
            personalization += f" The patient's name is {patient_display_name}."

        if patient_age is not None:
            personalization += f" The patient is {patient_age} years old."

        # Build traits context (in English - system behavior)
        traits = therapist_traits or []
        if traits:
            trait_descs = []
            for trait in traits:
                if trait in TherapistPrompts.TRAIT_GUIDELINES:
                    trait_descs.append(TherapistPrompts.TRAIT_GUIDELINES[trait])
            if trait_descs:
                personalization += "\n\nYour character traits:\n" + "\n".join(
                    f"- {desc}" for desc in trait_descs
                )

        prompt = f"""##Role:
You are a professional and empathetic psychological counselor.
{personalization}

Your job is to respond to the patient compassionately and offer support in psychological counseling based on the following information and requirements.
##Patient Context (preserved in original language):
  - Patient's current message: {patient_input}
  - Relevant historical memories: {memory_result}
  - Patient's primary emotion: {primary_emotion} (intensity: {emotional_intensity})

##Therapy Context:
  - Current therapy approach: {current_therapy}
  - Treatment stage: {current_stage}
  - Response strategy: {current_strategy}
  - Strategy guidance: {current_strategy_text}

##Response Requirements:
  1. Your expression should be in line with the psychological counselor's speaking style, as colloquial and natural as possible.
  2. Don't always directly repeat or quote what the patient has said. Just empathize the patient with as little words as possible. Ensure the smooth of the conversation.
  3. You must use diverse and different sentence patterns to reply each time to avoid a single reply mode. To avoid using the same sentence pattern, please refer to your previous replies from the conversation records for this session:{session_memory_context}.
  4. When the patient expresses a clear desire to end this conversation, please also provide a response to end the conversation in a declarative tone.
  5. Always embody your chosen character traits in your response style and tone.

##CRITICAL RULE - LANGUAGE MATCHING:
  You MUST respond in the EXACT SAME LANGUAGE as the patient's message above. Carefully detect the language of "Patient's current message" and respond entirely in that language. This is the most important constraint.

##Constraints:
  - Respond in the same language as the patient's input.
  - Your response should be no more than 60 words.
  - Do not provide any word count, analysis or explanation.
  - Directly generate your response only.
"""
        return prompt

    @staticmethod
    def get_first_session_greeting(
        therapist_name: str = "Опора",
        patient_display_name: str = "",
        language: str = "ru",
    ) -> str:
        """
        Greeting for first session with personalization.
        Supports Russian (default) and English based on language parameter.
        """
        if language == "ru" or language == "russian":
            name_part = f", {patient_display_name}" if patient_display_name else ""
            return (
                f"Здравствуйте{name_part}! Я {therapist_name}, ваш психолог. "
                f"Рада знакомству. Сегодня мы можем поговорить о вашей текущей ситуации."
            )
        else:
            name_part = f", {patient_display_name}" if patient_display_name else ""
            return f"Hello{name_part}! I'm {therapist_name}, your psychological counselor. Nice to meet you. Today we can talk about your recent situation."

    @staticmethod
    def get_return_session_greeting(
        therapist_name: str = "Опора",
        patient_display_name: str = "",
        language: str = "ru",
    ) -> str:
        """
        Greeting for returning patient with personalization.
        Supports Russian (default) and English based on language parameter.
        """
        if language == "ru" or language == "russian":
            name_part = f", {patient_display_name}" if patient_display_name else ""
            return (
                f"Здравствуйте{name_part}! Это снова {therapist_name}. "
                f"Рада вас видеть снова. Как вы себя чувствуете сегодня?"
            )
        else:
            name_part = f", {patient_display_name}" if patient_display_name else ""
            return f"Hello{name_part}! {therapist_name} here. Nice to see you again. How are you feeling today?"

    @staticmethod
    def get_fallback_response(language: str = "ru") -> str:
        """Fallback when LLM fails. Supports Russian (default) and English."""
        if language == "ru" or language == "russian":
            return "Извините, я временно не могу обработать ваш запрос. Пожалуйста, попробуйте еще раз."
        return "Sorry, I'm temporarily unable to process your request, please try again."
