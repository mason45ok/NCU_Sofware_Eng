"""帳號：註冊、驗證、登入鎖定、重設密碼、Google 登入、會員管理（BR-20～24；FR-01～08、46）。"""

import re
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import AccountToken, ExternalAccount, User
from app.schemas.account import GoogleIdentity
from tests.conftest import NOW, PASSWORD
from tests.helpers import error_code

pytestmark = pytest.mark.usefixtures("db_clean")


def token_from_mail(mailer, index=-1) -> str:
    return re.search(r"token=([\w-]+)", mailer.sent[index][2]).group(1)


def user_count() -> int:
    return db.session.scalar(select(func.count()).select_from(User))


# ---------- 註冊與驗證 ----------
def test_fr01_register_creates_unverified_user_and_sends_mail(services, mailer):
    dto = services.auth.register("New@Test.local", "新會員", PASSWORD)
    assert dto.email_verified is False and dto.has_password is True
    assert len(mailer.sent) == 1 and "驗證" in mailer.sent[0][1]


def test_fr01_duplicate_email_is_case_insensitive_and_silent(services, make_user, mailer):
    make_user("dup@test.local")
    assert services.auth.register("DUP@test.local", "另一人", PASSWORD) is None
    assert user_count() == 1 and mailer.sent == []  # 不透露帳號是否存在


def test_fr01_google_only_account_gets_set_password_mail(services, mailer):
    services.google.handle_callback(GoogleIdentity("g-1", "g@gmail.com", "G", True))
    assert services.auth.register("g@gmail.com", "冒用", PASSWORD) is None
    assert user_count() == 1 and "設定登入密碼" in mailer.sent[-1][1]


def test_br22_weak_password_rejected(services):
    assert (
        error_code(services.auth.register, "w@test.local", "弱", "abcdefgh") == "PASSWORD_TOO_WEAK"
    )
    assert error_code(services.auth.register, "w@test.local", "弱", "Ab1") == "PASSWORD_TOO_WEAK"
    assert user_count() == 0


def test_br23_verification_token_is_single_use(services, mailer):
    dto = services.auth.register("v@test.local", "會員", PASSWORD)
    token = token_from_mail(mailer)
    services.auth.verify_email(token)
    assert services.auth.get(dto.user_id).email_verified is True
    assert error_code(services.auth.verify_email, token) == "TOKEN_INVALID"
    stored = db.session.scalar(select(AccountToken))
    assert stored.token_hash != token  # 資料庫只存雜湊


def test_br23_verification_token_expires_after_24_hours(services, mailer, clock):
    services.auth.register("v@test.local", "會員", PASSWORD)
    token = token_from_mail(mailer)
    clock.advance(hours=24, seconds=1)
    assert error_code(services.auth.verify_email, token) == "TOKEN_INVALID"


def test_fr02_resend_verification_replaces_old_token(services, mailer):
    services.auth.register("v@test.local", "會員", PASSWORD)
    old = token_from_mail(mailer)
    services.auth.resend_verification("V@test.local")
    services.auth.resend_verification("nobody@test.local")  # 不存在也不報錯
    assert len(mailer.sent) == 2
    assert error_code(services.auth.verify_email, old) == "TOKEN_INVALID"
    services.auth.verify_email(token_from_mail(mailer))


# ---------- 登入與鎖定 ----------
def test_fr03_login_updates_last_login_and_unknown_email_looks_same(services, make_user):
    make_user("a@test.local")
    dto = services.auth.login("A@Test.local", PASSWORD)
    assert dto.last_login_at == NOW
    assert error_code(services.auth.login, "a@test.local", "Wrong123") == "INVALID_CREDENTIALS"
    assert error_code(services.auth.login, "nobody@test.local", PASSWORD) == "INVALID_CREDENTIALS"


def test_fr03_frozen_and_blacklisted_can_still_login(services, make_user):
    make_user("f@test.local", status="FROZEN", reason="測試")
    make_user("b@test.local", status="BLACKLISTED", reason="測試")
    assert services.auth.login("f@test.local", PASSWORD).status == "FROZEN"
    assert services.auth.login("b@test.local", PASSWORD).status == "BLACKLISTED"


