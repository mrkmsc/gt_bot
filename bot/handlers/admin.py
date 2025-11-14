"""Handlers for masters and administrators."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..analytics import AnalyticsService
from ..services.booking import BookingService

router = Router()


@router.message(Command("analytics"))
async def master_analytics(message: Message) -> None:
    sessionmaker = message.bot.get("db_sessionmaker")
    async with sessionmaker() as session:
        booking = BookingService(session)
        master = next((m for m in await booking.list_masters() if m.telegram_id == message.from_user.id), None)
        if not master:
            await message.answer("Команда доступна только мастерам. Добавьте свой Telegram ID в настройках.")
            return

        analytics = await AnalyticsService(session).build_master_summary(master)

    avg_rating = f"{analytics.avg_rating:.2f}" if analytics.avg_rating is not None else "нет данных"
    await message.answer(
        "📊 Статистика за последние 30 дней\n"
        f"Всего записей: {analytics.total_appointments}\n"
        f"Выполнено: {analytics.completed_appointments}\n"
        f"Отменено: {analytics.cancelled_appointments}\n"
        f"Средняя оценка: {avg_rating}\n"
        f"Выручка: {analytics.revenue:.2f} ₽"
    )


__all__ = ["router"]
