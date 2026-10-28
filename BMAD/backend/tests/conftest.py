"""測試共用設定。

- 純函式與模型測試（tests/unit 中不用 db_clean 的檔案）不需要資料庫。
- 其餘測試使用實際 PostgreSQL（TEST_DATABASE_URL，預設 judian_test），需有 btree_gist 擴充；
  不可用 SQLite 或 mock 代替（CLAUDE.md 測試規則）。
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import text

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.mail.sender import FakeMailer
from app.models import Branch, Equipment, Space, User, UserPassword
from app.security.passwords import hash_password
from app.services.auth import user_to_dto
from app.utils.clock import FixedClock
from app.utils.time import day_hour, local_date

# 固定的「現在」：2026-11-02（週一）台北 10:30
NOW = datetime(2026, 11, 2, 2, 30, tzinfo=UTC)
PASSWORD = "Passw0rd!"


def at(days: int, hour: int) -> datetime:
    """相對於 NOW 當地日期的整點（UTC 時間點）。"""
    return day_hour(local_date(NOW) + timedelta(days=days), hour)


@pytest.fixture(scope="session")
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture(scope="session")
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture(scope="session")
def app(clock, mailer, tmp_path_factory):
    app = create_app(TestingConfig, clock=clock, mailer=mailer)
    app.config["UPLOAD_DIR"] = str(tmp_path_factory.mktemp("uploads"))
    with app.app_context():
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        db.session.commit()
        db.drop_all()
        db.create_all()
    return app


@pytest.fixture
def db_clean(app, clock, mailer):
    """每個測試前後清空所有資料表，並重設時間與寄信記錄。"""
    tables = ", ".join(f'"{t.name}"' for t in db.metadata.sorted_tables)

    def reset():
        db.session.remove()
        with db.engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        clock.set(NOW)
        mailer.sent.clear()
        mailer.fail = False

    with app.app_context():
        reset()
        yield
        reset()


@pytest.fixture
def services(app):
    return app.extensions["services"]


@pytest.fixture
def client(app, db_clean):
    return app.test_client()


@pytest.fixture
def make_user(db_clean):
    def _make(
        email="member@test.local",
        name="測試會員",
        role="USER",
        status="ACTIVE",
        reason=None,
        verified=True,
        password=PASSWORD,
        last_login_at=None,
        created_at=None,
    ):
        user = User(
            email=email,
            name=name,
            role=role,
            status=status,
            status_reason=reason,
            email_verified_at=NOW if verified else None,
            last_login_at=last_login_at,
        )
        if created_at is not None:
            user.created_at = created_at
        if password:
            hash_hex, salt_hex = hash_password(password)
            user.password = UserPassword(password_hash=hash_hex, password_salt=salt_hex)
        db.session.add(user)
        db.session.commit()
        return user_to_dto(user)

    return _make


@pytest.fixture
def admin(make_user):
    return make_user("admin@test.local", "管理員", role="ADMIN")


@pytest.fixture
def make_space(db_clean):
    def _make(name="201 會議室", capacity=10, price=300, open_hour=9, close_hour=22, **kw):
        branch = Branch(
            name="測試場館",
            city="桃園市",
            district="中壢區",
            address="中大路 300 號",
            phone="03-1234567",
            latitude=24.9677,
            longitude=121.1916,
            open_time=time(open_hour),
            close_time=time(close_hour),
        )
        space = Space(
            branch=branch,
            name=name,
            space_type="MEETING",
            capacity=capacity,
            hourly_price=price,
            entry_guide="輸入房間密碼進入",
            **kw,
        )
        db.session.add_all([branch, space])
        db.session.commit()
        return space.space_id

    return _make


@pytest.fixture
def space_id(make_space):
    return make_space()


@pytest.fixture
def make_equipment(db_clean):
    def _make(name="投影機", category="AV"):
        equipment = Equipment(name=name, category=category)
        db.session.add(equipment)
        db.session.commit()
        return equipment.equipment_id

    return _make
