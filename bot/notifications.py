"""Notification scheduler for reminders and status updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .models import Appointment


@dataclass(slots=True)
class NotificationCallbacks:
    send_message: Callable[[int, str], Awaitable[None]]


class NotificationService:
    def __init__(self, scheduler: AsyncIOScheduler, callbacks: NotificationCallbacks) -> None:
        self.scheduler = scheduler
        self.callbacks = callbacks

    def schedule_reminders(self, appointment: Appointment, chat_id: int) -> None:
        # Reminder 24 hours before
        reminder_time = appointment.start_time - timedelta(hours=24)
        if reminder_time > datetime.utcnow():
            self.scheduler.add_job(
                self.callbacks.send_message,
                "date",
                run_date=reminder_time,
                args=(chat_id, f"Напоминание: запись на {appointment.service.name} {appointment.start_time:%d.%m %H:%M}"),
                id=f"reminder-24-{appointment.id}",
                replace_existing=True,
            )

        # Reminder 1 hour before
        reminder_time = appointment.start_time - timedelta(hours=1)
        if reminder_time > datetime.utcnow():
            self.scheduler.add_job(
                self.callbacks.send_message,
                "date",
                run_date=reminder_time,
                args=(chat_id, f"До визита осталось 1 час. Ваша запись на {appointment.service.name} в {appointment.start_time:%H:%M}"),
                id=f"reminder-1-{appointment.id}",
                replace_existing=True,
            )

    async def notify_status_change(self, appointment: Appointment, chat_id: int) -> None:
        await self.callbacks.send_message(
            chat_id,
            f"Статус вашей записи обновлён: {appointment.status.value}",
        )


__all__ = ["NotificationService", "NotificationCallbacks"]
