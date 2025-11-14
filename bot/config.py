"""Configuration utilities for the Telegram bot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import os


@dataclass(slots=True)
class BotConfig:
    """Runtime configuration for the bot."""

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./bot.db"
    google_credentials_file: Optional[Path] = None
    yookassa_shop_id: Optional[str] = None
    yookassa_api_key: Optional[str] = None
    subscription_price: int = 1990

    @classmethod
    def load(cls) -> "BotConfig":
        load_dotenv()
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN environment variable must be set")

        credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        credentials_path = Path(credentials) if credentials else None

        return cls(
            bot_token=token,
            database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db"),
            google_credentials_file=credentials_path,
            yookassa_shop_id=os.getenv("YOOKASSA_SHOP_ID"),
            yookassa_api_key=os.getenv("YOOKASSA_API_KEY"),
            subscription_price=int(os.getenv("SUBSCRIPTION_PRICE", "1990")),
        )


__all__ = ["BotConfig"]
