"""改期與評論（BR-14、16、19；ARCHITECTURE.md 6.4）。使用實際 PostgreSQL。"""

from datetime import timedelta

import pytest

from app.models import BookingStatusLog
from tests.conftest import at
from tests.helpers import CARD_DECLINED, CARD_OK, booked, error_code, fresh, req, slot

pytestmark = pytest.mark.usefixtures("db_clean")


def reschedule(services, user, dto, new_slot, method="CREDIT_CARD", card=CARD_OK, key="rs-1"):
    return services.bookings.reschedule_by_member(user, dto.booking_id, new_slot, method, card, key)


def test_br14_longer_slot_charges_difference_and_syncs_access_code(
    services, make_user, mailer, space_id
):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)  # 2 小時 NT$600
    quote = services.bookings.reschedule_quote(user, dto.booking_id, slot(3, 10, 13))
    assert (quote.diff, quote.new_amount, quote.requires_payment) == (300, 900, True)
    mailer.sent.clear()
    result = reschedule(services, user, dto, slot(3, 10, 13))
    booking = fresh(dto.booking_id)
    assert (result.total_amount, booking.net_paid(), booking.reschedule_count) == (900, 900, 1)
    assert booking.status == "CONFIRMED"
    assert booking.access_code.valid_from == at(3, 10) - timedelta(minutes=10)
    assert booking.access_code.valid_until == at(3, 13)
    assert booking.logs[-1].action == "RESCHEDULE" and "→" in booking.logs[-1].reason
    assert len(mailer.sent) == 1 and "已改期" in mailer.sent[0][1]


def test_br14_shorter_slot_refunds_difference(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 13)  # NT$900
    result = reschedule(services, user, dto, slot(3, 10, 12), method=None, card=None, key=None)
    booking = fresh(dto.booking_id)
    assert result.total_amount == 600 and booking.net_paid() == 600
    assert [p.amount for p in booking.payments if p.type == "REFUND"] == [300]


