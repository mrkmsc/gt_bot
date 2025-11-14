"""Subscription management for selling the bot as a service."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Master, Subscription


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_active(self, master: Master, *, level: str, duration_days: int = 30) -> Subscription:
        now = datetime.utcnow()
        stmt = select(Subscription).where(Subscription.master_id == master.id).order_by(Subscription.valid_until.desc())
        result = await self.session.execute(stmt)
        subscription = result.scalars().first()

        if subscription and subscription.valid_until > now:
            subscription.valid_until += timedelta(days=duration_days)
            await self.session.flush()
            return subscription

        subscription = Subscription(
            master_id=master.id,
            level=level,
            valid_until=now + timedelta(days=duration_days),
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def has_active(self, master: Master) -> bool:
        now = datetime.utcnow()
        stmt = select(Subscription).where(Subscription.master_id == master.id, Subscription.valid_until >= now)
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None


__all__ = ["SubscriptionService"]
