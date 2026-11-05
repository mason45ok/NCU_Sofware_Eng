"""BookingRepository 整合測試（實際 PostgreSQL）：查詢、分頁、鎖定與序號。FR-30、BR-06、BR-08、FR-50、FR-51。"""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Booking
from app.repositories import TABS, BookingRepository
from tests.conftest import at
from tests.helpers import booked, req

pytestmark = pytest.mark.usefixtures("db_clean")
repo = BookingRepository()


def test_get_and_get_locked_return_none_for_missing_booking():
    assert repo.get(999) is None
    assert repo.get_locked(999) is None


def test_fr30_list_by_tab_splits_and_paginates(services, make_user, space_id, clock):
    user = make_user()
    for day in (2, 3, 4):
        booked(services, user, space_id, day=day)
    services.bookings.create(user, req(space_id, day=6, start=10, end=12))  # 一筆待付款

    now = clock.now()
    upcoming, total = repo.list_by_tab(user.user_id, "upcoming", now, page=1, page_size=2)
    assert total == 3 and len(upcoming) == 2
    assert upcoming[0].start_at < upcoming[1].start_at  # 即將到來：由近到遠
    rest, _ = repo.list_by_tab(user.user_id, "upcoming", now, page=2, page_size=2)
    assert len(rest) == 1
    assert repo.list_by_tab(user.user_id, "pending", now, 1, 10)[1] == 1
    assert repo.list_by_tab(user.user_id, "closed", now, 1, 10)[1] == 0
    assert set(TABS) == {"pending", "upcoming", "completed", "closed"}


def test_fr30_list_by_tab_only_returns_own_bookings(services, make_user, space_id, clock):
    mine, other = make_user(), make_user("other@test.local")
    booked(services, other, space_id)
    assert repo.list_by_tab(mine.user_id, "upcoming", clock.now(), 1, 10) == ([], 0)


def test_br06_count_pending_ignores_overdue_and_confirmed(services, make_user, space_id, clock):
    user = make_user()
    booked(services, user, space_id, day=2)
    services.bookings.create(user, req(space_id, day=3))
    assert repo.count_pending(user.user_id, clock.now()) == 1
    assert repo.count_pending(user.user_id, clock.now() + timedelta(minutes=16)) == 0


def test_br08_lock_overdue_pending_finds_only_expired(services, make_user, space_id, clock):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    assert repo.lock_overdue_pending(clock.now()) == []
    later = clock.now() + timedelta(minutes=16)
    assert [b.booking_id for b in repo.lock_overdue_pending(later)] == [created.booking_id]
    assert [b.booking_id for b in repo.lock_overdue_pending_for(user.user_id, 0, later)] == [
        created.booking_id
    ]


def test_fr51_lock_finished_finds_confirmed_bookings_past_end(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, day=2)
    assert repo.lock_finished(dto.start_at) == []
    assert [b.booking_id for b in repo.lock_finished(dto.end_at)] == [dto.booking_id]


def test_has_slot_conflict_ignores_self_and_adjacent_slots(services, make_user, space_id, clock):
    user = make_user()
    first = booked(services, user, space_id, day=2, start=10, end=12)
    second = booked(services, user, space_id, day=2, start=14, end=16)
    other = db.session.get(Booking, second.booking_id)
    now = clock.now()
    assert repo.has_slot_conflict(other, first.start_at, first.end_at, now)  # 與第一筆重疊
    assert not repo.has_slot_conflict(other, at(2, 12), at(2, 14), now)  # 相鄰不算重疊（BR-03）
    own = db.session.get(Booking, first.booking_id)
    assert not repo.has_slot_conflict(own, first.start_at, first.end_at, now)  # 不與自己衝突


def test_list_active_in_spaces_returns_future_active_bookings(services, make_user, space_id, clock):
    user = make_user()
    dto = booked(services, user, space_id, day=2)
    rows = repo.list_active_in_spaces([space_id], clock.now())
    assert [b.booking_id for b in rows] == [dto.booking_id]
    assert repo.list_active_in_spaces([space_id], dto.end_at) == []


def test_next_id_is_increasing():
    first = repo.next_id()
    assert repo.next_id() > first
