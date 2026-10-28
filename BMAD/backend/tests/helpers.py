"""測試用小工具：組請求、建立並付款的訂單、取得資料庫中的最新狀態。"""

from __future__ import annotations

import pytest

from app.errors import AppError
from app.extensions import db
from app.models import Booking
from app.schemas.booking import CreateBookingReq, NewSlot
from tests.conftest import at

CARD_OK = "4242 4242 4242 4242"
CARD_DECLINED = "4000 0000 0000 0002"


def req(space_id: int, day: int = 2, start: int = 10, end: int = 12, attendees: int = 2):
    return CreateBookingReq(
        space_id=space_id, start_at=at(day, start), end_at=at(day, end), attendees=attendees
    )


def slot(day: int, start: int, end: int) -> NewSlot:
    return NewSlot(start_at=at(day, start), end_at=at(day, end))


def booked(services, user, space_id, day=2, start=10, end=12, key=None):
    """建立訂單並付款成功，回傳付款後的 BookingDTO。"""
    created = services.bookings.create(user, req(space_id, day, start, end))
    result = services.bookings.pay(
        user, created.booking_id, "CREDIT_CARD", CARD_OK, key or f"pay-{created.booking_id}"
    )
    assert result.status == "SUCCESS"
    return result.booking


def fresh(booking_id: int) -> Booking:
    """清掉快取後重新從資料庫讀取。"""
    db.session.expire_all()
    return db.session.get(Booking, booking_id)


def error_code(func, *args, **kwargs) -> str:
    """執行並回傳拋出的 AppError 錯誤碼。"""
    with pytest.raises(AppError) as exc:
        func(*args, **kwargs)
    return exc.value.code
