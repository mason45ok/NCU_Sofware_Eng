"""API 層：權限（未登入、非本人、非管理員）、錯誤格式、CSRF、限流、完整流程。使用 Flask test client。"""

import re
from io import BytesIO

import pytest

from app.extensions import limiter
from tests.conftest import PASSWORD, at
from tests.helpers import CARD_DECLINED, CARD_OK

pytestmark = pytest.mark.usefixtures("db_clean")
API = "/api/v1"


def login(client, email="member@test.local", password=PASSWORD):
    res = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.get_json()
    return res.get_json()["user"]


def slot_body(space_id, day=2, start=10, end=12, attendees=2):
    return {
        "space_id": space_id,
        "start_at": at(day, start).isoformat(),
        "end_at": at(day, end).isoformat(),
        "attendees": attendees,
    }


def create_and_pay(client, space_id, day=2, start=10, end=12, key="k-1"):
    created = client.post(f"{API}/bookings", json=slot_body(space_id, day, start, end))
    assert created.status_code == 201, created.get_json()
    booking_id = created.get_json()["booking_id"]
    paid = client.post(
        f"{API}/bookings/{booking_id}/pay",
        json={"method": "CREDIT_CARD", "card_no": CARD_OK},
        headers={"Idempotency-Key": key},
    )
    assert paid.status_code == 200 and paid.get_json()["status"] == "SUCCESS"
    return booking_id


# ---------- 權限與錯誤格式 ----------
def test_unauthenticated_requests_get_401_with_unified_error_format(client):
    for method, path in (("get", "/me/bookings"), ("post", "/bookings"), ("get", "/admin/summary")):
        res = getattr(client, method)(f"{API}{path}")
        assert res.status_code == 401
        error = res.get_json()["error"]
        assert error["code"] == "UNAUTHENTICATED" and error["message"] and error["details"] == {}


def test_non_admin_gets_403_on_admin_routes(client, make_user):
    make_user()
    login(client)
    for path in ("/admin/summary", "/admin/bookings", "/admin/users", "/admin/branches"):
        res = client.get(f"{API}{path}")
        assert res.status_code == 403 and res.get_json()["error"]["code"] == "FORBIDDEN"


def test_other_users_booking_is_404_not_403(client, make_user, space_id):
    make_user("owner@test.local")
    make_user("other@test.local")
    login(client, "owner@test.local")
    booking_id = create_and_pay(client, space_id)
    client.post(f"{API}/auth/logout")
    login(client, "other@test.local")
    for method, path in (
        ("get", f"/bookings/{booking_id}"),
        ("get", f"/bookings/{booking_id}/cancel-quote"),
        ("post", f"/bookings/{booking_id}/cancel"),
        ("post", f"/bookings/{booking_id}/review"),
    ):
        res = getattr(client, method)(
            f"{API}{path}", **({"json": {"rating": 5}} if method == "post" else {})
        )
        assert res.status_code == 404 and res.get_json()["error"]["code"] == "NOT_FOUND"


def test_validation_errors_list_fields(client):
    res = client.post(f"{API}/auth/login", json={"email": "not-an-email"})
    error = res.get_json()["error"]
    assert res.status_code == 400 and error["code"] == "VALIDATION_ERROR"
    assert {"email", "password"} <= set(error["details"]["fields"])


def test_csrf_token_required_when_enabled(app, client, make_user):
    make_user()
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        body = {"email": "member@test.local", "password": PASSWORD}
        denied = client.post(f"{API}/auth/login", json=body)
        assert denied.status_code == 403 and denied.get_json()["error"]["code"] == "FORBIDDEN"
        token = client.get(f"{API}/auth/csrf").get_json()["csrf_token"]
        allowed = client.post(f"{API}/auth/login", json=body, headers={"X-CSRFToken": token})
        assert allowed.status_code == 200
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_nfr02_login_is_rate_limited(client, make_user):
    make_user()
    limiter.enabled = True
    try:
        codes = [
            client.post(
                f"{API}/auth/login", json={"email": "member@test.local", "password": "Wrong123"}
            ).status_code
            for _ in range(11)
        ]
        assert codes[:10] == [401] * 10 and codes[10] == 429
        assert (
            client.post(
                f"{API}/auth/login", json={"email": "a@test.local", "password": "x"}
            ).get_json()["error"]["code"]
            == "RATE_LIMITED"
        )
    finally:
        limiter.enabled = False
        limiter.reset()


# ---------- 帳號流程 ----------
def test_register_verify_login_flow(client, mailer):
    res = client.post(
        f"{API}/auth/register",
        json={"email": "new@test.local", "name": "新會員", "password": PASSWORD},
    )
    assert res.status_code == 201
    me = client.get(f"{API}/auth/me").get_json()["user"]
    assert me["email"] == "new@test.local" and me["email_verified"] is False  # 註冊後自動登入
    token = re.search(r"token=([\w-]+)", mailer.sent[-1][2]).group(1)
    assert client.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get(f"{API}/auth/me").get_json()["user"]["email_verified"] is True
    assert (
        client.post(f"{API}/auth/verify-email", json={"token": token}).get_json()["error"]["code"]
        == "TOKEN_INVALID"
    )


