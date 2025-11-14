"""Payment integration abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class PaymentResult:
    payment_id: str
    confirmation_url: str
    amount: float


class PaymentProvider:
    """Minimalistic abstraction for online payments (e.g. ЮKassa)."""

    def __init__(self, shop_id: Optional[str], api_key: Optional[str]) -> None:
        self.shop_id = shop_id
        self.api_key = api_key

    async def create_payment(self, *, amount: float, description: str, return_url: str) -> PaymentResult:
        # In a real implementation the ЮKassa SDK would be used.
        # Here we return a fake payment that mimics the behaviour.
        payment_id = f"test-{int(amount * 100)}"
        confirmation_url = f"https://yookassa.ru/payments/{payment_id}?return={return_url}"
        return PaymentResult(payment_id=payment_id, confirmation_url=confirmation_url, amount=amount)

    async def capture_payment(self, payment_id: str) -> None:
        # Placeholder for SDK call.
        return None


__all__ = ["PaymentProvider", "PaymentResult"]
