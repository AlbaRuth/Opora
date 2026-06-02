"""Keyboard builders for prescreening flow."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.profile_labels import THERAPIST_STYLES


def build_skip_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="prescreen:skip_name"))
    return builder.as_markup()


def build_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Мужской", callback_data="prescreen:gender:male"),
        InlineKeyboardButton(text="Женский", callback_data="prescreen:gender:female"),
    )
    return builder.as_markup()


def build_patient_sex_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Мужской", callback_data="prescreen:sex:male"),
        InlineKeyboardButton(text="Женский", callback_data="prescreen:sex:female"),
    )
    builder.row(
        InlineKeyboardButton(
            text="Не хочу указывать",
            callback_data="prescreen:sex:prefer_not_to_say",
        )
    )
    return builder.as_markup()


def build_address_mode_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='На «Вы»', callback_data="prescreen:address:formal"),
        InlineKeyboardButton(text='На «Ты»', callback_data="prescreen:address:informal"),
    )
    return builder.as_markup()


def build_styles_keyboard(selected_styles: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for style_id, style_label in THERAPIST_STYLES:
        prefix = "✅ " if style_id in selected_styles else "⬜ "
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{style_label}",
                callback_data=f"prescreen:style:{style_id}",
            )
        )
    if selected_styles:
        builder.row(InlineKeyboardButton(text="✓ Готово", callback_data="prescreen:styles_done"))
    return builder.as_markup()

