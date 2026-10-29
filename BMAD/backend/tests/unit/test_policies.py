"""PricingPolicy、RefundPolicy 的邊界值（純函式，不需資料庫）。BR-07、12、13、14。"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.policies import pricing, refund

NOW = datetime(2026, 11, 2, 2, 30, tzinfo=UTC)


def test_br07_amount_is_hourly_price_times_hours():
    assert pricing.amount(300, 2) == 600
    assert pricing.amount(1200, 1) == 1200


@pytest.mark.parametrize(
    ("old_hours", "new_hours", "diff"), [(2, 3, 300), (3, 2, -300), (2, 2, 0), (1, 4, 900)]
)
def test_br14_reschedule_diff_uses_snapshot(old_hours, new_hours, diff):
    assert pricing.reschedule_diff(300, old_hours, new_hours) == diff


@pytest.mark.parametrize(
    ("lead", "ratio"),
    [
        (timedelta(hours=48), "1"),
        (timedelta(hours=24), "1"),  # 邊界：剛好 24 小時 → 100%
        (timedelta(hours=24) - timedelta(seconds=1), "0.5"),
        (timedelta(hours=3), "0.5"),  # 邊界：剛好 3 小時 → 50%
        (timedelta(hours=3) - timedelta(seconds=1), "0"),
        (timedelta(0), "0"),
        (timedelta(hours=-1), "0"),
    ],
)
def test_br12_member_ratio_boundaries(lead, ratio):
    assert refund.member_ratio(NOW + lead, NOW) == Decimal(ratio)


def test_br13_admin_ratio_is_full():
    assert refund.admin_ratio() == Decimal(1)


@pytest.mark.parametrize(
    ("net_paid", "ratio", "expected"),
    [(600, "1", 600), (600, "0.5", 300), (601, "0.5", 301), (0, "1", 0), (600, "0", 0)],
)
def test_br12_refund_amount_rounds_half_up(net_paid, ratio, expected):
    assert refund.refund_amount(net_paid, Decimal(ratio)) == expected
