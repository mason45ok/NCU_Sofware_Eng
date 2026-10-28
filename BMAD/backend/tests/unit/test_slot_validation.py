"""AvailabilityService.validate_slot：BR-01、BR-02（不需資料庫，用記憶體中的物件）。"""

from datetime import time, timedelta

import pytest

from app.errors import BusinessRuleError
from app.models import Branch, Space
from app.services.availability import AvailabilityService
from app.utils.clock import FixedClock
from tests.conftest import NOW, at


@pytest.fixture
def space():
    branch = Branch(open_time=time(9), close_time=time(22), status="OPEN")
    return Space(branch=branch, status="AVAILABLE")


@pytest.fixture
def service():
    return AvailabilityService(FixedClock(NOW))


def test_br01_valid_slot_passes(service, space):
    service.validate_slot(space, at(1, 10), at(1, 12))


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        (at(1, 10) + timedelta(minutes=30), at(1, 12), "INVALID_TIME_SLOT"),  # 非整點
        (at(1, 12), at(1, 12), "INVALID_TIME_SLOT"),  # 結束不晚於開始
        (at(1, 12), at(1, 10), "INVALID_TIME_SLOT"),
        (at(1, 8), at(1, 10), "OUTSIDE_OPENING_HOURS"),  # 早於營業時間
        (at(1, 21), at(1, 23), "OUTSIDE_OPENING_HOURS"),  # 超過營業時間
        (at(1, 20), at(2, 10), "INVALID_TIME_SLOT"),  # 跨日
    ],
)
def test_br01_invalid_slots(service, space, start, end, code):
    with pytest.raises(BusinessRuleError) as exc:
        service.validate_slot(space, start, end)
    assert exc.value.code == code


def test_br01_closing_hour_boundary_is_allowed(service, space):
    service.validate_slot(space, at(1, 20), at(1, 22))


def test_br02_next_full_hour_boundary(service, space):
    # 現在 10:30，下一個整點 11:00 可預約；10:00 已過
    service.validate_slot(space, at(0, 11), at(0, 12))
    with pytest.raises(BusinessRuleError) as exc:
        service.validate_slot(space, at(0, 10), at(0, 11))
    assert exc.value.code == "OUT_OF_RANGE"


def test_br02_sixty_day_boundary(service, space):
    service.validate_slot(space, at(60, 10), at(60, 12))
    with pytest.raises(BusinessRuleError) as exc:
        service.validate_slot(space, at(61, 10), at(61, 12))
    assert exc.value.code == "OUT_OF_RANGE"
