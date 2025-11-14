"""Feedback management."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Appointment, Feedback


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_feedback(self, appointment_id: int, rating: int, comment: str | None) -> Feedback:
        stmt = select(Appointment).where(Appointment.id == appointment_id)
        appointment = (await self.session.execute(stmt)).scalar_one()
        feedback = Feedback(appointment_id=appointment.id, rating=rating, comment=comment)
        self.session.add(feedback)
        await self.session.flush()
        return feedback


__all__ = ["FeedbackService"]
