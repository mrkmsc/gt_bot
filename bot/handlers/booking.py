"""Handlers implementing the booking flow."""

from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ..google_calendar import GoogleCalendarService
from ..models import AppointmentStatus
from ..notifications import NotificationService
from ..payments import PaymentProvider
from ..promotions import PromotionService
from ..services.booking import BookingService

router = Router()


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_master = State()
    choosing_slot = State()
    confirming = State()


def _service_keyboard(services) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in services:
        builder.button(text=service.name, callback_data=f"booking:service:{service.id}")
    builder.adjust(1)
    return builder.as_markup()


def _master_keyboard(masters) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for master in masters:
        builder.button(text=master.name, callback_data=f"booking:master:{master.id}")
    builder.adjust(1)
    return builder.as_markup()


def _slots_keyboard(slots) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots[:10]:
        label = slot.start_time.strftime("%d.%m %H:%M")
        if slot.promotion:
            label += f" (-{slot.promotion.discount_percent}%)"
        builder.button(text=label, callback_data=f"booking:slot:{slot.start_time.isoformat()}")
    builder.adjust(1)
    return builder.as_markup()


@router.message(F.text == "Записаться")
async def start_booking(message: Message, state: FSMContext) -> None:
    sessionmaker = message.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        booking = BookingService(session)
        services = await booking.list_services()
    if not services:
        await message.answer("Список услуг пуст. Обратитесь к администратору.")
        return
    await state.set_state(BookingStates.choosing_service)
    await message.answer("Выберите услугу", reply_markup=_service_keyboard(services))


