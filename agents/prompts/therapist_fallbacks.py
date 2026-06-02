"""Fallback helpers for therapist prompts."""

from __future__ import annotations


def build_therapist_fallback_response(
    language: str = "ru",
    address_mode: str = "formal",
) -> str:
    if language == "ru" or language == "russian":
        if address_mode == "informal":
            return "Извини, я временно не могу обработать твой запрос. Пожалуйста, попробуй еще раз."
        return "Извините, я временно не могу обработать ваш запрос. Пожалуйста, попробуйте еще раз."
    return "Sorry, I'm temporarily unable to process your request, please try again."