def test_br14_same_hours_needs_no_payment(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    result = reschedule(services, user, dto, slot(4, 14, 16), method=None, card=None, key=None)
    assert result.total_amount == 600 and len(fresh(dto.booking_id).payments) == 1


def test_br14_uses_original_price_snapshot(services, make_user, space_id):
    from app.extensions import db
    from app.models import Space

    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    db.session.get(Space, space_id).hourly_price = 1000
    db.session.commit()
    assert services.bookings.reschedule_quote(user, dto.booking_id, slot(3, 10, 13)).diff == 300


def test_br14_declined_card_keeps_original_booking(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    code = error_code(reschedule, services, user, dto, slot(3, 10, 13), card=CARD_DECLINED)
    assert code == "RESCHEDULE_NOT_ALLOWED"
    booking = fresh(dto.booking_id)
    assert (booking.start_at, booking.end_at) == (at(2, 10), at(2, 12))
    assert (booking.total_amount, booking.reschedule_count, len(booking.payments)) == (600, 0, 1)


def test_br14_missing_payment_method_for_upcharge(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    code = error_code(
        reschedule, services, user, dto, slot(3, 10, 13), method=None, card=None, key=None
    )
    assert code == "VALIDATION_ERROR"


def test_br14_slot_taken_rolls_back(services, make_user, space_id):
    a, b = make_user("a@test.local"), make_user("b@test.local")
    mine = booked(services, a, space_id, 2, 10, 12)
    booked(services, b, space_id, 3, 10, 12)
    code = error_code(
        reschedule, services, a, mine, slot(3, 11, 13), method=None, card=None, key=None
    )
    assert code == "SLOT_TAKEN"
    booking = fresh(mine.booking_id)
    assert (booking.start_at, booking.reschedule_count) == (at(2, 10), 0)


def test_br14_overlapping_own_old_slot_is_allowed(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    result = reschedule(services, user, dto, slot(2, 11, 13), method=None, card=None, key=None)
    assert result.start_at == at(2, 11)


def test_br14_within_24_hours_of_original_start_is_rejected(services, make_user, clock, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    clock.set(at(2, 10) - timedelta(hours=23))
    assert error_code(reschedule, services, user, dto, slot(4, 10, 12)) == "RESCHEDULE_NOT_ALLOWED"
    clock.set(at(2, 10) - timedelta(hours=24))  # 邊界：剛好 24 小時可改
    reschedule(services, user, dto, slot(4, 10, 12), method=None, card=None, key=None)


def test_br14_only_once(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    reschedule(services, user, dto, slot(3, 10, 12), method=None, card=None, key=None)
    assert error_code(reschedule, services, user, dto, slot(4, 10, 12)) == "RESCHEDULE_NOT_ALLOWED"


def test_br14_resending_same_request_is_idempotent(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    reschedule(services, user, dto, slot(3, 10, 13))
    again = reschedule(services, user, dto, slot(3, 10, 13))
    assert (
        again.total_amount == 900 and len(fresh(dto.booking_id).payments) == 2
    )  # 付款 600＋補付 300


def test_br14_only_confirmed_bookings_and_new_slot_rules(services, make_user, space_id):
    user = make_user()
    pending = services.bookings.create(user, req(space_id, 2, 10, 12))
    assert error_code(reschedule, services, user, pending, slot(3, 10, 12)) == "INVALID_STATE"
    paid = booked(services, user, space_id, 5, 10, 12)
    assert error_code(reschedule, services, user, paid, slot(6, 7, 9)) == "OUTSIDE_OPENING_HOURS"


def test_br19_admin_reschedule_same_hours_only_without_count(
    services, make_user, admin, clock, space_id
):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    clock.set(at(2, 10) - timedelta(hours=1))  # 不受 24 小時限制
    assert (
        error_code(
            services.bookings.reschedule_by_admin,
            admin,
            dto.booking_id,
            slot(4, 10, 13),
            "場地調整",
        )
        == "RESCHEDULE_NOT_ALLOWED"
    )
    assert (
        error_code(
            services.bookings.reschedule_by_admin, admin, dto.booking_id, slot(4, 10, 12), " "
        )
        == "VALIDATION_ERROR"
    )
    result = services.bookings.reschedule_by_admin(
        admin, dto.booking_id, slot(4, 14, 16), "場地調整"
    )
    booking = fresh(dto.booking_id)
    assert result.start_at == at(4, 14) and booking.reschedule_count == 0
    assert booking.net_paid() == 600 and len(booking.payments) == 1
    log = booking.logs[-1]
    assert (
        log.action == "RESCHEDULE" and log.changed_by == admin.user_id and "場地調整" in log.reason
    )


def test_br19_admin_cannot_use_member_method(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    assert (
        error_code(
            services.bookings.reschedule_by_admin, user, dto.booking_id, slot(4, 10, 12), "x"
        )
        == "FORBIDDEN"
    )


# ---------- 評論 ----------
def complete(services, clock, user, space_id):
    dto = booked(services, user, space_id, 2, 10, 12)
    clock.set(at(2, 12))
    services.bookings.complete_finished()
    return dto


def test_br16_review_after_completion(services, make_user, clock, space_id):
    user = make_user()
    dto = complete(services, clock, user, space_id)
    review = services.reviews.create(user, dto.booking_id, 5, "很棒")
    assert review.rating == 5 and review.reviewer.endswith("○○")
    assert services.reviews.list_for_space(space_id).total == 1
    assert services.catalog.get_space(space_id).avg_rating == 5.0


def test_br16_rejections(services, make_user, clock, space_id):
    user, other = make_user(), make_user("o@test.local")
    pending = booked(services, user, space_id, 5, 10, 12)
    assert (
        error_code(services.reviews.create, user, pending.booking_id, 5, None)
        == "REVIEW_NOT_ALLOWED"
    )  # 未完成
    dto = complete(services, clock, user, space_id)
    assert (
        error_code(services.reviews.create, other, dto.booking_id, 5, None) == "NOT_FOUND"
    )  # 非本人
    services.reviews.create(user, dto.booking_id, 4, None)
    assert (
        error_code(services.reviews.create, user, dto.booking_id, 5, None) == "REVIEW_NOT_ALLOWED"
    )  # 已評論


def test_br16_thirty_day_window(services, make_user, clock, space_id):
    user = make_user()
    dto = complete(services, clock, user, space_id)
    clock.set(at(2, 12) + timedelta(days=30, minutes=1))
    assert (
        error_code(services.reviews.create, user, dto.booking_id, 5, None) == "REVIEW_NOT_ALLOWED"
    )


def test_fr47_hidden_review_is_not_public_and_not_counted(services, make_user, clock, space_id):
    user = make_user()
    dto = complete(services, clock, user, space_id)
    review = services.reviews.create(user, dto.booking_id, 5, "不當內容")
    services.reviews.set_hidden(review.review_id, True)
    assert services.reviews.list_for_space(space_id).total == 0
    assert services.catalog.get_space(space_id).review_count == 0
    assert services.reviews.list_all().total == 1
    services.reviews.set_hidden(review.review_id, False)
    assert services.reviews.list_for_space(space_id).total == 1


def test_status_log_count_matches_actions(services, make_user, space_id):
    from sqlalchemy import func, select

    from app.extensions import db

    user = make_user()
    dto = booked(services, user, space_id)
    reschedule(services, user, dto, slot(3, 10, 12), method=None, card=None, key=None)
    count = db.session.scalar(select(func.count()).select_from(BookingStatusLog))
    assert count == 3  # CREATE、PAY、RESCHEDULE