def test_br22_five_failures_lock_for_fifteen_minutes(services, make_user, clock):
    make_user("a@test.local")
    for _ in range(4):
        assert error_code(services.auth.login, "a@test.local", "Wrong123") == "INVALID_CREDENTIALS"
    assert error_code(services.auth.login, "a@test.local", "Wrong123") == "ACCOUNT_LOCKED"
    assert (
        error_code(services.auth.login, "a@test.local", PASSWORD) == "ACCOUNT_LOCKED"
    )  # 鎖定期間正確密碼也不行
    clock.advance(minutes=14)
    assert error_code(services.auth.login, "a@test.local", PASSWORD) == "ACCOUNT_LOCKED"
    clock.advance(minutes=2)
    assert services.auth.login("a@test.local", PASSWORD).email == "a@test.local"


def test_br22_success_resets_failure_count(services, make_user):
    make_user("a@test.local")
    for _ in range(4):
        error_code(services.auth.login, "a@test.local", "Wrong123")
    services.auth.login("a@test.local", PASSWORD)
    for _ in range(4):  # 歸零後再失敗 4 次仍不鎖定
        assert error_code(services.auth.login, "a@test.local", "Wrong123") == "INVALID_CREDENTIALS"


# ---------- 密碼 ----------
def test_fr08_change_password_requires_old_password(services, make_user):
    user = make_user("a@test.local")
    assert (
        error_code(services.passwords.change, user, "Wrong123", "NewPassw0rd")
        == "INVALID_CREDENTIALS"
    )
    assert error_code(services.passwords.change, user, PASSWORD, "weak") == "PASSWORD_TOO_WEAK"
    services.passwords.change(user, PASSWORD, "NewPassw0rd")
    services.auth.login("a@test.local", "NewPassw0rd")
    assert error_code(services.auth.login, "a@test.local", PASSWORD) == "INVALID_CREDENTIALS"


def test_fr05_reset_password_flow_unlocks_and_invalidates_token(services, make_user, mailer):
    make_user("a@test.local")
    for _ in range(5):
        error_code(services.auth.login, "a@test.local", "Wrong123")
    services.passwords.request_reset("a@test.local")
    token = token_from_mail(mailer)
    assert (
        error_code(services.passwords.reset, token, "weak") == "PASSWORD_TOO_WEAK"
    )  # 權杖未被耗用
    services.passwords.reset(token, "NewPassw0rd")
    assert services.auth.login("a@test.local", "NewPassw0rd").email == "a@test.local"  # 鎖定已解除
    assert error_code(services.passwords.reset, token, "OtherPassw0rd") == "TOKEN_INVALID"


def test_fr05_reset_for_unknown_email_is_silent(services, mailer):
    services.passwords.request_reset("nobody@test.local")
    assert mailer.sent == []


def test_br23_reset_token_expires_after_30_minutes(services, make_user, mailer, clock):
    make_user("a@test.local")
    services.passwords.request_reset("a@test.local")
    clock.advance(minutes=31)
    assert (
        error_code(services.passwords.reset, token_from_mail(mailer), "NewPassw0rd")
        == "TOKEN_INVALID"
    )


def test_fr06_google_only_user_sets_password_and_can_login(services, mailer):
    result = services.google.handle_callback(GoogleIdentity("g-1", "g@gmail.com", "G", True))
    user = result.user
    assert user.has_password is False and user.email_verified is True
    assert error_code(services.passwords.change, user, "a", "NewPassw0rd1") == "VALIDATION_ERROR"
    services.passwords.request_setup(user)
    services.passwords.set_password(token_from_mail(mailer), "NewPassw0rd1")
    assert services.auth.login("g@gmail.com", "NewPassw0rd1").user_id == user.user_id


def test_br23_wrong_purpose_token_is_rejected(services, mailer):
    services.auth.register("v@test.local", "會員", PASSWORD)
    verify_token = token_from_mail(mailer)
    assert error_code(services.passwords.reset, verify_token, "NewPassw0rd") == "TOKEN_INVALID"


def test_fr53_purge_tokens_removes_old_ones_only(services, mailer, clock):
    services.auth.register("v@test.local", "會員", PASSWORD)
    clock.advance(days=6)
    assert services.passwords.purge_tokens() == 0
    clock.advance(days=3)  # 已過期超過 7 天
    assert services.passwords.purge_tokens() == 1
    assert services.passwords.purge_tokens() == 0


def test_fr07_update_profile_cannot_change_email(services, make_user):
    user = make_user("a@test.local")
    updated = services.auth.update_profile(user, "新名字", "0912345678")
    assert (updated.name, updated.phone, updated.email) == ("新名字", "0912345678", "a@test.local")


