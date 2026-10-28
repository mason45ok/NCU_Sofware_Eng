"""AdminBookingService：訂單查詢與後台首頁數字（只做查詢，不寫入任何資料；FR-44）。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_, func, or_, select

from ..errors import NotFoundError
from ..extensions import db
from ..models import (
    Booking,
    BookingStatus,
    BookingStatusLog,
    Branch,
    NotificationLog,
    SendStatus,
    Space,
    SpaceStatus,
    User,
)
from ..schemas.admin import (
    AdminBookingDetail,
    AdminSummary,
    BookingFilters,
    NotificationDTO,
    StatusLogDTO,
)
from ..schemas.base import Page
from ..schemas.booking import BookingDTO
from ..utils.clock import Clock
from ..utils.time import day_hour, local_date
from .booking import BookingService


class AdminBookingService:
    def __init__(self, clock: Clock, bookings: BookingService) -> None:
        self.clock = clock
        self.bookings = bookings

    def search(self, f: BookingFilters) -> Page[BookingDTO]:
        stmt = select(Booking).join(User, User.user_id == Booking.user_id)
        if f.no:
            stmt = stmt.where(Booking.booking_no.ilike(f"%{f.no}%"))
        if f.email:
            stmt = stmt.where(User.email.ilike(f"%{f.email}%"))
        if f.space_id:
            stmt = stmt.where(Booking.space_id == f.space_id)
        if f.status:
            stmt = stmt.where(Booking.status == f.status)
        if f.date_from:
            stmt = stmt.where(Booking.end_at > day_hour(f.date_from, 0))
        if f.date_to:
            stmt = stmt.where(Booking.start_at < day_hour(f.date_to, 24))
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            db.session.execute(
                stmt.order_by(Booking.booking_id.desc())
                .limit(f.page_size)
                .offset((f.page - 1) * f.page_size)
            )
            .scalars()
            .all()
        )
        return Page[BookingDTO](
            items=[self.bookings.to_dto(b) for b in rows],
            page=f.page,
            page_size=f.page_size,
            total=total,
        )

    def detail(self, booking_id: int) -> AdminBookingDetail:
        booking = db.session.get(Booking, booking_id)
        if booking is None:
            raise NotFoundError()
        logs = db.session.execute(
            select(BookingStatusLog)
            .where(BookingStatusLog.booking_id == booking_id)
            .order_by(BookingStatusLog.log_id)
        ).scalars()
        notifications = db.session.execute(
            select(NotificationLog)
            .where(NotificationLog.booking_id == booking_id)
            .order_by(NotificationLog.notification_id)
        ).scalars()
        return AdminBookingDetail(
            booking=self.bookings.to_dto(booking),
            logs=[StatusLogDTO.model_validate(x) for x in logs],
            notifications=[NotificationDTO.model_validate(x) for x in notifications],
        )

    def summary(self) -> AdminSummary:
        """後台首頁：今日訂單數、受停用影響的未來訂單、寄送失敗通知。"""
        now = self.clock.now()
        today = local_date(now)
        start, end = day_hour(today, 0), day_hour(today, 24) + timedelta(0)
        today_count = db.session.scalar(
            select(func.count()).where(
                Booking.start_at >= start,
                Booking.start_at < end,
                Booking.status.in_(
                    [
                        BookingStatus.PENDING_PAYMENT.value,
                        BookingStatus.CONFIRMED.value,
                        BookingStatus.COMPLETED.value,
                    ]
                ),
            )
        )
        affected = db.session.scalar(
            select(func.count())
            .select_from(Booking)
            .join(Space, Space.space_id == Booking.space_id)
            .join(Branch, Branch.branch_id == Space.branch_id)
            .where(
                Booking.end_at > now,
                or_(Space.status != SpaceStatus.AVAILABLE.value, Branch.status != "OPEN"),
                or_(
                    Booking.status == BookingStatus.CONFIRMED.value,
                    and_(
                        Booking.status == BookingStatus.PENDING_PAYMENT.value,
                        Booking.expires_at > now,
                    ),
                ),
            )
        )
        failed = db.session.scalar(
            select(func.count()).where(NotificationLog.status == SendStatus.FAILED.value)
        )
        return AdminSummary(
            today_bookings=today_count,
            pending_affected_bookings=affected,
            failed_notifications=failed,
        )
