"""Common handlers shared across the bot."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

router = Router()


def _main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Записаться")],
            [KeyboardButton(text="Мои записи"), KeyboardButton(text="Отменить запись")],
            [KeyboardButton(text="Оставить отзыв")],
            [KeyboardButton(text="Акции")],
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Я помогу записаться к специалисту. Выберите действие в меню.",
        reply_markup=_main_menu(),
    )


__all__ = ["router"]
