"""AccessCodeService：房間密碼（模擬門禁）。有效性在查詢時即時判斷（BR-11）。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete

from ..errors import NotFoundError
from ..extensions import db
from ..models import AccessCode, AccessCodeState, Booking
from ..schemas.booking import AccessCodeView
from ..security.tokens import new_access_code
from ..utils.clock import Clock

LEAD = timedelta(minutes=10)


class AccessCodeService:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def issue(self, booking: Booking) -> None:
        """付款成功時產生；有效期間為開始前 10 分鐘至結束。"""
        booking.access_code = AccessCode(
            code=new_access_code(),
            valid_from=booking.start_at - LEAD,
            valid_until=booking.end_at,
        )
        db.session.flush()

    def sync_validity(self, booking: Booking) -> None:
        """改期後同步有效時間（密碼不變）。"""
        code = booking.access_code
        if code is not None:
            code.valid_from = booking.start_at - LEAD
            code.valid_until = booking.end_at

    def revoke(self, booking: Booking) -> None:
        code = booking.access_code
        if code is not None and code.revoked_at is None:
            code.revoked_at = self.clock.now()

    def view(self, booking: Booking) -> AccessCodeView | None:
        code = booking.access_code
        if code is None:
            return None
        state = code.state(self.clock.now())
        return AccessCodeView(
            state=state.value,
            code=code.code if state == AccessCodeState.VALID else None,
            valid_from=code.valid_from,
            valid_until=code.valid_until,
        )

    def view_for_owner(self, user_id: int, booking_id: int) -> AccessCodeView | None:
        booking = db.session.get(Booking, booking_id)
        if booking is None or booking.user_id != user_id:
            raise NotFoundError()
        return self.view(booking)

    def purge_expired(self) -> int:
        """排程：刪除 valid_until 超過 7 天的房間密碼（冪等）。"""
        cutoff = self.clock.now() - timedelta(days=7)
        res = db.session.execute(delete(AccessCode).where(AccessCode.valid_until < cutoff))
        db.session.commit()
        return res.rowcount
