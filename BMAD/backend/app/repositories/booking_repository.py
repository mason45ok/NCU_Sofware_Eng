"""BookingRepository：訂單相關的資料存取（窄版）。

只收納 BookingService 用到的查詢、鎖定與分頁；交易的開始與結束（commit／rollback）由
Service 決定，這裡只轉交給同一個 session，確保「訂單變更＋金流紀錄」仍在同一個交易。
防止重複預約依賴資料庫排除約束 ex_bookings_no_overlap，不在此做「先查再新增」。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from ..extensions import db
from ..models import Booking, BookingStatus, Space, User

TABS = ("pending", "upcoming", "completed", "closed")


class BookingRepository:
    # ---------- 單筆讀取與鎖定 ----------
    def get(self, booking_id: int) -> Booking | None:
        return db.session.get(Booking, booking_id)

    def get_locked(self, booking_id: int) -> Booking | None:
        """鎖定訂單列（FOR UPDATE）並以資料庫最新內容覆蓋快取。"""
        return db.session.execute(
            select(Booking)
            .where(Booking.booking_id == booking_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()

    def get_space(self, space_id: int) -> Space | None:
        return db.session.get(Space, space_id)

    def get_user(self, user_id: int) -> User | None:
        return db.session.get(User, user_id)

    def get_user_locked(self, user_id: int) -> User:
        """鎖定使用者列，防止同一人併發突破待付款上限（BR-06）。"""
        return db.session.execute(
            select(User)
            .where(User.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()

    # ---------- 計數與序號 ----------
    def count_pending(self, user_id: int, now: datetime) -> int:
        return db.session.scalar(
            select(func.count()).where(
                Booking.user_id == user_id,
                Booking.status == BookingStatus.PENDING_PAYMENT.value,
                Booking.expires_at > now,
            )
        )

    def next_id(self) -> int:
        return db.session.scalar(
            select(func.nextval(func.pg_get_serial_sequence("bookings", "booking_id")))
        )

    # ---------- 逾時、結束的批次處理（SKIP LOCKED 避開正在付款的訂單） ----------
    def lock_overdue_pending_for(self, user_id: int, space_id: int, now: datetime) -> list[Booking]:
        """BR-08：指定使用者或指定空間的逾時待付款訂單。"""
        return list(
            db.session.execute(
                select(Booking)
                .where(
                    Booking.status == BookingStatus.PENDING_PAYMENT.value,
                    Booking.expires_at <= now,
                    or_(Booking.user_id == user_id, Booking.space_id == space_id),
                )
                .with_for_update(skip_locked=True)
            ).scalars()
        )

    def lock_overdue_pending(self, now: datetime) -> list[Booking]:
        """FR-50：所有逾時待付款訂單。"""
        return list(
            db.session.execute(
                select(Booking)
                .where(
                    Booking.status == BookingStatus.PENDING_PAYMENT.value,
                    Booking.expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )

    def lock_finished(self, now: datetime) -> list[Booking]:
        """FR-51、BR-15：結束時間已到的已確認訂單。"""
        return list(
            db.session.execute(
                select(Booking)
                .where(
                    Booking.status == BookingStatus.CONFIRMED.value,
                    Booking.end_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )

    # ---------- 列表 ----------
    def list_by_tab(
        self, user_id: int, tab: str, now: datetime, page: int, page_size: int
    ) -> tuple[list[Booking], int]:
        """FR-30：待付款、即將到來、已完成、已取消／已失效；回傳 (該頁訂單, 總筆數)。"""
        pending, confirmed = (
            BookingStatus.PENDING_PAYMENT.value,
            BookingStatus.CONFIRMED.value,
        )
        cond, order = {
            "pending": (
                and_(Booking.status == pending, Booking.expires_at > now),
                Booking.created_at.desc(),
            ),
            "upcoming": (
                and_(Booking.status == confirmed, Booking.end_at > now),
                Booking.start_at.asc(),
            ),
            "completed": (
                or_(
                    Booking.status == BookingStatus.COMPLETED.value,
                    and_(Booking.status == confirmed, Booking.end_at <= now),
                ),
                Booking.start_at.desc(),
            ),
            "closed": (
                or_(
                    Booking.status.in_(
                        [BookingStatus.CANCELLED.value, BookingStatus.EXPIRED.value]
                    ),
                    and_(Booking.status == pending, Booking.expires_at <= now),
                ),
                Booking.created_at.desc(),
            ),
        }[tab]
        stmt = select(Booking).where(Booking.user_id == user_id, cond)
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            db.session.execute(stmt.order_by(order).limit(page_size).offset((page - 1) * page_size))
            .scalars()
            .all()
        )
        return list(rows), total

    def list_active_in_spaces(self, space_ids: list[int], now: datetime) -> list[Booking]:
        """BR-18：指定空間的未來有效訂單（待付款未逾時與已確認）。"""
        return list(
            db.session.execute(
                select(Booking)
                .where(
                    Booking.space_id.in_(space_ids),
                    Booking.end_at > now,
                    or_(
                        Booking.status == BookingStatus.CONFIRMED.value,
                        and_(
                            Booking.status == BookingStatus.PENDING_PAYMENT.value,
                            Booking.expires_at > now,
                        ),
                    ),
                )
                .order_by(Booking.start_at)
            ).scalars()
        )

    def has_slot_conflict(
        self, booking: Booking, start_at: datetime, end_at: datetime, now: datetime
    ) -> bool:
        """改期試算用：同空間其他佔用中的訂單是否與新時段重疊（只用於顯示，最終仍由排除約束保證）。"""
        return (
            db.session.scalar(
                select(func.count()).where(
                    Booking.space_id == booking.space_id,
                    Booking.booking_id != booking.booking_id,
                    Booking.occupying(now),
                    Booking.start_at < end_at,
                    Booking.end_at > start_at,
                )
            )
            > 0
        )

    # ---------- 寫入與交易（交易邊界由 Service 決定） ----------
    def add(self, booking: Booking) -> None:
        db.session.add(booking)

    def flush(self) -> None:
        db.session.flush()

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