def test_register_existing_email_looks_identical(client, make_user):
    make_user("dup@test.local")
    res = client.post(
        f"{API}/auth/register", json={"email": "dup@test.local", "name": "x", "password": PASSWORD}
    )
    assert res.status_code == 201 and res.get_json() == {"message": "請查收驗證信件"}
    assert client.get(f"{API}/auth/me").get_json() == {"user": None}  # 沒有被登入


def test_login_wrong_password_and_logout(client, make_user):
    make_user()
    res = client.post(
        f"{API}/auth/login", json={"email": "member@test.local", "password": "Wrong123"}
    )
    assert res.status_code == 401 and res.get_json()["error"]["message"] == "帳號或密碼錯誤"
    login(client)
    assert client.post(f"{API}/auth/logout").status_code == 200
    assert client.get(f"{API}/me/bookings").status_code == 401


def test_fr04_google_mock_three_cases(client, make_user):
    make_user("user1@judian.local")
    page = client.get(f"{API}/dev/google-mock")
    assert page.status_code == 200

    new = client.get(
        f"{API}/auth/google/callback?sub=g-new&email=new@gmail.com&name=New", follow_redirects=False
    )
    assert new.status_code == 302 and new.headers["Location"] == "/"
    assert client.get(f"{API}/auth/me").get_json()["user"]["email"] == "new@gmail.com"
    client.post(f"{API}/auth/logout")

    link = client.get(f"{API}/auth/google/callback?sub=g-777&email=user1@judian.local&name=Wang")
    assert link.status_code == 302 and link.headers["Location"].startswith("/auth/google/link")
    assert client.get(f"{API}/auth/me").get_json()["user"] is None  # 尚未登入
    wrong = client.post(f"{API}/auth/google/link", json={"password": "Wrong123"})
    assert wrong.status_code == 401
    ok = client.post(f"{API}/auth/google/link", json={"password": PASSWORD})
    assert (
        ok.status_code == 200
        and client.get(f"{API}/auth/me").get_json()["user"]["email"] == "user1@judian.local"
    )


def test_fr04_google_link_without_pending_identity_fails(client):
    res = client.post(f"{API}/auth/google/link", json={"password": PASSWORD})
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "TOKEN_INVALID"


def test_fr07_08_profile_and_password(client, make_user):
    make_user()
    login(client)
    assert (
        client.patch(f"{API}/me", json={"name": "新名字", "phone": "0912"}).get_json()["user"][
            "name"
        ]
        == "新名字"
    )
    assert client.patch(f"{API}/me", json={"email": "x@y.com"}).status_code == 400  # email 不可改
    bad = client.put(
        f"{API}/me/password", json={"old_password": "Wrong123", "new_password": "NewPassw0rd"}
    )
    assert bad.status_code == 401
    assert (
        client.put(
            f"{API}/me/password", json={"old_password": PASSWORD, "new_password": "NewPassw0rd"}
        ).status_code
        == 200
    )


# ---------- 目錄 ----------
def test_public_catalog_endpoints(client, space_id):
    assert client.get(f"{API}/catalog/filters").get_json()["cities"] == {"桃園市": ["中壢區"]}
    result = client.get(f"{API}/spaces?city=桃園市&people=5&sort=price_asc").get_json()
    assert result["total"] == 1 and result["items"][0]["space_id"] == space_id
    assert client.get(f"{API}/spaces/{space_id}").get_json()["branch"]["maps_url"]
    assert client.get(f"{API}/spaces/9999").status_code == 404
    avail = client.get(f"{API}/spaces/{space_id}/availability?date=2026-11-04").get_json()
    assert avail["bookable"] and len(avail["slots"]) == 13
    assert client.get(f"{API}/spaces/{space_id}/availability?date=bad").status_code == 400
    assert client.get(f"{API}/spaces/{space_id}/reviews").get_json()["total"] == 0
    assert client.get(f"{API}/spaces?people=0").status_code == 400


