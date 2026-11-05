"""Repository 層：集中資料存取（SQL、鎖定、分頁），Service 只看到物件與方法。"""

from .booking_repository import TABS, BookingRepository

__all__ = ["TABS", "BookingRepository"]