# ---------- Google 登入（FR-04、BR-24） ----------
def test_fr04_case1_bound_google_logs_in(services):
    first = services.google.handle_callback(GoogleIdentity("g-1", "g@gmail.com", "G", True))
    again = services.google.handle_callback(GoogleIdentity("g-1", "changed@gmail.com", "G", True))
    assert again.status == "LOGGED_IN" and again.user.user_id == first.user.user_id


def test_fr04_case2_new_email_creates_verified_account(services):
    result = services.google.handle_callback(GoogleIdentity("g-2", "new@gmail.com", "新人", True))
    assert result.status == "LOGGED_IN" and result.user.email_verified is True
    unverified = services.google.handle_callback(
        GoogleIdentity("g-3", "n2@gmail.com", "新人", False)
    )
    assert unverified.user.email_verified is False


def test_br24_fr04_case3_existing_email_requires_password_to_link(services, make_user):
    make_user("user1@judian.local")
    identity = GoogleIdentity("g-777", "USER1@judian.local", "王小明", True)
    result = services.google.handle_callback(identity)
    assert result.status == "NEEDS_LINK" and result.user is None  # 不自動合併
    assert db.session.scalar(select(func.count()).select_from(ExternalAccount)) == 0
    assert (
        error_code(services.google.link, identity, identity.email, "Wrong123")
        == "INVALID_CREDENTIALS"
    )
    assert db.session.scalar(select(func.count()).select_from(ExternalAccount)) == 0
    linked = services.google.link(identity, identity.email, PASSWORD)
    assert linked.email == "user1@judian.local"
    assert services.google.handle_callback(identity).status == "LOGGED_IN"


def test_fr04_case3_account_already_linked_to_other_google(services):
    services.google.handle_callback(GoogleIdentity("g-1", "g@gmail.com", "G", True))
    other = GoogleIdentity("g-OTHER", "g@gmail.com", "G", True)
    assert error_code(services.google.handle_callback, other) == "ACCOUNT_ALREADY_LINKED"


def test_fr04_link_password_failures_count_toward_lock(services, make_user):
    make_user("user1@judian.local")
    identity = GoogleIdentity("g-777", "user1@judian.local", "王", True)
    for _ in range(4):
        assert (
            error_code(services.google.link, identity, identity.email, "Wrong123")
            == "INVALID_CREDENTIALS"
        )
    assert (
        error_code(services.google.link, identity, identity.email, "Wrong123") == "ACCOUNT_LOCKED"
    )


# ---------- 會員管理（BR-20、21） ----------
def test_br20_restricting_requires_reason_and_unrestricting_clears_it(services, make_user, admin):
    user = make_user("a@test.local")
    assert (
        error_code(services.admin_users.set_status, admin, user.user_id, "FROZEN", "")
        == "VALIDATION_ERROR"
    )
    frozen = services.admin_users.set_status(admin, user.user_id, "FROZEN", "違規")
    assert (frozen.status, frozen.status_reason) == ("FROZEN", "違規")
    active = services.admin_users.set_status(admin, user.user_id, "ACTIVE", None)
    assert (active.status, active.status_reason) == ("ACTIVE", None)


def test_br20_non_admin_and_admin_targets_are_rejected(services, make_user, admin):
    user, other = make_user("a@test.local"), make_user("b@test.local")
    assert (
        error_code(services.admin_users.set_status, user, other.user_id, "FROZEN", "x")
        == "FORBIDDEN"
    )
    assert (
        error_code(services.admin_users.set_status, admin, admin.user_id, "FROZEN", "x")
        == "FORBIDDEN"
    )


def test_br21_freeze_inactive_users_after_180_days(services, make_user, admin):
    old = NOW - timedelta(days=181)
    recent = NOW - timedelta(days=179)
    make_user("old@test.local", last_login_at=old)
    make_user("never@test.local", last_login_at=None, created_at=old)
    make_user("recent@test.local", last_login_at=recent)
    make_user("oldfrozen@test.local", status="FROZEN", reason="既有", last_login_at=old)
    db.session.get(User, admin.user_id).last_login_at = old
    db.session.commit()
    assert services.admin_users.freeze_inactive() == 2
    assert services.admin_users.freeze_inactive() == 0  # 冪等
    page = services.admin_users.search(None, None, "FROZEN")
    assert {u.email for u in page.items} == {
        "old@test.local",
        "never@test.local",
        "oldfrozen@test.local",
    }
    assert (
        services.admin_users.search("admin", None, None).items[0].status == "ACTIVE"
    )  # 管理員不受影響
