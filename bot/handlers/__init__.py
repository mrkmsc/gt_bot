"""Router aggregation for the bot."""

from __future__ import annotations

from aiogram import Router

from . import admin, booking, common, feedback

__all__ = ["admin", "booking", "common", "feedback", "setup_router"]


def setup_router() -> Router:
    router = Router()
    router.include_router(common.router)
    router.include_router(booking.router)
    router.include_router(feedback.router)
    router.include_router(admin.router)
    return router
