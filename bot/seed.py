"""Utility helpers to bootstrap the database with sample data."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from .models import Master, Promotion, Service


async def seed_defaults(sessionmaker: async_sessionmaker) -> None:
    async with sessionmaker() as session:
        services_count = await session.scalar(select(func.count()).select_from(Service))
        masters_count = await session.scalar(select(func.count()).select_from(Master))

        if services_count == 0:
            session.add_all(
                [
                    Service(name="Стрижка", description="Модельная стрижка", duration_minutes=60, price=1500),
                    Service(name="Окрашивание", description="Полное окрашивание", duration_minutes=120, price=3500),
                    Service(name="Укладка", description="Укладка волос", duration_minutes=45, price=1200),
                ]
            )

        if masters_count == 0:
            session.add_all(
                [
                    Master(name="Анна", specialization="Парикмахер"),
                    Master(name="Мария", specialization="Колорист"),
                ]
            )

        await session.commit()

    # create promotions separately to ensure master ids exist
    async with sessionmaker() as session:
        promotions_count = await session.scalar(select(func.count()).select_from(Promotion))
        if promotions_count == 0:
            master = (await session.execute(select(Master))).scalars().first()
            if master:
                session.add(
                    Promotion(
                        master_id=master.id,
                        name="-10% на первую запись",
                        description="Скидка для новых клиентов",
                        discount_percent=10,
                        client_group="новые",
                        active=True,
                    )
                )
                await session.commit()


__all__ = ["seed_defaults"]
