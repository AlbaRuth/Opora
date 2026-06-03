"""LLM-powered patient simulator for sandbox conversations."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from typing import Any

from agents.evaluators.structured_outputs import (
    SandboxPrescreeningProfile,
    SandboxScenario,
    validate_model,
)
from services.llm import LlmGateway

PATIENT_ARCHETYPES = (
    "тревожный профессионал с телесными симптомами",
    "выгоревший родитель без ресурса на себя",
    "студент с паникой и страхом оценки",
    "человек после утраты или разрыва отношений",
    "перфекционист с бессонницей и самокритикой",
    "сomatизирующий пациент с частыми обращениями к врачам",
    "социально тревожный introvert на новой работе",
    "человек с хроническим стрессом и раздражительностью",
    "пациент с навязчивыми мыслями и ритуалами",
    "человек с проблемами в отношениях и чувством одиночества",
)


def runtime_entropy(base_seed: str = "") -> str:
    """Add per-call randomness so repeated runs stay unique."""
    nonce = secrets.token_hex(8)
    base = base_seed.strip()
    if base:
        return f"{base}\nruntime_nonce={nonce}"
    return f"runtime_nonce={nonce}"


def build_prescreening_generation_messages(seed: str) -> list[dict[str, str]]:
    """Build messages for AI-generated sandbox prescreening data."""
    system_prompt = """Роль:
Ты генерируешь вымышленные данные prescreening для sandbox-теста психологического бота.

Задача:
Верни один JSON-объект с профилем пациента и настройками психолога. Каждый запуск должен давать нового, неповторимого пациента.

Правила разнообразия:
- Если seed пустой или общий — придумай новый случай с нуля.
- Если seed задан — используй его только как направление, но не копируй предыдущие прогоны дословно.
- Выбери один архетип из списка или придумай свой, но не повторяй шаблонные имена вроде Elena/Julian Vance.
- Имена, возраст, пол, стиль обращения и brief должны быть правдоподобны для России/русскоязычного контекста.
- Все текстовые поля JSON пиши по-русски.

Клинические границы:
Без графики, без реальных персональных данных, без диагнозов как установленных фактов.

Схема JSON:
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

Примеры архетипов (выбери один или свой):
- тревожный профессионал
- выгоревший родитель
- студент с паникой
- человек после утраты
- перфекционист с бессонницей

Формат ответа:
Только JSON, без markdown и пояснений."""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Seed для prescreening:\n{seed or 'seed не задан — придумай полностью нового пациента.'}\n\n"
                f"Подсказка по архетипам:\n- " + "\n- ".join(PATIENT_ARCHETYPES)
            ),
        },
    ]


def build_scenario_generation_messages(
    *,
    seed: str,
    prescreening_profile: dict[str, Any],
) -> list[dict[str, str]]:
    """Build messages for AI-generated sandbox clinical scenario."""
    system_prompt = """Роль:
Ты генерируешь клинически правдоподобный вымышленный сценарий для sandbox-теста.

Задача:
Создай уникальную ситуацию пациента, согласованную с prescreening-профилем. Это не шаблон из базы: каждый раз новая история, новые детали, новый эмоциональный рисунок.

Правила разнообразия:
- Не повторяй типовые формулировки между запусками.
- Сам выбери архетип/линию кейса (можно из brief профиля, можно новый).
- Сделай hidden_context с 3–6 конкретными фактами, которые пациент раскрывает не сразу.
- cooperation_style опиши по-русски (например: «открытый», «осторожный, но честный», «сначала уклончивый»).
- Все строковые поля JSON — только на русском языке.

Клинические границы:
Безопасно для тестовой среды, без графики, без категоричных диагнозов.

Схема JSON:
{
  "persona_archetype": "string",
  "presenting_problem": "string",
  "mental_health_history": "string",
  "physical_health_history": "string",
  "current_problems": "string",
  "intake_hypothesis": "string",
  "intake_hypothesis_explanation": "string",
  "hidden_context": ["string"],
  "emotional_arc": "string",
  "cooperation_style": "string",
  "speech_style": "string"
}

Формат ответа:
Только JSON, без markdown и пояснений."""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Prescreening profile:\n{prescreening_profile}\n\n"
                f"Scenario seed:\n{seed or 'seed не задан — придумай новый случай.'}\n\n"
                f"Подсказка по архетипам:\n- " + "\n- ".join(PATIENT_ARCHETYPES)
            ),
        },
    ]


def build_auto_patient_messages(
    *,
    conversation: list[dict[str, str]],
    start_phase: str = "intake",
    prescreening_profile: dict[str, Any] | None = None,
    clinical_card: dict[str, Any] | None = None,
    generated_scenario: dict[str, Any] | None = None,
    test_goal: str = "",
    context_limit: int | None = None,
    turn_number: int = 1,
    entropy: str = "",
) -> list[dict[str, str]]:
    """Build OpenAI-compatible messages that keep the model in patient role."""
    transcript = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in conversation[-(context_limit or 12):]
    )
    scenario = generated_scenario or {}
    archetype = scenario.get("persona_archetype") or scenario.get("cooperation_style") or "не задан"

    system_prompt = f"""Роль:
