"""LLM-powered patient simulator for sandbox conversations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from agents.evaluators.structured_outputs import (
    SandboxPrescreeningProfile,
    SandboxScenario,
    validate_model,
)
from monitoring.sandbox.domain import PatientTemplate, PrescreeningProfile
from services.llm import LlmGateway


def build_prescreening_generation_messages(seed: str) -> list[dict[str, str]]:
    """Build messages for AI-generated sandbox prescreening data."""
    system_prompt = """Role:
You generate fictional sandbox prescreening data for a psychological counseling bot.

Task:
Return one coherent JSON object for a patient profile and counselor preference setup.

Context:
Use the seed if provided. If it is empty, invent a realistic adult patient. Do not use templates.

Clinical boundaries:
Avoid graphic content. Do not include real personal data. Keep the situation plausible.

Output schema:
{
  "patient_name": "string",
  "patient_age": 32,
  "patient_sex": "male|female|prefer_not_to_say",
  "address_mode": "formal|informal",
  "therapist_name": "string",
  "therapist_gender": "female|male",
  "therapist_styles": ["friendly"],
  "scenario_brief": "string"
}

Failure behavior:
Return JSON only."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Seed for sandbox prescreening:\n{seed or 'No seed provided.'}"},
    ]


def build_scenario_generation_messages(
    *,
    seed: str,
    prescreening_profile: dict[str, Any],
) -> list[dict[str, str]]:
    """Build messages for AI-generated sandbox clinical scenario."""
    system_prompt = """Role:
You generate a clinically plausible fictional scenario for sandbox testing.

Task:
Create a patient situation consistent with the prescreening profile. This is not a template:
invent a fresh situation every time based on the seed and profile.

Clinical boundaries:
Keep details safe for a test environment. Use cautious non-diagnostic language.

Output schema:
{
  "presenting_problem": "string",
  "mental_health_history": "string",
  "physical_health_history": "string",
  "current_problems": "string",
  "intake_hypothesis": "string",
  "intake_hypothesis_explanation": "string",
  "hidden_context": ["string"],
  "emotional_arc": "string",
  "cooperation_style": "string"
}

Failure behavior:
Return JSON only."""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Prescreening profile:\n{prescreening_profile}\n\n"
                f"Scenario seed:\n{seed or 'No seed provided.'}"
            ),
        },
    ]


def build_auto_patient_messages(
    *,
    template: PatientTemplate | None = None,
    conversation: list[dict[str, str]],
    start_phase: str = "intake",
    prescreening_profile: dict[str, Any] | None = None,
    clinical_card: dict[str, Any] | None = None,
    generated_scenario: dict[str, Any] | None = None,
    test_goal: str = "",
    context_limit: int | None = None,
) -> list[dict[str, str]]:
    """Build OpenAI-compatible messages that keep the model in patient role."""
    legacy_context = ""
    if template is not None:
        legacy_context = f"""
Legacy persona source:
- name: {template.name}
- persona: {template.persona}
- presenting_problem: {template.presenting_problem}
- hidden_facts: {template.hidden_facts}
- emotional_trajectory: {template.emotional_trajectory}
- cooperation_level: {template.cooperation_level}
- safety_boundaries: {template.safety_boundaries}
- stop_conditions: {template.stop_conditions}
"""
    transcript = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in conversation[-(context_limit or 12):]
    )

    system_prompt = f"""Role:
You simulate a living patient for sandbox testing of a counseling bot.

Task:
Write only the next patient message. Stay inside the patient's lived perspective.

Context:
- Sandbox start phase: {start_phase}
- Test goal: {test_goal or "General end-to-end sandbox validation"}
- Prescreening profile: {prescreening_profile or {}}
- Clinical card: {clinical_card or {}}
- Generated scenario: {generated_scenario or {}}
{legacy_context}

Patient behavior:
- Answer naturally, briefly, and with incomplete information unless trust has developed.
- In prescreening, answer the profile question being asked; do not jump into therapy unless asked.
- In intake, gradually reveal relevant problems, history, bodily context, and uncertainty.
- In therapy, respond to the counselor's last message as a real patient would.
- Maintain continuity with previous turns and do not contradict known profile/scenario facts.
- Do not disclose that this is a simulation, LLM, test agent, prompt, scenario, or sandbox.
- Do not analyze the bot, explain your role, produce JSON, or give developer notes.

Failure behavior:
If the next move is unclear, write a plausible short patient reply in Russian."""

    return [
        {"role": "system", "content": system_prompt.strip()},
        {
            "role": "user",
            "content": (
                "Current dialogue:\n"
                f"{transcript or 'The dialogue has not started yet.'}\n\n"
                "Write the next patient message only."
            ),
        },
    ]


