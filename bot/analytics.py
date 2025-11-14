"""Analytics helpers for masters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Appointment, AppointmentStatus, Feedback, Master


@dataclass(slots=True)
class AnalyticsSummary:
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    avg_rating: float | None
    revenue: float


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_master_summary(self, master: Master, *, days: int = 30) -> AnalyticsSummary:
        since = datetime.utcnow() - timedelta(days=days)

        stmt_total = select(func.count()).select_from(Appointment).where(Appointment.master_id == master.id, Appointment.start_time >= since)
        total = await self.session.scalar(stmt_total) or 0

        stmt_completed = select(func.count()).select_from(Appointment).where(
            Appointment.master_id == master.id,
            Appointment.start_time >= since,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        completed = await self.session.scalar(stmt_completed) or 0

        stmt_cancelled = select(func.count()).select_from(Appointment).where(
            Appointment.master_id == master.id,
            Appointment.start_time >= since,
            Appointment.status == AppointmentStatus.CANCELLED,
        )
        cancelled = await self.session.scalar(stmt_cancelled) or 0

        stmt_rating = (
            select(func.avg(Feedback.rating))
            .join(Appointment, Feedback.appointment_id == Appointment.id)
            .where(Appointment.master_id == master.id, Appointment.start_time >= since)
        )
        avg_rating = await self.session.scalar(stmt_rating)

        stmt_revenue = select(func.sum(Appointment.price)).where(
            Appointment.master_id == master.id,
            Appointment.start_time >= since,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        revenue = await self.session.scalar(stmt_revenue) or 0.0

        return AnalyticsSummary(
            total_appointments=int(total),
            completed_appointments=int(completed),
            cancelled_appointments=int(cancelled),
            avg_rating=float(avg_rating) if avg_rating is not None else None,
            revenue=float(revenue),
        )


__all__ = ["AnalyticsService", "AnalyticsSummary"]
