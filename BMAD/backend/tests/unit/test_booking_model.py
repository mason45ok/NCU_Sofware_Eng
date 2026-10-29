"""Booking.transition() 的所有合法與不合法轉換（D10）、record()、實收計算。BR-25。不需資料庫。"""

import pytest

from app.errors import ConflictError
from app.models import Booking, BookingAction, BookingStatus, Payment

S = BookingStatus
A = BookingAction

LEGAL = [
    (None, S.PENDING_PAYMENT, A.CREATE),
    (S.PENDING_PAYMENT, S.CONFIRMED, A.PAY),
    (S.PENDING_PAYMENT, S.EXPIRED, A.EXPIRE),
    (S.PENDING_PAYMENT, S.CANCELLED, A.CANCEL),
    (S.CONFIRMED, S.CANCELLED, A.CANCEL),
    (S.CONFIRMED, S.COMPLETED, A.COMPLETE),
]


def _booking(status):
    booking = Booking()
    booking.status = status.value if status else None
    return booking


@pytest.mark.parametrize(("src", "dst", "action"), LEGAL)
def test_br25_legal_transitions_write_log(src, dst, action):
    booking = _booking(src)
    log = booking.transition(dst, action, 7, "原因")
    assert booking.status == dst
    assert (log.from_status, log.to_status, log.action) == (
        src.value if src else None,
        dst.value,
        action.value,
    )
    assert log.changed_by == 7
    assert booking.logs == [log]


ILLEGAL = [
    (src, dst)
    for src in S
    for dst in S
    if (src, dst) not in {(a, b) for a, b, _ in LEGAL} and src != dst
] + [(S.CANCELLED, S.CANCELLED), (S.COMPLETED, S.COMPLETED)]


@pytest.mark.parametrize(("src", "dst"), ILLEGAL)
def test_illegal_transitions_raise_invalid_state(src, dst):
    booking = _booking(src)
    with pytest.raises(ConflictError) as exc:
        booking.transition(dst, A.CANCEL, None, None)
    assert exc.value.code == "INVALID_STATE"
    assert booking.status == src  # 狀態未被改變
    assert booking.logs == []


def test_record_keeps_status_but_writes_log():
    booking = _booking(S.CONFIRMED)
    log = booking.record(A.RESCHEDULE, 1, "A → B")
    assert booking.status == S.CONFIRMED
    assert (log.from_status, log.to_status, log.action) == ("CONFIRMED", "CONFIRMED", "RESCHEDULE")


def test_net_paid_is_payments_minus_refunds_and_ignores_failed():
    booking = _booking(S.CONFIRMED)
    booking.payments.extend(
        [
            Payment(type="PAYMENT", amount=600, status="SUCCESS"),
            Payment(type="PAYMENT", amount=300, status="FAILED"),
            Payment(type="REFUND", amount=100, status="SUCCESS"),
        ]
    )
    assert (booking.paid_amount(), booking.refunded_amount(), booking.net_paid()) == (600, 100, 500)


def test_is_active_matches_exclusion_constraint_condition():
    assert _booking(S.PENDING_PAYMENT).is_active()
    assert _booking(S.CONFIRMED).is_active()
    assert not any(_booking(s).is_active() for s in (S.CANCELLED, S.EXPIRED, S.COMPLETED))
