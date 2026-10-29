"""users（D1）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .columns import BigId
from .enums import Role, UserStatus


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('USER','ADMIN')", name="ck_users_role"),
        CheckConstraint("status IN ('ACTIVE','FROZEN','BLACKLISTED')", name="ck_users_status"),
        CheckConstraint("status = 'ACTIVE' OR status_reason IS NOT NULL", name="ck_users_reason"),
        Index("uq_users_email", text("lower(email)"), unique=True),
    )

    user_id: Mapped[BigId] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(10), default=Role.USER.value, server_default="USER")
    status: Mapped[str] = mapped_column(
        String(12), default=UserStatus.ACTIVE.value, server_default="ACTIVE"
    )
    status_reason: Mapped[str | None] = mapped_column(String(200))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    password: Mapped[UserPassword | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    external_accounts: Mapped[list[ExternalAccount]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    def can_book(self) -> bool:
        """BR-05：帳號 ACTIVE 且 email 已驗證。"""
        return self.status == UserStatus.ACTIVE and self.email_verified_at is not None

    def has_password(self) -> bool:
        return self.password is not None


class UserPassword(db.Model):
    __tablename__ = "user_passwords"
    __table_args__ = (CheckConstraint("failed_attempts >= 0", name="ck_user_passwords_attempts"),)

    password_id: Mapped[BigId] = mapped_column(primary_key=True)
    user_id: Mapped[BigId] = mapped_column(
        db.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )
    password_hash: Mapped[str] = mapped_column(db.CHAR(64))
    password_salt: Mapped[str] = mapped_column(db.CHAR(32))
    failed_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="password")

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now


class ExternalAccount(db.Model):
    __tablename__ = "external_accounts"
    __table_args__ = (
        CheckConstraint("provider IN ('GOOGLE')", name="ck_external_provider"),
        db.UniqueConstraint("provider", "provider_user_id", name="uq_external_provider_sub"),
        db.UniqueConstraint("user_id", "provider", name="uq_external_user_provider"),
    )

    ext_id: Mapped[BigId] = mapped_column(primary_key=True)
    user_id: Mapped[BigId] = mapped_column(db.ForeignKey("users.user_id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(10))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    provider_email: Mapped[str | None] = mapped_column(String(254))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="external_accounts")


class AccountToken(db.Model):
    __tablename__ = "account_tokens"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('VERIFY_EMAIL','RESET_PASSWORD','SET_PASSWORD')",
            name="ck_tokens_purpose",
        ),
        CheckConstraint("expires_at > created_at", name="ck_tokens_expiry"),
        Index("ix_account_tokens_user", "user_id", "purpose"),
    )

    token_id: Mapped[BigId] = mapped_column(primary_key=True)
    user_id: Mapped[BigId] = mapped_column(db.ForeignKey("users.user_id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(db.CHAR(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def is_usable(self, now: datetime) -> bool:
        return self.used_at is None and self.expires_at > now
