"""訂單規則：誰能做什麼的判斷與門檻（純函式，不碰資料庫）。

同一套規則只在這裡寫一份：畫面用的 can_* 旗標與實際執行時的檢查共用同一個判斷，
不會出現「按鈕可按、送出卻被拒」或相反的不一致。
"""

from datetime import datetime, timedelta
from enum import StrEnum

from ..models.enums import BookingStatus

PENDING_LIMIT = 3  # BR-06：同一會員最多 3 筆待付款
RESCHEDULE_MIN_LEAD = timedelta(hours=24)  # BR-14：開始前 24 小時內不可改期
MAX_RESCHEDULES = 1  # BR-14：每筆訂單最多改期 1 次
REVIEW_WINDOW = timedelta(days=30)  # BR-16：結束後 30 天內可評論


class RescheduleDenial(StrEnum):
    NOT_CONFIRMED = "NOT_CONFIRMED"
    TOO_LATE = "TOO_LATE"
    LIMIT_REACHED = "LIMIT_REACHED"


def can_cancel(status: str, expires_at: datetime, end_at: datetime, now: datetime) -> bool:
    """待付款且未逾時，或已確認且尚未結束。"""
    if status == BookingStatus.PENDING_PAYMENT:
        return expires_at > now
    return status == BookingStatus.CONFIRMED and end_at > now


def reschedule_denial(
    status: str, start_at: datetime, reschedule_count: int, now: datetime
) -> RescheduleDenial | None:
    """會員改期被拒絕的原因；None 表示可以改期。依序檢查：狀態、24 小時、次數。"""
    if status != BookingStatus.CONFIRMED:
        return RescheduleDenial.NOT_CONFIRMED
    if start_at - now < RESCHEDULE_MIN_LEAD:
        return RescheduleDenial.TOO_LATE
    if reschedule_count >= MAX_RESCHEDULES:
        return RescheduleDenial.LIMIT_REACHED
    return None


def can_reschedule(status: str, start_at: datetime, reschedule_count: int, now: datetime) -> bool:
    return reschedule_denial(status, start_at, reschedule_count, now) is None


def review_window_open(end_at: datetime, now: datetime) -> bool:
    return now <= end_at + REVIEW_WINDOW


def can_review(status: str, end_at: datetime, now: datetime, has_review: bool) -> bool:
    return status == BookingStatus.COMPLETED and not has_review and review_window_open(end_at, now)