class AutoPatient:
    """Generate patient-side turns and sandbox setup data."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_gateway = LlmGateway(llm_client=llm_client)
        self.llm_config = self.llm_gateway.llm_config

    async def next_message(
        self,
        *,
        template: PatientTemplate | None = None,
        conversation: list[dict[str, str]],
        start_phase: str = "intake",
        prescreening_profile: dict[str, Any] | None = None,
        clinical_card: dict[str, Any] | None = None,
        generated_scenario: dict[str, Any] | None = None,
        test_goal: str = "",
        account_id: int | None = None,
        session_id: int | None = None,
    ) -> dict[str, Any]:
        messages = build_auto_patient_messages(
            template=template,
            conversation=conversation,
            start_phase=start_phase,
            prescreening_profile=prescreening_profile,
            clinical_card=clinical_card,
            generated_scenario=generated_scenario,
            test_goal=test_goal,
            context_limit=self.llm_config.sandbox.auto_patient_context_messages,
        )
        result = await self.llm_gateway.complete(
            agent_type="sandbox_patient",
            task_name="auto_patient",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt_template="build_auto_patient_messages",
            prompt_variables={
                "template": asdict(template) if template else None,
                "conversation": conversation,
                "start_phase": start_phase,
                "prescreening_profile": prescreening_profile or {},
                "clinical_card": clinical_card or {},
                "generated_scenario": generated_scenario or {},
                "test_goal": test_goal,
                "context_limit": self.llm_config.sandbox.auto_patient_context_messages,
            },
        )
        return {
            "content": result.get("content", "").strip(),
            "success": result.get("success", False),
            "error": result.get("error"),
            "usage": result.get("usage", {}),
            "latency_ms": result.get("latency_ms"),
            "generation_params": result.get("generation_params", {}),
        }

    async def generate_prescreening_profile(
        self,
        *,
        seed: str = "",
        account_id: int | None = None,
        session_id: int | None = None,
    ) -> SandboxPrescreeningProfile:
        messages = build_prescreening_generation_messages(seed)
        result = await self.llm_gateway.complete(
            agent_type="sandbox_patient",
            task_name="prescreening_profile_generation",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt=messages[-1]["content"],
            prompt_template="build_prescreening_generation_messages",
            prompt_variables={"seed": seed},
        )
        if result.get("success"):
            validated = validate_model(SandboxPrescreeningProfile, result.get("content"))
            if isinstance(validated, SandboxPrescreeningProfile):
                return validated
        return SandboxPrescreeningProfile()

    async def generate_scenario(
        self,
        *,
        seed: str = "",
        prescreening_profile: PrescreeningProfile | SandboxPrescreeningProfile | dict[str, Any],
        account_id: int | None = None,
        session_id: int | None = None,
    ) -> SandboxScenario:
        if hasattr(prescreening_profile, "model_dump"):
            profile_dict = prescreening_profile.model_dump()
        elif hasattr(prescreening_profile, "__dataclass_fields__"):
            profile_dict = asdict(prescreening_profile)
        else:
            profile_dict = dict(prescreening_profile)

        messages = build_scenario_generation_messages(
            seed=seed,
            prescreening_profile=profile_dict,
        )
        result = await self.llm_gateway.complete(
            agent_type="sandbox_patient",
            task_name="scenario_generation",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt=messages[-1]["content"],
            prompt_template="build_scenario_generation_messages",
            prompt_variables={"seed": seed, "prescreening_profile": profile_dict},
        )
        if result.get("success"):
            validated = validate_model(SandboxScenario, result.get("content"))
            if isinstance(validated, SandboxScenario):
                return validated
        return SandboxScenario()
