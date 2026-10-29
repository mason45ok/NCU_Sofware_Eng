"""reviews、user_favorites、notification_logs（D1、D2-2）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .columns import BigId
from .enums import SendStatus


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),)

    review_id: Mapped[BigId] = mapped_column(primary_key=True)
    booking_id: Mapped[BigId] = mapped_column(db.ForeignKey("bookings.booking_id"), unique=True)
    rating: Mapped[int] = mapped_column(db.SmallInteger)
    comment: Mapped[str | None] = mapped_column(String(500))
    is_hidden: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    booking = relationship("Booking", back_populates="review")


class UserFavorite(db.Model):
    __tablename__ = "user_favorites"

    user_id: Mapped[BigId] = mapped_column(
        db.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    space_id: Mapped[BigId] = mapped_column(
        db.ForeignKey("spaces.space_id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"
    __table_args__ = (
        CheckConstraint(
            "type IN ('VERIFY_EMAIL','RESET_PASSWORD','SET_PASSWORD',"
            "'BOOKING_CONFIRMED','BOOKING_CANCELLED','BOOKING_RESCHEDULED')",
            name="ck_notifications_type",
        ),
        CheckConstraint("status IN ('PENDING','SENT','FAILED')", name="ck_notifications_status"),
        CheckConstraint("attempts >= 0", name="ck_notifications_attempts"),
        Index("ix_notification_logs_status", "status", "created_at"),
    )

    notification_id: Mapped[BigId] = mapped_column(primary_key=True)
    user_id: Mapped[BigId] = mapped_column(db.ForeignKey("users.user_id"))
    booking_id: Mapped[BigId | None] = mapped_column(db.ForeignKey("bookings.booking_id"))
    type: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(8), default=SendStatus.PENDING.value, server_default="PENDING"
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    error_message: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