@router.callback_query(BookingStates.choosing_service, F.data.startswith("booking:service"))
async def choose_master(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, service_id = callback.data.split(":")
    sessionmaker = callback.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        booking = BookingService(session)
        service = await booking.get_service(int(service_id))
        masters = await booking.list_masters()
    await state.update_data(service_id=service.id)
    await state.set_state(BookingStates.choosing_master)
    await callback.message.edit_text(
        f"Услуга: {service.name}. Выберите мастера.",
        reply_markup=_master_keyboard(masters),
    )
    await callback.answer()


@router.message(F.text == "Мои записи")
async def list_appointments(message: Message) -> None:
    sessionmaker = message.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        booking = BookingService(session)
        customer = await booking.get_or_create_customer(
            message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        appointments = await booking.list_customer_appointments(customer)

    if not appointments:
        await message.answer("У вас пока нет записей.")
        return

    lines = ["Ваши записи:"]
    for appointment in appointments:
        status = "✅" if appointment.status == AppointmentStatus.CONFIRMED else "❌"
        lines.append(
            f"{status} {appointment.service.name} у {appointment.master.name} — {appointment.start_time:%d.%m %H:%M}"
        )
    await message.answer("\n".join(lines))


@router.message(F.text == "Отменить запись")
async def ask_cancel(message: Message) -> None:
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
            if appt.status == AppointmentStatus.CONFIRMED
        ]

    if not appointments:
        await message.answer("Нет активных записей для отмены.")
        return

    builder = InlineKeyboardBuilder()
    for appt in appointments:
        label = f"{appt.service.name} {appt.start_time:%d.%m %H:%M}"
        builder.button(text=label, callback_data=f"booking:cancel_appointment:{appt.id}")
    builder.adjust(1)
    await message.answer("Выберите запись для отмены", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("booking:cancel_appointment"))
async def cancel_appointment(callback: CallbackQuery) -> None:
    _, _, appointment_id = callback.data.split(":")
    sessionmaker = callback.bot.get("db_sessionmaker")
    notification_service: NotificationService = callback.bot.get("notification_service")
    calendar_service: GoogleCalendarService | None = callback.bot.get("google_calendar")

    async with sessionmaker() as session:
        booking = BookingService(session)
        appointment = await booking.cancel_appointment(int(appointment_id))
        await session.refresh(appointment, attribute_names=["service", "master"])
        await session.commit()

    if calendar_service and appointment.master.google_calendar_id:
        calendar_service.delete_event(appointment.master.google_calendar_id, f"appointment-{appointment.id}")

    await notification_service.notify_status_change(appointment, callback.from_user.id)
    await callback.message.edit_text("Запись отменена")
    await callback.answer()


@router.message(F.text == "Акции")
async def show_promotions(message: Message) -> None:
    sessionmaker = message.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        promotions = await PromotionService(session).list_active()

    if not promotions:
        await message.answer("Сейчас нет активных акций.")
        return

    lines = ["Текущие акции:"]
    for promo in promotions:
        lines.append(
            f"💡 {promo.name} — скидка {promo.discount_percent}% (группа: {promo.client_group or 'все клиенты'})"
        )
    await message.answer("\n".join(lines))


@router.callback_query(BookingStates.choosing_master, F.data.startswith("booking:master"))
async def choose_slot(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, master_id = callback.data.split(":")
    data = await state.get_data()
    sessionmaker = callback.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        booking = BookingService(session)
        service = await booking.get_service(int(data["service_id"]))
        master = await booking.get_master(int(master_id))
        slots = await booking.calculate_available_slots(master=master, service=service, from_time=datetime.utcnow())
    if not slots:
        await callback.answer("Нет свободных слотов", show_alert=True)
        return
    await state.update_data(master_id=master.id)
    await state.set_state(BookingStates.choosing_slot)
    await callback.message.edit_text(
        f"Выбран мастер: {master.name}. Выберите время.",
        reply_markup=_slots_keyboard(slots),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_slot, F.data.startswith("booking:slot"))
async def confirm_slot(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, iso_dt = callback.data.split(":")
    start_time = datetime.fromisoformat(iso_dt)
    await state.update_data(start_time=iso_dt)
    await state.set_state(BookingStates.confirming)
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data="booking:confirm")
    builder.button(text="Отмена", callback_data="booking:cancel")
    builder.adjust(1)
    await callback.message.edit_text(
        f"Подтверждаете запись на {start_time:%d.%m %H:%M}?",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(BookingStates.confirming, F.data == "booking:cancel")
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer("Запись отменена.")
    await callback.answer()


@router.callback_query(BookingStates.confirming, F.data == "booking:confirm")
async def finalize_booking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    sessionmaker = callback.bot.get("db_sessionmaker")
    payment_provider: PaymentProvider = callback.bot.get("payment_provider")
    notification_service: NotificationService = callback.bot.get("notification_service")
    calendar_service: GoogleCalendarService | None = callback.bot.get("google_calendar")

    async with sessionmaker() as session:
        booking = BookingService(session)
        customer = await booking.get_or_create_customer(
            callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
        )
        service = await booking.get_service(int(data["service_id"]))
        master = await booking.get_master(int(data["master_id"]))
        start_time = datetime.fromisoformat(data["start_time"])
        promotions = await booking.list_promotions(master.id)
        promotion = promotions[0] if promotions else None
        appointment = await booking.create_appointment(
            customer=customer,
            master=master,
            service=service,
            start_time=start_time,
            promotion=promotion,
        )
        await session.commit()

    # Sync with Google Calendar when configured
    if calendar_service and master.google_calendar_id:
        calendar_service.ensure_event(
            master.google_calendar_id,
            event_id=f"appointment-{appointment.id}",
            summary=f"{service.name} — {customer.full_name or customer.username}",
            start=start_time,
            end=appointment.end_time,
        )

    # Payment link (optional)
    payment = await payment_provider.create_payment(
        amount=float(appointment.price),
        description=f"Оплата услуги {service.name}",
        return_url="https://t.me/your_bot",
    )

    notification_service.schedule_reminders(appointment, callback.from_user.id)

    await callback.message.edit_text(
        "Запись подтверждена! \n"
        f"Услуга: {service.name}\n"
        f"Мастер: {master.name}\n"
        f"Дата: {start_time:%d.%m %H:%M}\n"
        f"Сумма к оплате: {appointment.price} ₽\n"
        f"Ссылка для оплаты: {payment.confirmation_url}",
    )
    await callback.answer()


__all__ = ["router"]
