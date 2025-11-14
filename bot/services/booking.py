"""Business logic for managing appointments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    Appointment,
    AppointmentStatus,
    Customer,
    Master,
    Promotion,
    Service,
)


@dataclass(slots=True)
class AvailableSlot:
    master: Master
    start_time: datetime
    end_time: datetime
    price: float
    promotion: Optional[Promotion] = None


class BookingService:
    """Encapsulates appointment operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_customer(self, telegram_id: int, *, username: Optional[str], full_name: Optional[str]) -> Customer:
        stmt = select(Customer).where(Customer.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        customer = result.scalar_one_or_none()
        if customer is None:
            customer = Customer(telegram_id=telegram_id, username=username, full_name=full_name)
            self.session.add(customer)
            await self.session.flush()
        return customer

    async def list_services(self) -> Iterable[Service]:
        stmt = select(Service).where(Service.active.is_(True)).order_by(Service.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_masters(self) -> Iterable[Master]:
        stmt = select(Master).order_by(Master.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_service(self, service_id: int) -> Service:
        stmt = select(Service).where(Service.id == service_id)
        result = await self.session.execute(stmt)
        service = result.scalar_one_or_none()
        if service is None:
            raise NoResultFound(f"Service {service_id} not found")
        return service

    async def get_master(self, master_id: int) -> Master:
        stmt = select(Master).where(Master.id == master_id)
        result = await self.session.execute(stmt)
        master = result.scalar_one_or_none()
        if master is None:
            raise NoResultFound(f"Master {master_id} not found")
        return master

    async def list_promotions(self, master_id: Optional[int] = None) -> Iterable[Promotion]:
        stmt = select(Promotion).where(Promotion.active.is_(True))
        if master_id:
            stmt = stmt.where(Promotion.master_id == master_id)
        result = await self.session.execute(stmt.order_by(Promotion.discount_percent.desc()))
        return result.scalars().all()

    async def calculate_available_slots(
        self,
        *,
        master: Master,
        service: Service,
        from_time: datetime,
        days_ahead: int = 7,
    ) -> list[AvailableSlot]:
        """Create a simple availability grid based on the master schedule."""

        stmt = select(Appointment).where(
            Appointment.master_id == master.id,
            Appointment.start_time >= from_time,
            Appointment.start_time <= from_time + timedelta(days=days_ahead),
            Appointment.status == AppointmentStatus.CONFIRMED,
        )
        result = await self.session.execute(stmt)
        existing = result.scalars().all()

        busy_intervals = [(appt.start_time, appt.end_time) for appt in existing]
        busy_intervals.sort()

        slots: list[AvailableSlot] = []
        work_start = 9
        work_end = 20
        current_day = from_time.replace(hour=work_start, minute=0, second=0, microsecond=0)
        end_day = from_time + timedelta(days=days_ahead)

        promotions = await self.list_promotions(master.id)
        promotion = promotions[0] if promotions else None

        while current_day < end_day:
            if current_day.weekday() >= 5:  # weekends closed
                current_day += timedelta(days=1)
                current_day = current_day.replace(hour=work_start)
                continue

            slot_end = current_day + timedelta(minutes=service.duration_minutes)
            overlaps = any(start < slot_end and end > current_day for start, end in busy_intervals)
            if not overlaps and current_day >= from_time:
                price = float(service.price)
                if promotion:
                    price = price * (100 - promotion.discount_percent) / 100
                slots.append(AvailableSlot(master=master, start_time=current_day, end_time=slot_end, price=price, promotion=promotion))

            current_day += timedelta(minutes=service.duration_minutes)
            if current_day.hour >= work_end:
                current_day = (current_day + timedelta(days=1)).replace(hour=work_start, minute=0)

        return slots

    async def create_appointment(
        self,
        *,
        customer: Customer,
        master: Master,
        service: Service,
        start_time: datetime,
        promotion: Optional[Promotion] = None,
    ) -> Appointment:
        slots = await self.calculate_available_slots(master=master, service=service, from_time=start_time - timedelta(minutes=service.duration_minutes), days_ahead=1)
        if not any(slot.start_time == start_time for slot in slots):
            raise ValueError("Selected slot is no longer available")

        price = float(service.price)
        if promotion:
            price = price * (100 - promotion.discount_percent) / 100

        appointment = Appointment(
            customer_id=customer.id,
            master_id=master.id,
            service_id=service.id,
            promotion_id=promotion.id if promotion else None,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=service.duration_minutes),
            price=price,
        )
        appointment.customer = customer
        appointment.master = master
        appointment.service = service
        if promotion:
            appointment.promotion = promotion
        self.session.add(appointment)
        await self.session.flush()
        return appointment

    async def cancel_appointment(self, appointment_id: int) -> Appointment:
        stmt = select(Appointment).where(Appointment.id == appointment_id)
        result = await self.session.execute(stmt)
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise NoResultFound("Appointment not found")

        appointment.status = AppointmentStatus.CANCELLED
        await self.session.flush()
        return appointment

    async def list_customer_appointments(self, customer: Customer) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.service),
                selectinload(Appointment.master),
                selectinload(Appointment.feedback),
            )
            .where(Appointment.customer_id == customer.id)
            .order_by(Appointment.start_time.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


__all__ = ["BookingService", "AvailableSlot"]