# ---------- 預約流程 ----------
def test_full_booking_flow_via_api(client, make_user, space_id, mailer):
    make_user()
    login(client)
    quote = client.post(f"{API}/bookings/quote", json=slot_body(space_id, 2, 10, 13)).get_json()
    assert (quote["hours"], quote["total_amount"], quote["payment_deadline_minutes"]) == (
        3,
        900,
        15,
    )

    booking_id = create_and_pay(client, space_id, 2, 10, 13)
    detail = client.get(f"{API}/bookings/{booking_id}").get_json()
    assert detail["status"] == "CONFIRMED" and detail["access_code"]["state"] == "NOT_YET_VALID"
    assert detail["access_code"]["code"] is None and detail["start_at"].endswith("+08:00")
    assert len(mailer.sent) == 1

    tabs = {
        tab: client.get(f"{API}/me/bookings?tab={tab}").get_json()["total"]
        for tab in ("pending", "upcoming", "completed", "closed")
    }
    assert tabs == {"pending": 0, "upcoming": 1, "completed": 0, "closed": 0}
    assert client.get(f"{API}/me/bookings?tab=bad").status_code == 400

    cancel_quote = client.get(f"{API}/bookings/{booking_id}/cancel-quote").get_json()
    assert cancel_quote["refund_amount"] == 900 and cancel_quote["ratio"] == 1.0
    cancelled = client.post(f"{API}/bookings/{booking_id}/cancel").get_json()
    assert cancelled["status"] == "CANCELLED" and cancelled["net_paid"] == 0


def test_fr22_declined_card_is_200_failed_and_missing_key_is_400(client, make_user, space_id):
    make_user()
    login(client)
    booking_id = client.post(f"{API}/bookings", json=slot_body(space_id)).get_json()["booking_id"]
    no_key = client.post(f"{API}/bookings/{booking_id}/pay", json={"method": "LINE_PAY"})
    assert no_key.status_code == 400
    declined = client.post(
        f"{API}/bookings/{booking_id}/pay",
        json={"method": "CREDIT_CARD", "card_no": CARD_DECLINED},
        headers={"Idempotency-Key": "k1"},
    )
    assert declined.status_code == 200
    assert (
        declined.get_json()["status"] == "FAILED"
        and declined.get_json()["reason"] == "CARD_DECLINED"
    )
    assert declined.get_json()["booking"]["status"] == "PENDING_PAYMENT"
    bad_method = client.post(
        f"{API}/bookings/{booking_id}/pay",
        json={"method": "CASH"},
        headers={"Idempotency-Key": "k2"},
    )
    assert bad_method.status_code == 400


def test_fr21_slot_taken_is_409_and_limit_is_409(client, make_user, space_id):
    make_user("a@test.local")
    make_user("b@test.local")
    login(client, "a@test.local")
    assert client.post(f"{API}/bookings", json=slot_body(space_id)).status_code == 201
    client.post(f"{API}/auth/logout")
    login(client, "b@test.local")
    taken = client.post(f"{API}/bookings", json=slot_body(space_id))
    assert taken.status_code == 409 and taken.get_json()["error"]["code"] == "SLOT_TAKEN"
    over = client.post(f"{API}/bookings", json=slot_body(space_id, 3, 10, 11, attendees=99))
    assert over.status_code == 422 and over.get_json()["error"]["code"] == "OVER_CAPACITY"
    late = client.post(
        f"{API}/bookings", json={**slot_body(space_id), "start_at": "2026-11-04T10:00:00"}
    )
    assert late.status_code == 400  # 缺少時區


def test_fr33_reschedule_and_review_via_api(client, make_user, space_id, services, clock):
    make_user()
    login(client)
    booking_id = create_and_pay(client, space_id, 2, 10, 12)
    new = {"start_at": at(3, 10).isoformat(), "end_at": at(3, 13).isoformat()}
    quote = client.post(f"{API}/bookings/{booking_id}/reschedule-quote", json=new).get_json()
    assert quote["diff"] == 300 and quote["requires_payment"]
    no_pay = client.post(f"{API}/bookings/{booking_id}/reschedule", json=new)
    assert no_pay.status_code == 400
    done = client.post(
        f"{API}/bookings/{booking_id}/reschedule",
        json={**new, "method": "LINE_PAY"},
        headers={"Idempotency-Key": "rs-1"},
    )
    assert done.status_code == 200 and done.get_json()["total_amount"] == 900

    assert client.post(f"{API}/bookings/{booking_id}/review", json={"rating": 5}).status_code == 422
    clock.set(at(3, 13))
    services.bookings.complete_finished()
    assert client.post(f"{API}/bookings/{booking_id}/review", json={"rating": 6}).status_code == 400
    review = client.post(f"{API}/bookings/{booking_id}/review", json={"rating": 5, "comment": "讚"})
    assert review.status_code == 201
    assert client.get(f"{API}/spaces/{space_id}/reviews").get_json()["total"] == 1


def test_fr15_favorites_api(client, make_user, space_id):
    make_user()
    login(client)
    assert client.put(f"{API}/me/favorites/{space_id}").status_code == 200
    assert client.put(f"{API}/me/favorites/{space_id}").status_code == 200
    assert [s["space_id"] for s in client.get(f"{API}/me/favorites").get_json()["items"]] == [
        space_id
    ]
    assert client.put(f"{API}/me/favorites/9999").status_code == 404
    assert client.delete(f"{API}/me/favorites/{space_id}").status_code == 200
    assert client.get(f"{API}/me/favorites").get_json()["items"] == []


