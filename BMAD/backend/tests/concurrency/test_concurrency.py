"""併發測試（NFR-03；ARCHITECTURE.md 6.1、6.2、6.6）。必須使用實際 PostgreSQL，不可用 SQLite 或 mock。"""

import threading
from collections import Counter
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.errors import AppError
from app.extensions import db
from app.models import Booking, BookingStatusLog, Payment
from tests.conftest import NOW
from tests.helpers import CARD_OK, req

pytestmark = [pytest.mark.concurrency, pytest.mark.usefixtures("db_clean")]


def run_parallel(app, jobs):
    """每個工作在自己的執行緒、應用程式情境與資料庫連線中執行，並同時起跑。"""
    barrier = threading.Barrier(len(jobs))
    results = [None] * len(jobs)

    def worker(index, job):
        with app.app_context():
            barrier.wait()
            try:
                results[index] = ("ok", job())
            except AppError as exc:
                results[index] = ("error", exc.code)
            finally:
                db.session.remove()

    threads = [threading.Thread(target=worker, args=(i, job)) for i, job in enumerate(jobs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert all(r is not None for r in results), "有執行緒未完成"
    return results


def test_nfr03_twenty_concurrent_bookings_for_same_slot_only_one_succeeds(
    app, services, make_user, space_id
):
    users = [make_user(f"u{i}@test.local") for i in range(20)]
    jobs = [lambda u=u: services.bookings.create(u, req(space_id, 2, 10, 12)) for u in users]
    results = run_parallel(app, jobs)
    assert Counter(r[0] for r in results) == {"ok": 1, "error": 19}
    assert {r[1] for r in results if r[0] == "error"} == {"SLOT_TAKEN"}
    assert db.session.scalar(select(func.count()).select_from(Booking)) == 1


def test_overlapping_but_different_slots_still_allow_only_non_overlapping(
    app, services, make_user, space_id
):
    users = [make_user(f"u{i}@test.local") for i in range(6)]
    slots = [(10, 12), (11, 13), (12, 14), (13, 15), (14, 16), (10, 11)]
    jobs = [
        lambda u=u, s=s: services.bookings.create(u, req(space_id, 2, *s))
        for u, s in zip(users, slots)
    ]
    run_parallel(app, jobs)
    booked = db.session.execute(
        select(Booking.start_at, Booking.end_at).order_by(Booking.start_at)
    ).all()
    assert all(a.end_at <= b.start_at for a, b in zip(booked, booked[1:])), (
        "資料庫中不應有重疊的訂單"
    )


def test_br06_same_user_concurrent_requests_cannot_exceed_pending_limit(
    app, services, make_user, space_id
):
    user = make_user()
    jobs = [
        lambda h=h: services.bookings.create(user, req(space_id, 2, h, h + 1))
        for h in range(10, 16)
    ]
    results = run_parallel(app, jobs)
    codes = Counter(r[1] if r[0] == "error" else "ok" for r in results)
    assert codes == {"ok": 3, "PENDING_LIMIT": 3}


def test_br09_concurrent_payments_with_same_key_charge_once(
    app, services, make_user, space_id, mailer
):
    user = make_user()
    booking_id = services.bookings.create(user, req(space_id)).booking_id
    jobs = [
        lambda: services.bookings.pay(user, booking_id, "CREDIT_CARD", CARD_OK, "same-key")
        for _ in range(8)
    ]
    results = run_parallel(app, jobs)
    assert [r[0] for r in results] == ["ok"] * 8
    assert all(r[1].status == "SUCCESS" for r in results)
    assert db.session.scalar(select(func.count()).select_from(Payment)) == 1
    assert len(mailer.sent) == 1  # 確認信只寄一次


def test_br09_concurrent_payments_with_different_keys_confirm_once(
    app, services, make_user, space_id
):
    user = make_user()
    booking_id = services.bookings.create(user, req(space_id)).booking_id
    jobs = [
        lambda i=i: services.bookings.pay(user, booking_id, "CREDIT_CARD", CARD_OK, f"key-{i}")
        for i in range(6)
    ]
    results = run_parallel(app, jobs)
    assert Counter(r[0] for r in results) == {"ok": 1, "error": 5}
    assert {r[1] for r in results if r[0] == "error"} == {"INVALID_STATE"}
    assert db.session.scalar(select(func.count()).select_from(Payment)) == 1


def test_pay_racing_with_expiry_job_leaves_a_single_consistent_outcome(
    app, services, make_user, clock, space_id
):
    user = make_user()
    booking_id = services.bookings.create(user, req(space_id)).booking_id
    clock.set(NOW + timedelta(minutes=16))  # 已超過付款期限
    jobs = [
        lambda: services.bookings.pay(user, booking_id, "CREDIT_CARD", CARD_OK, "k1"),
        lambda: services.bookings.expire_overdue(),
    ]
    run_parallel(app, jobs)
    db.session.expire_all()
    booking = db.session.get(Booking, booking_id)
    assert booking.status == "EXPIRED"  # 不會出現「已付款卻被標成逾時」
    assert db.session.scalar(select(func.count()).select_from(Payment)) == 0
    actions = [
        r.action
        for r in db.session.scalars(
            select(BookingStatusLog).where(BookingStatusLog.booking_id == booking_id)
        )
    ]
    assert actions.count("EXPIRE") == 1


def test_concurrent_cancel_refunds_once(app, services, make_user, space_id):
    user = make_user()
    booking_id = services.bookings.create(user, req(space_id)).booking_id
    services.bookings.pay(user, booking_id, "CREDIT_CARD", CARD_OK, "k")
    jobs = [lambda: services.bookings.cancel_by_member(user, booking_id) for _ in range(6)]
    results = run_parallel(app, jobs)
    assert [r[0] for r in results] == ["ok"] * 6
    assert (
        db.session.scalar(select(func.count()).select_from(Payment).where(Payment.type == "REFUND"))
        == 1
    )
