"""訂單規則（純函式，不需資料庫）：BR-06、BR-14、BR-16 與 can_* 旗標共用的判斷。"""

from datetime import UTC, datetime, timedelta

import pytest

from app.policies.booking_rules import (
    RescheduleDenial,
    can_cancel,
    can_reschedule,
    can_review,
    reschedule_denial,
    review_window_open,
)
from app.utils.time import whole_hours

NOW = datetime(2026, 11, 2, 2, 30, tzinfo=UTC)
H = timedelta(hours=1)


# ---------- can_cancel ----------
def test_can_cancel_pending_until_deadline_and_confirmed_until_end():
    assert can_cancel("PENDING_PAYMENT", NOW + H, NOW + 5 * H, NOW)
    assert not can_cancel("PENDING_PAYMENT", NOW, NOW + 5 * H, NOW)  # 剛好逾時
    assert can_cancel("CONFIRMED", NOW - H, NOW + H, NOW)
    assert not can_cancel("CONFIRMED", NOW - H, NOW, NOW)  # 剛好結束
    for status in ("CANCELLED", "EXPIRED", "COMPLETED"):
        assert not can_cancel(status, NOW + H, NOW + 5 * H, NOW)


# ---------- 改期（BR-14） ----------
@pytest.mark.parametrize(
    ("status", "lead", "count", "expected"),
    [
        ("CONFIRMED", timedelta(hours=24), 0, None),  # 邊界：剛好 24 小時可以改
        ("CONFIRMED", timedelta(hours=24) - timedelta(seconds=1), 0, RescheduleDenial.TOO_LATE),
        ("CONFIRMED", timedelta(hours=48), 1, RescheduleDenial.LIMIT_REACHED),
        ("PENDING_PAYMENT", timedelta(hours=48), 0, RescheduleDenial.NOT_CONFIRMED),
        ("CANCELLED", timedelta(hours=48), 0, RescheduleDenial.NOT_CONFIRMED),
        # 同時不符合時，依序回報：狀態 → 24 小時 → 次數
        ("PENDING_PAYMENT", timedelta(hours=1), 1, RescheduleDenial.NOT_CONFIRMED),
        ("CONFIRMED", timedelta(hours=1), 1, RescheduleDenial.TOO_LATE),
    ],
)
def test_br14_reschedule_denial(status, lead, count, expected):
    assert reschedule_denial(status, NOW + lead, count, NOW) == expected
    assert can_reschedule(status, NOW + lead, count, NOW) is (expected is None)


# ---------- 評論（BR-16） ----------
def test_br16_review_window_is_30_days_after_end_inclusive():
    end = NOW - timedelta(days=30)
    assert review_window_open(end, NOW)  # 邊界：剛好 30 天
    assert not review_window_open(end - timedelta(seconds=1), NOW)


def test_br16_can_review_requires_completed_and_no_existing_review():
    end = NOW - H
    assert can_review("COMPLETED", end, NOW, has_review=False)
    assert not can_review("COMPLETED", end, NOW, has_review=True)
    assert not can_review("CONFIRMED", end, NOW, has_review=False)
    assert not can_review("COMPLETED", NOW - timedelta(days=31), NOW, has_review=False)


# ---------- 時數 ----------
def test_whole_hours():
    assert whole_hours(NOW, NOW + 2 * H) == 2
    assert whole_hours(NOW, NOW + H) == 1