# ---------- 管理後台 ----------
def test_admin_booking_handling_via_api(client, make_user, admin, space_id):
    member = make_user("member@test.local")
    login(client, "member@test.local")
    booking_id = create_and_pay(client, space_id, 2, 10, 12)
    client.post(f"{API}/auth/logout")
    login(client, "admin@test.local")

    found = client.get(f"{API}/admin/bookings?email=member@&status=CONFIRMED").get_json()
    assert found["total"] == 1
    detail = client.get(f"{API}/admin/bookings/{booking_id}").get_json()
    assert [log["action"] for log in detail["logs"]] == ["CREATE", "PAY"]

    refund_body = {"amount": 100, "reason": "補償"}
    assert (
        client.post(f"{API}/admin/bookings/{booking_id}/refunds", json=refund_body).status_code
        == 400
    )  # 缺冪等鍵
    first = client.post(
        f"{API}/admin/bookings/{booking_id}/refunds",
        json=refund_body,
        headers={"Idempotency-Key": "r1"},
    )
    again = client.post(
        f"{API}/admin/bookings/{booking_id}/refunds",
        json=refund_body,
        headers={"Idempotency-Key": "r1"},
    )
    assert first.status_code == again.status_code == 201
    assert first.get_json()["payment_id"] == again.get_json()["payment_id"]
    too_much = client.post(
        f"{API}/admin/bookings/{booking_id}/refunds",
        json={"amount": 9999},
        headers={"Idempotency-Key": "r2"},
    )
    assert (
        too_much.status_code == 422
        and too_much.get_json()["error"]["code"] == "REFUND_EXCEEDS_PAID"
    )

    move = {"start_at": at(4, 14).isoformat(), "end_at": at(4, 16).isoformat()}
    assert (
        client.post(f"{API}/admin/bookings/{booking_id}/reschedule", json=move).status_code == 400
    )  # 缺原因
    assert (
        client.post(
            f"{API}/admin/bookings/{booking_id}/reschedule", json={**move, "reason": "場地調整"}
        ).status_code
        == 200
    )

    assert client.post(f"{API}/admin/bookings/{booking_id}/cancel", json={}).status_code == 400
    cancelled = client.post(
        f"{API}/admin/bookings/{booking_id}/cancel", json={"reason": "停業"}
    ).get_json()
    assert cancelled["status"] == "CANCELLED" and cancelled["net_paid"] == 0

    status = client.patch(
        f"{API}/admin/users/{member.user_id}/status", json={"status": "FROZEN", "reason": "測試"}
    )
    assert status.get_json()["status"] == "FROZEN"
    assert (
        client.patch(
            f"{API}/admin/users/{member.user_id}/status", json={"status": "FROZEN"}
        ).status_code
        == 400
    )
    summary = client.get(f"{API}/admin/summary").get_json()
    assert set(summary) == {"today_bookings", "pending_affected_bookings", "failed_notifications"}


def test_admin_space_status_returns_affected_and_photo_upload(client, make_user, admin, space_id):
    make_user("member@test.local")
    login(client, "member@test.local")
    booking_id = create_and_pay(client, space_id)
    client.post(f"{API}/auth/logout")
    login(client, "admin@test.local")

    result = client.post(
        f"{API}/admin/spaces/{space_id}/status", json={"status": "MAINTENANCE"}
    ).get_json()
    assert [b["booking_id"] for b in result["affected_bookings"]] == [booking_id]
    assert client.get(f"{API}/spaces").get_json()["total"] == 0

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    ok = client.post(
        f"{API}/admin/spaces/{space_id}/photos",
        data={"file": (BytesIO(png), "room.png")},
        content_type="multipart/form-data",
    )
    assert ok.status_code == 201 and ok.get_json()["sort_order"] == 0
    bad = client.post(
        f"{API}/admin/spaces/{space_id}/photos",
        data={"file": (BytesIO(b"x"), "room.png")},
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400 and bad.get_json()["error"]["code"] == "INVALID_UPLOAD"


def test_admin_notifications_list_and_retry(client, make_user, admin, space_id, mailer):
    make_user("member@test.local")
    login(client, "member@test.local")
    mailer.fail = True
    create_and_pay(client, space_id)
    client.post(f"{API}/auth/logout")
    login(client, "admin@test.local")
    failed = client.get(f"{API}/admin/notifications?status=FAILED").get_json()
    assert failed["total"] == 1
    mailer.fail = False
    retried = client.post(
        f"{API}/admin/notifications/{failed['items'][0]['notification_id']}/retry"
    )
    assert retried.get_json()["status"] == "SENT"
