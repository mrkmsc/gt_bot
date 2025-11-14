"""Entry point for running the Telegram bot."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import BotConfig
from .database import get_sessionmaker, init_engine
from .google_calendar import CalendarConfig, GoogleCalendarService
from .handlers import setup_router
from .notifications import NotificationCallbacks, NotificationService
from .payments import PaymentProvider
from .seed import seed_defaults


async def on_startup(bot: Bot) -> None:
    logging.info("Bot started as %s", await bot.get_me())


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = BotConfig.load()
    await init_engine(config)

    sessionmaker = get_sessionmaker()
    await seed_defaults(sessionmaker)

    bot = Bot(token=config.bot_token, parse_mode="HTML")
    dp = Dispatcher()

    scheduler = AsyncIOScheduler(timezone="UTC")

    async def send_message(chat_id: int, text: str) -> None:
        await bot.send_message(chat_id, text)

    notification_service = NotificationService(
        scheduler,
        NotificationCallbacks(send_message=send_message),
    )
    scheduler.start()

    calendar_service = GoogleCalendarService(
        CalendarConfig(credentials_file=str(config.google_credentials_file) if config.google_credentials_file else None)
    )

    payment_provider = PaymentProvider(config.yookassa_shop_id, config.yookassa_api_key)

    bot["db_sessionmaker"] = sessionmaker
    bot["notification_service"] = notification_service
    bot["payment_provider"] = payment_provider
    bot["google_calendar"] = calendar_service

    dp.include_router(setup_router())
    dp.startup.register(on_startup)

    try:
        await dp.start_polling(bot)
    finally:
        await scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
