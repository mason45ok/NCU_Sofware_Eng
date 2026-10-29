"""AvailabilityService：可預約時段計算與時段驗證（BR-01、02；D11）。

只用於顯示與事前驗證；真正防止重疊的是資料庫排除約束 ex_bookings_no_overlap。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select

from ..errors import BusinessRuleError, NotFoundError
from ..extensions import db
from ..models import Booking, Space
from ..schemas.catalog import AvailabilityDTO, Slot
from ..utils.clock import Clock
from ..utils.time import day_hour, local_date, next_full_hour, to_taipei

MAX_DAYS = 60


class AvailabilityService:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def validate_slot(self, space: Space, start_at: datetime, end_at: datetime) -> None:
        """整點、同一天、營業時間內（BR-01），下一個整點起 60 天內（BR-02）。"""
        for t in (start_at, end_at):
            if t.minute != 0 or t.second != 0 or t.microsecond != 0:
                raise BusinessRuleError("INVALID_TIME_SLOT")
        if end_at <= start_at or local_date(start_at) != local_date(end_at - timedelta(seconds=1)):
            raise BusinessRuleError("INVALID_TIME_SLOT")
        open_at, close_at = space.branch.opening_range(local_date(start_at))
        if start_at < open_at or end_at > close_at:
            raise BusinessRuleError("OUTSIDE_OPENING_HOURS")
        now = self.clock.now()
        last_day = local_date(now) + timedelta(days=MAX_DAYS)
        if start_at < next_full_hour(now) or local_date(start_at) > last_day:
            raise BusinessRuleError("OUT_OF_RANGE")

    def slots_for(self, space: Space, local_day: date) -> list[Slot]:
        """D11：營業時間內每個整點時段的狀態（呼叫端已確認空間可預約與日期範圍）。"""
        now = self.clock.now()
        open_at, close_at = space.branch.opening_range(local_day)
        busy = (
            db.session.execute(
                select(Booking.start_at, Booking.end_at).where(
                    Booking.space_id == space.space_id,
                    Booking.occupying(now),
                    Booking.start_at < close_at,
                    Booking.end_at > open_at,
                )
            )
            .tuples()
            .all()
        )
        earliest = next_full_hour(now)
        slots: list[Slot] = []
        for hour in range(to_taipei(open_at).hour, to_taipei(close_at).hour):
            s, e = day_hour(local_day, hour), day_hour(local_day, hour + 1)
            if s < earliest:
                status = "PAST"
            elif any(b_start < e and b_end > s for b_start, b_end in busy):
                status = "BOOKED"
            else:
                status = "AVAILABLE"
            slots.append(Slot(start=hour, end=hour + 1, start_at=s, end_at=e, status=status))
        return slots

    def availability(self, space_id: int, local_day: date) -> AvailabilityDTO:
        """FR-14：公開 API 用，不含預約者資訊。"""
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        open_hour = space.branch.open_time.hour
        close_hour = space.branch.close_time.hour
        base = dict(
            space_id=space_id,
            date=local_day,
            open_hour=open_hour,
            close_hour=close_hour,
            slots=[],
        )
        if not space.is_bookable():
            return AvailabilityDTO(bookable=False, reason="UNAVAILABLE", **base)
        today = local_date(self.clock.now())
        if local_day < today or local_day > today + timedelta(days=MAX_DAYS):
            return AvailabilityDTO(bookable=False, reason="OUT_OF_RANGE", **base)
        base["slots"] = self.slots_for(space, local_day)
        return AvailabilityDTO(bookable=True, **base)
