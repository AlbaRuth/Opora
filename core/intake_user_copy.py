"""User-facing scripted text for clinical intake (non-LLM)."""

from core.clinical_card_format import (
    card_has_clinical_data,
    format_clinical_card_fields,
    truncate_words,
)


def build_intake_extracted_summary(
    card: dict[str, str],
    *,
    address_mode: str,
    initial_info_insufficient: bool,
    max_words: int = 180,
) -> str:
    """Patient-facing summary of extracted intake card fields at closure."""
    if not card_has_clinical_data(card):
        if address_mode == "informal":
            return (
                "Я пока зафиксировал только часть информации — "
                "полную сводку можно будет посмотреть по команде /summary."
            )
        return (
            "Я пока зафиксировал только часть информации — "
            "полную сводку можно будет посмотреть по команде /summary."
        )

    if initial_info_insufficient:
        intro = (
            "Пока у нас не хватает данных для полной картины, но вот что уже записано:"
            if address_mode == "formal"
            else "Пока не хватает данных для полной картины, но вот что уже записано:"
        )
    elif address_mode == "informal":
        intro = "Кратко зафиксирую, что мы уже записали:"
    else:
        intro = "Кратко зафиксирую, что мы уже записали:"

    body = format_clinical_card_fields(card)
    combined = f"{intro}\n\n{body}"
    return truncate_words(combined, max_words)


def build_intake_completion_notice(
    address_mode: str,
    initial_info_insufficient: bool,
) -> str:
    """Short scripted follow-up when intake closes (same turn as model reply).

    Args:
        address_mode: "informal" (ты) or "formal" (вы).
        initial_info_insufficient: True when closed on max turns with missing fields.
    """
    if initial_info_insufficient:
        if address_mode == "informal":
            return (
                "На этом заканчиваем первый этап знакомства.\n\n"
                "Что уже записано, можно посмотреть командой /summary.\n\n"
                "Дальше пойдём в обычный разговор — разберёмся с тем, что для тебя важно, "
                "и при необходимости доберём детали по ходу."
            )
        return (
            "На этом мы завершаем первый этап знакомства.\n\n"
            "Что уже записано, можно посмотреть командой /summary.\n\n"
            "Дальше продолжим в обычном формате — вместе проработаем то, что для вас важно, "
            "и при необходимости уточним детали по ходу."
        )

    if address_mode == "informal":
        return (
            "Основную информацию мы собрали.\n\n"
            "Чтобы посмотреть сводку карточки, набери /summary.\n\n"
            "Дальше будем спокойно работать с тем, что тебя сейчас беспокоит."
        )
    return (
        "Основную информацию мы собрали.\n\n"
        "Чтобы посмотреть сводку карточки, введите /summary.\n\n"
        "Дальше будем спокойно работать с тем, что для вас сейчас важно."
    )


def build_intake_start_message(
    patient_name: str,
    address_mode: str,
    therapist_gender: str,
    min_user_turns: int,
    max_user_turns: int,
) -> str:
    """Opening message when starting patient card collection."""
    name_part = f"{patient_name}, " if patient_name else ""
    tg = therapist_gender if therapist_gender in ("female", "male") else "female"
    is_female = tg == "female"
    mog = "могла" if is_female else "мог"
    polezn = "полезной" if is_female else "полезным"
    your_msgs = "твоих сообщений" if address_mode == "informal" else "ваших сообщений"

    if min_user_turns < 1:
        min_user_turns = 1
    if max_user_turns < min_user_turns:
        max_user_turns = min_user_turns

    if min_user_turns == max_user_turns:
        rounds_line = (
            f"На этом этапе заложено {min_user_turns} {your_msgs} в диалоге "
            "для создания клинической карточки."
        )
    else:
        rounds_line = (
            f"На этом этапе заложено от {min_user_turns} до {max_user_turns} "
            f"{your_msgs} в диалоге для создания клинической карточки."
        )

    if address_mode == "informal":
        body = (
            f"{name_part}чтобы я {mog} лучше понимать тебя и эффективнее помогать, "
            "мне нужно собрать некоторую информацию о твоем состоянии. "
            f"Это поможет мне быть более {polezn} в наших беседах.\n\n"
            f"{rounds_line}\n\n"
            "Расскажи, пожалуйста, что сейчас беспокоит тебя больше всего?"
        )
        return body

    body = (
        f"{name_part}чтобы я {mog} лучше понимать вас и эффективнее помогать, "
        "мне нужно собрать некоторую информацию о вашем состоянии. "
        f"Это поможет мне быть более {polezn} в наших беседах.\n\n"
        f"{rounds_line}\n\n"
        "Расскажите, пожалуйста, что сейчас беспокоит вас больше всего?"
    )
    return body


def build_welcome_back_message(
    patient_name: str,
    address_mode: str = "formal",
    therapist_gender: str = "female",
) -> str:
    """Welcome-back message for users with an existing card."""
    name = patient_name or "друг"
    tg = therapist_gender if therapist_gender in ("female", "male") else "female"
    glad = "Рада" if tg == "female" else "Рад"

    if address_mode == "informal":
        return (
            f"Привет, {name}! {glad} тебя видеть. "
            "Расскажи, как прошел твой день?"
        )
    return (
        f"Привет, {name}! {glad} вас видеть. "
        "Расскажите, как прошел ваш день?"
    )