Ты симулируешь живого пациента в sandbox-тесте counseling-бота.

Задача:
Напиши только следующую реплику пациента от первого лица.

Язык:
ВСЕГДА пиши только по-русски. Даже если в диалоге встречается английский — отвечай по-русски.

Стиль и смелость:
- Не стесняйся: говори прямо о симптомах, эмоциях, теле, отношениях, страхах, стыде, быте.
- Будь живым человеком: можно путаться, уточнять, менять формулировки, проявлять эмоции.
- Избегай канцелярита, шаблонов и «идеальных» ответов пациента из учебника.
- Каждая реплика должна звучать по-новому; не повторяй одни и те же заходы.

Контекст:
- Фаза sandbox: {start_phase}
- Номер реплики пациента: {turn_number}
- Цель теста: {test_goal or "сквозная проверка intake/therapy pipeline"}
- Prescreening profile: {prescreening_profile or {}}
- Clinical card: {clinical_card or {}}
- Generated scenario: {scenario}
- Архетип/линия кейса: {archetype}
- Энтропия запуска: {entropy or "не задана"}

Поведение по фазам:
- prescreening: отвечай на текущий вопрос анкеты, не уходи в терапию раньше времени.
- intake: постепенно раскрывай проблемы, историю, тело, сомнения; часть hidden_context раскрывай не сразу.
- therapy: реагируй на последнюю реплику психолога как реальный пациент.

Запреты:
- Не раскрывай, что это симуляция, LLM, тест, sandbox, prompt или сценарий.
- Не анализируй бота, не давай JSON, не пиши пояснения разработчику.

Если следующий шаг неочевиден — всё равно дай короткую правдоподобную реплику пациента по-русски."""

    return [
        {"role": "system", "content": system_prompt.strip()},
        {
            "role": "user",
            "content": (
                "Текущий диалог:\n"
                f"{transcript or 'Диалог ещё не начался.'}\n\n"
                "Напиши только следующую реплику пациента."
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
        conversation: list[dict[str, str]],
        start_phase: str = "intake",
        prescreening_profile: dict[str, Any] | None = None,
        clinical_card: dict[str, Any] | None = None,
        generated_scenario: dict[str, Any] | None = None,
        test_goal: str = "",
        account_id: int | None = None,
        session_id: int | None = None,
        turn_number: int = 1,
        entropy: str = "",
    ) -> dict[str, Any]:
        context_limit = self.llm_config.sandbox.auto_patient_context_messages
        messages = build_auto_patient_messages(
            conversation=conversation,
            start_phase=start_phase,
            prescreening_profile=prescreening_profile,
            clinical_card=clinical_card,
            generated_scenario=generated_scenario,
            test_goal=test_goal,
            context_limit=context_limit,
            turn_number=turn_number,
            entropy=entropy,
        )
        result = await self.llm_gateway.complete(
            agent_type="sandbox_patient",
            task_name="auto_patient",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt_template="build_auto_patient_messages",
            prompt_variables={
                "conversation": conversation,
                "start_phase": start_phase,
                "prescreening_profile": prescreening_profile or {},
                "clinical_card": clinical_card or {},
                "generated_scenario": generated_scenario or {},
                "test_goal": test_goal,
                "context_limit": context_limit,
                "turn_number": turn_number,
                "entropy": entropy,
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
        effective_seed = runtime_entropy(seed)
        messages = build_prescreening_generation_messages(effective_seed)
        result = await self.llm_gateway.complete(
            agent_type="sandbox_patient",
            task_name="prescreening_profile_generation",
            messages=messages,
            account_id=account_id,
            session_id=session_id,
            prompt=messages[-1]["content"],
            prompt_template="build_prescreening_generation_messages",
            prompt_variables={"seed": effective_seed},
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
        prescreening_profile: dict[str, Any],
        account_id: int | None = None,
        session_id: int | None = None,
    ) -> SandboxScenario:
        effective_seed = runtime_entropy(seed)
        profile_dict = dict(prescreening_profile)
        messages = build_scenario_generation_messages(
            seed=effective_seed,
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
            prompt_variables={"seed": effective_seed, "prescreening_profile": profile_dict},
        )
        if result.get("success"):
            validated = validate_model(SandboxScenario, result.get("content"))
            if isinstance(validated, SandboxScenario):
                return validated
        return SandboxScenario()