"""建立訂單與時段規則（BR-01～08；ARCHITECTURE.md 6.1）。使用實際 PostgreSQL。"""

from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Space
from app.utils.time import local_date
from tests.conftest import NOW
from tests.helpers import booked, error_code, fresh, req

pytestmark = pytest.mark.usefixtures("db_clean")


def test_fr21_create_success_snapshots_price_and_deadline(services, make_user, space_id):
    user = make_user()
    dto = services.bookings.create(user, req(space_id, 2, 10, 12))
    assert dto.status == "PENDING_PAYMENT"
    assert dto.hours == 2 and dto.hourly_price_snapshot == 300 and dto.total_amount == 600
    assert dto.expires_at == NOW + timedelta(minutes=15)  # BR-08
    assert dto.booking_no.startswith("B20261102-")
    assert [log.action for log in fresh(dto.booking_id).logs] == ["CREATE"]  # BR-25


def test_br07_price_change_does_not_affect_existing_booking(services, make_user, space_id):
    user = make_user()
    dto = services.bookings.create(user, req(space_id))
    db.session.get(Space, space_id).hourly_price = 999
    db.session.commit()
    assert services.bookings.get_for_owner(user, dto.booking_id).total_amount == 600


def test_br07_quote_matches_create(services, make_user, space_id):
    user = make_user()
    quote = services.bookings.quote(user, req(space_id, 2, 10, 13))
    created = services.bookings.create(user, req(space_id, 2, 10, 13))
    assert quote.total_amount == created.total_amount == 900


def test_br03_overlap_rejected_but_adjacent_allowed(services, make_user, space_id):
    a, b = make_user("a@test.local"), make_user("b@test.local")
    services.bookings.create(a, req(space_id, 2, 10, 12))
    assert error_code(services.bookings.create, b, req(space_id, 2, 11, 13)) == "SLOT_TAKEN"
    assert error_code(services.bookings.create, b, req(space_id, 2, 10, 12)) == "SLOT_TAKEN"
    services.bookings.create(b, req(space_id, 2, 12, 13))  # 相鄰：允許
    services.bookings.create(b, req(space_id, 2, 9, 10))  # 相鄰：允許


def test_br03_cancelled_booking_releases_slot(services, make_user, space_id):
    a, b = make_user("a@test.local"), make_user("b@test.local")
    first = services.bookings.create(a, req(space_id))
    services.bookings.cancel_by_member(a, first.booking_id)
    services.bookings.create(b, req(space_id))


def test_br04_capacity_and_unavailable_space(services, make_user, make_space):
    user = make_user()
    sid = make_space(capacity=4)
    assert error_code(services.bookings.create, user, req(sid, attendees=5)) == "OVER_CAPACITY"
    services.bookings.create(user, req(sid, attendees=4))
    db.session.get(Space, sid).status = "MAINTENANCE"
    db.session.commit()
    assert error_code(services.bookings.create, user, req(sid, 3)) == "SPACE_UNAVAILABLE"


def test_br04_disabled_branch_is_unavailable(services, make_user, space_id):
    user = make_user()
    db.session.get(Space, space_id).branch.status = "DISABLED"
    db.session.commit()
    assert error_code(services.bookings.create, user, req(space_id)) == "SPACE_UNAVAILABLE"


def test_br01_outside_hours_and_br02_range_via_create(services, make_user, space_id):
    user = make_user()
    assert (
        error_code(services.bookings.create, user, req(space_id, 2, 7, 9))
        == "OUTSIDE_OPENING_HOURS"
    )
    assert error_code(services.bookings.create, user, req(space_id, 0, 9, 10)) == "OUT_OF_RANGE"
    assert error_code(services.bookings.create, user, req(space_id, 61, 10, 11)) == "OUT_OF_RANGE"


def test_br05_unverified_and_restricted_users_cannot_book(services, make_user, space_id):
    unverified = make_user("u@test.local", verified=False)
    frozen = make_user("f@test.local", status="FROZEN", reason="測試")
    blacklisted = make_user("b@test.local", status="BLACKLISTED", reason="測試")
    assert error_code(services.bookings.create, unverified, req(space_id)) == "EMAIL_NOT_VERIFIED"
    assert error_code(services.bookings.create, frozen, req(space_id)) == "ACCOUNT_RESTRICTED"
    assert error_code(services.bookings.create, blacklisted, req(space_id)) == "ACCOUNT_RESTRICTED"


def test_br06_at_most_three_pending_bookings(services, make_user, space_id):
    user = make_user()
    for hour in (10, 11, 12):
        services.bookings.create(user, req(space_id, 2, hour, hour + 1))
    assert error_code(services.bookings.create, user, req(space_id, 2, 13, 14)) == "PENDING_LIMIT"


def test_br06_paid_booking_does_not_count_toward_limit(services, make_user, space_id):
    user = make_user()
    booked(services, user, space_id, 2, 10, 11)
    for hour in (11, 12, 13):
        services.bookings.create(user, req(space_id, 2, hour, hour + 1))


def test_br08_overdue_pending_is_expired_and_slot_released(services, make_user, clock, space_id):
    a, b = make_user("a@test.local"), make_user("b@test.local")
    first = services.bookings.create(a, req(space_id))
    clock.advance(minutes=16)
    services.bookings.create(b, req(space_id))  # 同一交易先處理逾時訂單，不必等排程
    assert fresh(first.booking_id).status == "EXPIRED"
    assert [log.action for log in fresh(first.booking_id).logs] == ["CREATE", "EXPIRE"]


def test_br08_overdue_pending_does_not_count_toward_limit(services, make_user, clock, space_id):
    user = make_user()
    for hour in (10, 11, 12):
        services.bookings.create(user, req(space_id, 2, hour, hour + 1))
    clock.advance(minutes=16)
    services.bookings.create(user, req(space_id, 2, 13, 14))


def test_fr14_availability_marks_booked_and_past_slots(services, make_user, space_id):
    user = make_user()
    services.bookings.create(user, req(space_id, 0, 14, 16))  # 今天 14:00–16:00
    day = services.availability.availability(space_id, local_date(NOW))  # 今天（台北 11/02）
    by_hour = {s.start: s.status for s in day.slots}
    assert by_hour[9] == by_hour[10] == "PAST"  # 現在 10:30，下一個整點 11:00
    assert by_hour[11] == "AVAILABLE"
    assert by_hour[14] == by_hour[15] == "BOOKED"
    assert by_hour[16] == "AVAILABLE"
