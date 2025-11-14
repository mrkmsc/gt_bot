"""Handlers related to collecting feedback."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..models import AppointmentStatus
from ..services.booking import BookingService
from ..services.feedback import FeedbackService

router = Router()


class FeedbackStates(StatesGroup):
    choosing_appointment = State()
    entering_rating = State()
    entering_comment = State()


@router.message(F.text == "Оставить отзыв")
async def start_feedback(message: Message, state: FSMContext) -> None:
    sessionmaker = message.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        booking = BookingService(session)
        customer = await booking.get_or_create_customer(
            message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        appointments = [
            appt
            for appt in await booking.list_customer_appointments(customer)
            if appt.status == AppointmentStatus.COMPLETED and appt.feedback is None
        ]

    if not appointments:
        await message.answer("Нет завершённых записей без отзыва.")
        return

    builder = InlineKeyboardBuilder()
    for appointment in appointments:
        builder.button(
            text=f"{appointment.service.name} {appointment.start_time:%d.%m}",
            callback_data=f"feedback:select:{appointment.id}",
        )
    builder.adjust(1)

    await state.set_state(FeedbackStates.choosing_appointment)
    await message.answer("Выберите визит для отзыва", reply_markup=builder.as_markup())


@router.callback_query(FeedbackStates.choosing_appointment, F.data.startswith("feedback:select"))
async def choose_rating(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, appointment_id = callback.data.split(":")
    await state.update_data(appointment_id=int(appointment_id))
    await state.set_state(FeedbackStates.entering_rating)
    await callback.message.edit_text("Оцените визит по шкале от 1 до 5")
    await callback.answer()


@router.message(FeedbackStates.entering_rating, F.text.regexp(r"^[1-5]$"))
async def capture_rating(message: Message, state: FSMContext) -> None:
    await state.update_data(rating=int(message.text))
    await state.set_state(FeedbackStates.entering_comment)
    await message.answer("Напишите короткий отзыв (можно пропустить, отправив -)")


@router.message(FeedbackStates.entering_rating)
async def invalid_rating(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте число от 1 до 5")


@router.message(FeedbackStates.entering_comment)
async def finalize_feedback(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    comment = None if message.text == "-" else message.text

    sessionmaker = message.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        feedback_service = FeedbackService(session)
        await feedback_service.add_feedback(data["appointment_id"], data["rating"], comment)
        await session.commit()

    await state.clear()
    await message.answer("Спасибо за отзыв!")


__all__ = ["router"]
