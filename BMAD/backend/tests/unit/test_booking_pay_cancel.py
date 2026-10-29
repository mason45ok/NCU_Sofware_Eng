"""付款、房間密碼、取消與退款（BR-09～13、17、18、25、26；ARCHITECTURE.md 6.2、6.3、6.5）。"""

import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import BookingStatusLog, NotificationLog, User
from tests.conftest import at
from tests.helpers import CARD_DECLINED, CARD_OK, booked, error_code, fresh, req

pytestmark = pytest.mark.usefixtures("db_clean")


# ---------- 付款 ----------
def test_br10_pay_success_confirms_issues_code_and_sends_mail(
    services, make_user, mailer, space_id
):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    result = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", CARD_OK, "k1")
    assert result.status == "SUCCESS" and result.booking.status == "CONFIRMED"
    code = fresh(created.booking_id).access_code
    assert re.fullmatch(r"\d{6}", code.code)
    assert code.valid_from == at(2, 10) - timedelta(minutes=10) and code.valid_until == at(2, 12)
    assert len(mailer.sent) == 1 and code.code in mailer.sent[0][2]  # 確認信含房間密碼
    assert [log.action for log in fresh(created.booking_id).logs] == ["CREATE", "PAY"]


def test_br09_declined_card_keeps_pending_and_allows_retry(services, make_user, space_id):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    failed = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", CARD_DECLINED, "k1")
    assert failed.status == "FAILED" and failed.reason == "CARD_DECLINED"
    assert failed.booking.status == "PENDING_PAYMENT"
    ok = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", CARD_OK, "k2")
    assert ok.status == "SUCCESS"
    statuses = [p.status for p in fresh(created.booking_id).payments]
    assert statuses == ["FAILED", "SUCCESS"]


def test_br09_same_idempotency_key_charges_once(services, make_user, mailer, space_id):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    first = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", CARD_OK, "same")
    second = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", CARD_OK, "same")
    assert first.status == second.status == "SUCCESS"
    assert len(fresh(created.booking_id).payments) == 1
    assert len(mailer.sent) == 1


def test_br09_key_used_for_another_booking_is_rejected(services, make_user, space_id):
    user = make_user()
    first = services.bookings.create(user, req(space_id, 2, 10, 11))
    second = services.bookings.create(user, req(space_id, 2, 12, 13))
    services.bookings.pay(user, first.booking_id, "CREDIT_CARD", CARD_OK, "dup")
    code = error_code(services.bookings.pay, user, second.booking_id, "CREDIT_CARD", CARD_OK, "dup")
    assert code == "IDEMPOTENCY_KEY_REUSED"


def test_fr22_pay_after_deadline_expires_booking(services, make_user, clock, space_id):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    clock.advance(minutes=16)
    assert (
        error_code(services.bookings.pay, user, created.booking_id, "LINE_PAY", None, "k")
        == "BOOKING_EXPIRED"
    )
    assert fresh(created.booking_id).status == "EXPIRED"
    assert (
        error_code(services.bookings.pay, user, created.booking_id, "LINE_PAY", None, "k2")
        == "BOOKING_EXPIRED"
    )


