"""ReviewService：評論的查詢與寫入（C6）。透過 BookingService 確認訂單屬於本人。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..errors import BusinessRuleError, NotFoundError
from ..extensions import db
from ..models import Booking, BookingStatus, Review, Space
from ..schemas.account import UserDTO
from ..schemas.base import Page
from ..schemas.catalog import ReviewDTO
from ..utils.clock import Clock
from .booking import REVIEW_WINDOW, BookingService


def _mask(name: str) -> str:
    """評論者名稱只顯示第一個字。"""
    return (name[:1] or "會") + "○○"


class ReviewService:
    def __init__(self, clock: Clock, bookings: BookingService) -> None:
        self.clock = clock
        self.bookings = bookings

    def create(self, user: UserDTO, booking_id: int, rating: int, comment: str | None) -> ReviewDTO:
        """BR-16：本人、已完成、自 end_at 起 30 天內、每單一則。"""
        booking = self.bookings.get_for_owner(user, booking_id)  # 非本人 → 404
        if booking.status != BookingStatus.COMPLETED:
            raise BusinessRuleError("REVIEW_NOT_ALLOWED", "訂單完成後才能評論")
        if self.clock.now() > booking.end_at + REVIEW_WINDOW:
            raise BusinessRuleError("REVIEW_NOT_ALLOWED", "已超過評論期限（結束後 30 天內）")
        if booking.reviewed:
            raise BusinessRuleError("REVIEW_NOT_ALLOWED", "此訂單已評論過")
        review = Review(booking_id=booking_id, rating=rating, comment=comment or None)
        db.session.add(review)
        try:
            db.session.commit()
        except IntegrityError:  # 併發重複送出
            db.session.rollback()
            raise BusinessRuleError("REVIEW_NOT_ALLOWED", "此訂單已評論過") from None
        return self._dto(review)

    def list_for_space(self, space_id: int, page: int = 1, page_size: int = 10) -> Page[ReviewDTO]:
        """公開評論列表（不含隱藏者）。"""
        if db.session.get(Space, space_id) is None:
            raise NotFoundError()
        stmt = (
            select(Review)
            .join(Booking, Booking.booking_id == Review.booking_id)
            .where(Booking.space_id == space_id, Review.is_hidden.is_(False))
        )
        return self._page(stmt, page, page_size)

    def list_all(self, page: int = 1, page_size: int = 20) -> Page[ReviewDTO]:
        """管理後台：全部評論（FR-47）。"""
        return self._page(select(Review), page, page_size)

    def set_hidden(self, review_id: int, hidden: bool) -> ReviewDTO:
        review = db.session.get(Review, review_id)
        if review is None:
            raise NotFoundError()
        review.is_hidden = hidden
        db.session.commit()
        return self._dto(review)

    def _page(self, stmt, page: int, page_size: int) -> Page[ReviewDTO]:
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            db.session.execute(
                stmt.order_by(Review.review_id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            .scalars()
            .all()
        )
        return Page[ReviewDTO](
            items=[self._dto(r) for r in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    @staticmethod
    def _dto(review: Review) -> ReviewDTO:
        booking = review.booking
        return ReviewDTO(
            review_id=review.review_id,
            booking_id=booking.booking_id,
            space_id=booking.space_id,
            space_name=booking.space.name,
            reviewer=_mask(booking.user.name),
            rating=review.rating,
            comment=review.comment,
            is_hidden=review.is_hidden,
            created_at=review.created_at,
        )
