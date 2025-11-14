"""Promotion helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Promotion


class PromotionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[Promotion]:
        stmt = select(Promotion).where(Promotion.active.is_(True)).order_by(Promotion.discount_percent.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


__all__ = ["PromotionService"]