def test_pay_already_confirmed_with_new_key_is_invalid_state(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    assert (
        error_code(services.bookings.pay, user, dto.booking_id, "LINE_PAY", None, "new")
        == "INVALID_STATE"
    )


def test_br05_frozen_user_cannot_pay_but_can_cancel(services, make_user, space_id):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    member = db.session.get(User, user.user_id)
    member.status, member.status_reason = "FROZEN", "測試"
    db.session.commit()
    assert (
        error_code(services.bookings.pay, user, created.booking_id, "LINE_PAY", None, "k")
        == "ACCOUNT_RESTRICTED"
    )
    assert services.bookings.cancel_by_member(user, created.booking_id).status == "CANCELLED"


def test_br18_disabled_space_blocks_payment_and_lists_affected(
    services, make_user, admin, space_id
):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    paid = booked(services, user, space_id, 3, 10, 12)
    result = services.admin_catalog.set_space_status(space_id, "DISABLED")
    assert {b.booking_id for b in result.affected_bookings} == {created.booking_id, paid.booking_id}
    assert (
        error_code(services.bookings.pay, user, created.booking_id, "LINE_PAY", None, "k")
        == "SPACE_UNAVAILABLE"
    )
    # 管理員逐筆取消，已付款者全額退款
    cancelled = services.bookings.cancel_by_admin(admin, paid.booking_id, "場地維修")
    assert cancelled.status == "CANCELLED" and cancelled.net_paid == 0


def test_wrong_owner_gets_not_found(services, make_user, space_id):
    owner, other = make_user("o@test.local"), make_user("x@test.local")
    dto = booked(services, owner, space_id)
    for call in (
        lambda: services.bookings.get_for_owner(other, dto.booking_id),
        lambda: services.bookings.pay(other, dto.booking_id, "LINE_PAY", None, "k"),
        lambda: services.bookings.cancel_by_member(other, dto.booking_id),
        lambda: services.bookings.cancel_quote(other, dto.booking_id),
    ):
        assert error_code(call) == "NOT_FOUND"


# ---------- 房間密碼 ----------
def test_br11_access_code_visible_only_while_valid(services, make_user, clock, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)

    def view():
        return services.access_codes.view_for_owner(user.user_id, dto.booking_id)

    assert view().state == "NOT_YET_VALID" and view().code is None
    clock.set(at(2, 10) - timedelta(minutes=10))  # 剛好開始前 10 分鐘
    assert view().state == "VALID" and re.fullmatch(r"\d{6}", view().code)
    clock.set(at(2, 12) + timedelta(minutes=1))
    assert view().state == "EXPIRED" and view().code is None


def test_br11_cancel_revokes_access_code_immediately(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    services.bookings.cancel_by_member(user, dto.booking_id)
    assert services.access_codes.view_for_owner(user.user_id, dto.booking_id).state == "REVOKED"


def test_fr52_purge_removes_codes_expired_over_seven_days(services, make_user, clock, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    clock.set(at(2, 12) + timedelta(days=6))
    assert services.access_codes.purge_expired() == 0
    clock.set(at(2, 12) + timedelta(days=8))
    assert services.access_codes.purge_expired() == 1
    assert services.access_codes.purge_expired() == 0  # 冪等
    assert fresh(dto.booking_id).access_code is None


# ---------- 取消與退款 ----------
@pytest.mark.parametrize(
    ("lead_hours", "refund"),
    [(47, 600), (24, 600), (23, 300), (3, 300), (2, 0)],  # BR-12 邊界
)
def test_br12_member_refund_ratio(services, make_user, clock, space_id, lead_hours, refund):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)  # NT$600
    clock.set(at(2, 10) - timedelta(hours=lead_hours))
    quote = services.bookings.cancel_quote(user, dto.booking_id)
    assert quote.refund_amount == refund
    cancelled = services.bookings.cancel_by_member(user, dto.booking_id)
    assert cancelled.status == "CANCELLED" and cancelled.net_paid == 600 - refund
    refunds = [p for p in fresh(dto.booking_id).payments if p.type == "REFUND"]
    assert sum(p.amount for p in refunds) == refund and len(refunds) == (1 if refund else 0)


def test_br12_cancel_pending_has_no_refund(services, make_user, space_id):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    assert services.bookings.cancel_quote(user, created.booking_id).refund_amount == 0
    cancelled = services.bookings.cancel_by_member(user, created.booking_id)
    assert cancelled.status == "CANCELLED" and cancelled.cancelled_by == user.user_id
    assert fresh(created.booking_id).payments == []


def test_fr32_cancel_twice_refunds_once(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    services.bookings.cancel_by_member(user, dto.booking_id)
    again = services.bookings.cancel_by_member(user, dto.booking_id)
    assert again.status == "CANCELLED"
    assert len([p for p in fresh(dto.booking_id).payments if p.type == "REFUND"]) == 1


def test_cancel_completed_or_ended_booking_is_invalid_state(services, make_user, clock, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    clock.set(at(2, 12) + timedelta(minutes=1))
    assert error_code(services.bookings.cancel_by_member, user, dto.booking_id) == "INVALID_STATE"
    services.bookings.complete_finished()
    assert error_code(services.bookings.cancel_by_member, user, dto.booking_id) == "INVALID_STATE"


def test_br13_admin_cancel_refunds_in_full_and_requires_reason(
    services, make_user, admin, clock, space_id
):
    user = make_user()
    dto = booked(services, user, space_id)
    clock.set(at(2, 10) - timedelta(hours=1))  # 會員取消會是 0%
    assert (
        error_code(services.bookings.cancel_by_admin, admin, dto.booking_id, "  ")
        == "VALIDATION_ERROR"
    )
    cancelled = services.bookings.cancel_by_admin(admin, dto.booking_id, "場地漏水")
    assert cancelled.net_paid == 0 and cancelled.cancel_reason == "場地漏水"
    assert cancelled.cancelled_by == admin.user_id


def test_admin_methods_reject_non_admin(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    assert error_code(services.bookings.cancel_by_admin, user, dto.booking_id, "x") == "FORBIDDEN"


def test_br25_every_change_is_logged(services, make_user, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    services.bookings.cancel_by_member(user, dto.booking_id)
    logs = db.session.scalars(
        select(BookingStatusLog)
        .where(BookingStatusLog.booking_id == dto.booking_id)
        .order_by(BookingStatusLog.log_id)
    ).all()
    assert [(x.action, x.changed_by) for x in logs] == [
        ("CREATE", user.user_id),
        ("PAY", user.user_id),
        ("CANCEL", user.user_id),
    ]


# ---------- 部分退款 ----------
def test_br17_partial_refund_within_paid_amount(services, make_user, admin, space_id):
    user = make_user()
    dto = booked(services, user, space_id)  # NT$600
    payment = services.bookings.refund_partially(admin, dto.booking_id, 200, "refund-1", "客訴補償")
    assert payment.type == "REFUND" and payment.amount == 200
    again = services.bookings.refund_partially(admin, dto.booking_id, 200, "refund-1")
    assert again.payment_id == payment.payment_id  # 重複送出不重複退款
    booking = fresh(dto.booking_id)
    assert booking.net_paid() == 400 and booking.status == "CONFIRMED"
    assert booking.logs[-1].action == "REFUND"


def test_br17_refund_cannot_exceed_net_paid(services, make_user, admin, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    services.bookings.refund_partially(admin, dto.booking_id, 500, "r1")
    code = error_code(services.bookings.refund_partially, admin, dto.booking_id, 101, "r2")
    assert code == "REFUND_EXCEEDS_PAID"
    services.bookings.refund_partially(admin, dto.booking_id, 100, "r3")
    assert fresh(dto.booking_id).net_paid() == 0


def test_br17_cancel_after_partial_refund_uses_net_paid(
    services, make_user, admin, clock, space_id
):
    user = make_user()
    dto = booked(services, user, space_id)
    services.bookings.refund_partially(admin, dto.booking_id, 200, "r1")
    clock.set(at(2, 10) - timedelta(hours=10))  # 50%
    cancelled = services.bookings.cancel_by_member(user, dto.booking_id)
    assert cancelled.net_paid == 200  # 實收 400 的 50% = 退 200


# ---------- 排程 ----------
def test_fr50_expire_overdue_is_idempotent(services, make_user, clock, space_id):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    assert services.bookings.expire_overdue() == 0
    clock.advance(minutes=16)
    assert services.bookings.expire_overdue() == 1
    assert services.bookings.expire_overdue() == 0
    assert fresh(created.booking_id).status == "EXPIRED"


def test_br15_fr51_complete_finished(services, make_user, clock, space_id):
    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    clock.set(at(2, 12) - timedelta(minutes=1))
    assert services.bookings.complete_finished() == 0
    clock.set(at(2, 12))
    assert services.bookings.complete_finished() == 1
    assert services.bookings.complete_finished() == 0
    assert fresh(dto.booking_id).status == "COMPLETED"


# ---------- 通知 ----------
def test_br26_mail_failure_is_logged_and_retried(services, make_user, mailer, space_id):
    user = make_user()
    mailer.fail = True
    dto = booked(services, user, space_id)  # 寄信失敗不影響付款結果
    assert dto.status == "CONFIRMED"
    log = db.session.scalar(select(NotificationLog))
    assert (log.status, log.attempts) == ("FAILED", 1) and log.error_message
    mailer.fail = False
    assert services.notifications.retry_failed() == 1
    db.session.refresh(log)
    assert (log.status, log.attempts) == ("SENT", 2) and len(mailer.sent) == 1
    assert services.notifications.retry_failed() == 0


def test_br26_retry_stops_after_three_attempts(services, make_user, mailer, space_id):
    user = make_user()
    mailer.fail = True
    booked(services, user, space_id)
    assert services.notifications.retry_failed() == 1
    assert services.notifications.retry_failed() == 1
    assert services.notifications.retry_failed() == 0  # attempts 已達 3


def test_br26_cancel_sends_notification_with_refund(services, make_user, mailer, space_id):
    user = make_user()
    dto = booked(services, user, space_id)
    mailer.sent.clear()
    services.bookings.cancel_by_member(user, dto.booking_id)
    assert (
        len(mailer.sent) == 1 and "已取消" in mailer.sent[0][1] and "NT$ 600" in mailer.sent[0][2]
    )
