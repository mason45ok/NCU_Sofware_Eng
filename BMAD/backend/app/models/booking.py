"""bookings、booking_status_logs、payments、access_codes（D2-2）。

訂單狀態只能透過 Booking.transition() 改變（C4）；改期與部分退款不改狀態，用 Booking.record()。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, and_, func, or_, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..errors import ConflictError
from ..extensions import db
from .columns import BigId
from .enums import (
    AccessCodeState,
    BookingAction,
    BookingStatus,
    PaymentStatus,
    PaymentType,
)

# 狀態圖 D10 的允許轉換；None 代表新建立的訂單
_ALLOWED: dict[str | None, set[str]] = {
    None: {BookingStatus.PENDING_PAYMENT},
    BookingStatus.PENDING_PAYMENT: {
        BookingStatus.CONFIRMED,
        BookingStatus.EXPIRED,
        BookingStatus.CANCELLED,
    },
    BookingStatus.CONFIRMED: {BookingStatus.CANCELLED, BookingStatus.COMPLETED},
}


class Booking(db.Model):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("attendees > 0", name="ck_bookings_attendees"),
        CheckConstraint("hourly_price_snapshot > 0", name="ck_bookings_price"),
        CheckConstraint("total_amount > 0", name="ck_bookings_total_positive"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT','CONFIRMED','CANCELLED','EXPIRED','COMPLETED')",
            name="ck_bookings_status",
        ),
        CheckConstraint("reschedule_count BETWEEN 0 AND 1", name="ck_bookings_reschedule"),
        CheckConstraint("end_at > start_at", name="ck_bookings_range"),
        CheckConstraint(
            "extract(epoch FROM start_at)::bigint % 3600 = 0",
            name="ck_bookings_start_hour",
        ),
        CheckConstraint(
            "extract(epoch FROM end_at)::bigint % 3600 = 0", name="ck_bookings_end_hour"
        ),
        CheckConstraint(
            "total_amount = hourly_price_snapshot * "
            "(extract(epoch FROM (end_at - start_at))::int / 3600)",
            name="ck_bookings_amount",
        ),
        CheckConstraint(
            "(status = 'CANCELLED') = (cancelled_at IS NOT NULL)",
            name="ck_bookings_cancelled",
        ),
        # 核心約束（BR-03）：同一空間有效訂單的時段不可重疊，半開區間 [)，相鄰不衝突
        ExcludeConstraint(
            ("space_id", "="),
            (func.tstzrange(text("start_at"), text("end_at"), "[)"), "&&"),
            name="ex_bookings_no_overlap",
            using="gist",
            where=text("status IN ('PENDING_PAYMENT','CONFIRMED')"),
        ),
        Index("ix_bookings_user", "user_id", "status"),
        Index(
            "ix_bookings_pending_expiry",
            "expires_at",
            postgresql_where=text("status = 'PENDING_PAYMENT'"),
        ),
        Index(
            "ix_bookings_confirmed_end",
            "end_at",
            postgresql_where=text("status = 'CONFIRMED'"),
        ),
    )

    booking_id: Mapped[BigId] = mapped_column(primary_key=True)
    booking_no: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[BigId] = mapped_column(db.ForeignKey("users.user_id"))
    space_id: Mapped[BigId] = mapped_column(db.ForeignKey("spaces.space_id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attendees: Mapped[int]
    note: Mapped[str | None] = mapped_column(String(500))
    hourly_price_snapshot: Mapped[int]
    total_amount: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), server_default="PENDING_PAYMENT")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reschedule_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cancelled_by: Mapped[BigId | None] = mapped_column(db.ForeignKey("users.user_id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(200))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", foreign_keys=[user_id])
    space = relationship("Space")
    logs: Mapped[list[BookingStatusLog]] = relationship(
        back_populates="booking",
        order_by="BookingStatusLog.log_id",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="booking",
        order_by="Payment.payment_id",
        cascade="all, delete-orphan",
    )
    access_code: Mapped[AccessCode | None] = relationship(back_populates="booking", uselist=False)
    review = relationship("Review", back_populates="booking", uselist=False)

    # ---- 衍生屬性 ----
    def hours(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 3600)

    def is_active(self) -> bool:
        """與資料庫排除約束的條件相同：待付款或已確認。"""
        return self.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED)

    def is_payment_overdue(self, now: datetime) -> bool:
        return self.status == BookingStatus.PENDING_PAYMENT and self.expires_at <= now

    def paid_amount(self) -> int:
        return sum(
            p.amount
            for p in self.payments
            if p.type == PaymentType.PAYMENT and p.status == PaymentStatus.SUCCESS
        )

    def refunded_amount(self) -> int:
        return sum(
            p.amount
            for p in self.payments
            if p.type == PaymentType.REFUND and p.status == PaymentStatus.SUCCESS
        )

    def net_paid(self) -> int:
        """實收 = 成功付款加總 − 成功退款加總（BR-12、17 的計算基準）。"""
        return self.paid_amount() - self.refunded_amount()

    # ---- 查詢條件 ----
    @classmethod
    def occupying(cls, now: datetime):
        """目前佔用時段的訂單：未逾時的待付款，或已確認（用於顯示與搜尋）。"""
        return or_(
            and_(cls.status == BookingStatus.PENDING_PAYMENT.value, cls.expires_at > now),
            cls.status == BookingStatus.CONFIRMED.value,
        )

    # ---- 狀態機 ----
    def transition(
        self,
        to: BookingStatus,
        action: BookingAction,
        actor_id: int | None,
        reason: str | None,
    ) -> BookingStatusLog:
        """唯一可以改變訂單狀態的方法；不合法的轉換拋出 INVALID_STATE。"""
        allowed = _ALLOWED.get(self.status, set())
        if to not in allowed:
            raise ConflictError(
                "INVALID_STATE",
                details={"from": self.status, "to": to.value},
            )
        log = BookingStatusLog(
            from_status=self.status,
            to_status=to.value,
            action=action.value,
            changed_by=actor_id,
            reason=reason,
        )
        self.status = to.value
        self.logs.append(log)
        return log

    def record(
        self, action: BookingAction, actor_id: int | None, reason: str | None
    ) -> BookingStatusLog:
        """不改變狀態、只寫狀態紀錄（改期 RESCHEDULE、部分退款 REFUND）。"""
        log = BookingStatusLog(
            from_status=self.status,
            to_status=self.status,
            action=action.value,
            changed_by=actor_id,
            reason=reason,
        )
        self.logs.append(log)
        return log


class BookingStatusLog(db.Model):
    __tablename__ = "booking_status_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('CREATE','PAY','CANCEL','EXPIRE','COMPLETE','RESCHEDULE','REFUND')",
            name="ck_status_logs_action",
        ),
        Index("ix_booking_status_logs_booking", "booking_id", "created_at"),
    )

    log_id: Mapped[BigId] = mapped_column(primary_key=True)
    booking_id: Mapped[BigId] = mapped_column(db.ForeignKey("bookings.booking_id"))
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(12))
    changed_by: Mapped[BigId | None] = mapped_column(db.ForeignKey("users.user_id"))
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="logs")


class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("type IN ('PAYMENT','REFUND')", name="ck_payments_type"),
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint("method IN ('CREDIT_CARD','LINE_PAY')", name="ck_payments_method"),
        CheckConstraint("status IN ('SUCCESS','FAILED')", name="ck_payments_status"),
        CheckConstraint(
            "(status = 'SUCCESS') = (transaction_no IS NOT NULL)",
            name="ck_payments_txn",
        ),
        Index("ix_payments_booking", "booking_id"),
    )

    payment_id: Mapped[BigId] = mapped_column(primary_key=True)
    booking_id: Mapped[BigId] = mapped_column(db.ForeignKey("bookings.booking_id"))
    type: Mapped[str] = mapped_column(String(8))
    amount: Mapped[int]
    method: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(8))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    transaction_no: Mapped[str | None] = mapped_column(String(40))
    created_by: Mapped[BigId | None] = mapped_column(db.ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="payments")


class AccessCode(db.Model):
    __tablename__ = "access_codes"
    __table_args__ = (
        CheckConstraint("code ~ '^[0-9]{6}$'", name="ck_access_codes_code"),
        CheckConstraint("valid_until > valid_from", name="ck_access_codes_range"),
    )

    code_id: Mapped[BigId] = mapped_column(primary_key=True)
    booking_id: Mapped[BigId] = mapped_column(db.ForeignKey("bookings.booking_id"), unique=True)
    code: Mapped[str] = mapped_column(db.CHAR(6))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="access_code")

    def state(self, now: datetime) -> AccessCodeState:
        """BR-11：查詢時即時計算，不依賴清理排程。"""
        if self.revoked_at is not None:
            return AccessCodeState.REVOKED
        if now < self.valid_from:
            return AccessCodeState.NOT_YET_VALID
        if now > self.valid_until:
            return AccessCodeState.EXPIRED
        return AccessCodeState.VALID

    def is_valid(self, now: datetime) -> bool:
        return self.state(now) == AccessCodeState.VALID
