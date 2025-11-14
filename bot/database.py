"""Database utilities built on top of SQLAlchemy."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import BotConfig
from .models import Base

_async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def init_engine(config: BotConfig) -> None:
    """Initialise the database engine and create tables if necessary."""

    global _async_session_maker

    if _async_session_maker is not None:
        return

    engine = create_async_engine(config.database_url, echo=False, future=True)
    _async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _async_session_maker is None:
        raise RuntimeError("Database engine has not been initialised")
    return _async_session_maker


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session_maker = get_sessionmaker()
    session = session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


__all__ = ["init_engine", "session_scope", "get_sessionmaker"]
