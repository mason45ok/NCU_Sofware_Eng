"""BookingService：訂單流程的唯一入口（C1、C2）。

建立、付款、取消、改期、部分退款、逾時與完成都由它協調。只有它能寫入 bookings、
booking_status_logs 與退款；狀態一律透過 Booking.transition() 改變，其餘紀錄用 Booking.record()。
所有寫入流程在單一資料庫交易內完成，寄信在提交後執行（ARCHITECTURE.md 第 6 節）。
"""

from __future__ import annotations

import functools
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from ..errors import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from ..extensions import db
from ..models import (
    Booking,
    BookingAction,
    BookingStatus,
    NotificationType,
    PaymentStatus,
    PaymentType,
    Role,
    Space,
    User,
    UserStatus,
)
from ..policies import pricing, refund
from ..schemas.account import UserDTO
from ..schemas.base import Page
from ..schemas.booking import (
    BookingDTO,
    CreateBookingReq,
    NewSlot,
    PaymentDTO,
    PayResultDTO,
    QuoteDTO,
    QuoteReq,
    RefundQuoteDTO,
    RescheduleQuoteDTO,
)
from ..utils.clock import Clock
from ..utils.time import format_local, local_date, to_taipei
from .access_code import AccessCodeService
from .availability import AvailabilityService
from .notification import NotificationService
from .payment import PaymentService

PAYMENT_DEADLINE_MINUTES = 15
PENDING_LIMIT = 3
RESCHEDULE_MIN_LEAD = timedelta(hours=24)
REVIEW_WINDOW = timedelta(days=30)
TABS = ("pending", "upcoming", "completed", "closed")


def _transactional(fn):
    """任何例外都回滾整個交易（原訂單不變）。"""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            db.session.rollback()
            raise

    return wrapper


def _is_exclusion_violation(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == "23P01"


class BookingService:
    def __init__(
        self,
        clock: Clock,
        availability: AvailabilityService,
        payments: PaymentService,
        access_codes: AccessCodeService,
        notifications: NotificationService,
    ) -> None:
        self.clock = clock
        self.availability = availability
        self.payments = payments
        self.access_codes = access_codes
        self.notifications = notifications

    # ================= 共用 =================
    def _lock(self, booking_id: int, owner_id: int | None = None) -> Booking:
        """鎖定訂單列（FOR UPDATE）；owner_id 不符一律回 404（不透露存在與否）。"""
        booking = db.session.execute(
            select(Booking)
            .where(Booking.booking_id == booking_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if booking is None or (owner_id is not None and booking.user_id != owner_id):
            raise NotFoundError()
        return booking

    def _owned(self, user: UserDTO, booking_id: int) -> Booking:
        booking = db.session.get(Booking, booking_id)
        if booking is None or booking.user_id != user.user_id:
            raise NotFoundError()
        return booking

    @staticmethod
    def _require_admin(admin: UserDTO) -> None:
        if admin.role != Role.ADMIN:
            raise ForbiddenError("FORBIDDEN")

    @staticmethod
    def _require_can_book(user: User) -> None:
        """BR-05：帳號 ACTIVE 且 email 已驗證。"""
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenError("ACCOUNT_RESTRICTED")
        if not user.is_email_verified():
            raise ForbiddenError("EMAIL_NOT_VERIFIED")

    def to_dto(self, b: Booking) -> BookingDTO:
        now = self.clock.now()
        space, branch = b.space, b.space.branch
        pending = b.status == BookingStatus.PENDING_PAYMENT
        confirmed = b.status == BookingStatus.CONFIRMED
        return BookingDTO(
            booking_id=b.booking_id,
            booking_no=b.booking_no,
            status=b.status,
            space_id=space.space_id,
            space_name=space.name,
            branch_name=branch.name,
            branch_address=f"{branch.city}{branch.district}{branch.address}",
            branch_phone=branch.phone,
            entry_guide=space.entry_guide,
            user_id=b.user_id,
            user_email=b.user.email,
            start_at=b.start_at,
            end_at=b.end_at,
            hours=b.hours(),
            attendees=b.attendees,
            note=b.note,
            hourly_price_snapshot=b.hourly_price_snapshot,
            total_amount=b.total_amount,
            expires_at=b.expires_at,
            reschedule_count=b.reschedule_count,
            cancelled_by=b.cancelled_by,
            cancel_reason=b.cancel_reason,
            cancelled_at=b.cancelled_at,
            net_paid=b.net_paid(),
            payments=[PaymentDTO.model_validate(p) for p in b.payments],
            access_code=self.access_codes.view(b),
            can_cancel=(pending and b.expires_at > now) or (confirmed and b.end_at > now),
            can_reschedule=confirmed
            and b.reschedule_count == 0
            and b.start_at - now >= RESCHEDULE_MIN_LEAD,
            can_review=b.status == BookingStatus.COMPLETED
            and b.review is None
            and now <= b.end_at + REVIEW_WINDOW,
            reviewed=b.review is not None,
            created_at=b.created_at,
        )

    def _check_request(self, space: Space, attendees: int, start_at, end_at) -> int:
        """BR-01、02、04 的共用檢查；回傳時數。"""
        if not space.is_bookable():
            raise BusinessRuleError("SPACE_UNAVAILABLE")
        if attendees > space.capacity:
            raise BusinessRuleError(
                "OVER_CAPACITY",
                details={"capacity": space.capacity, "attendees": attendees},
            )
        self.availability.validate_slot(space, start_at, end_at)
        return int((end_at - start_at).total_seconds() // 3600)

    # ================= 試算與建立（6.1） =================
    def quote(self, user: UserDTO, req: QuoteReq) -> QuoteDTO:
        """FR-20：試算金額與檢查時段規則，不建立訂單；與 create() 呼叫同一個 PricingPolicy。"""
        space = db.session.get(Space, req.space_id)
        if space is None:
            raise NotFoundError()
        hours = self._check_request(space, req.attendees, req.start_at, req.end_at)
        return QuoteDTO(
            space_id=space.space_id,
            hours=hours,
            hourly_price=space.hourly_price,
            total_amount=pricing.amount(space.hourly_price, hours),
            payment_deadline_minutes=PAYMENT_DEADLINE_MINUTES,
            cancel_policy=refund.CANCEL_POLICY_TEXT,
        )

    @_transactional
    def create(self, user: UserDTO, req: CreateBookingReq) -> BookingDTO:
        now = self.clock.now()
        member = db.session.execute(
            select(User)
            .where(User.user_id == user.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()  # 鎖定使用者列，防止同一人併發突破待付款上限
        self._expire_overdue_for(member.user_id, req.space_id, now)

        pending_count = db.session.scalar(
            select(func.count()).where(
                Booking.user_id == member.user_id,
                Booking.status == BookingStatus.PENDING_PAYMENT.value,
                Booking.expires_at > now,
            )
        )
        if pending_count >= PENDING_LIMIT:
            raise ConflictError("PENDING_LIMIT")
        self._require_can_book(member)

        space = db.session.get(Space, req.space_id)
        if space is None:
            raise NotFoundError()
        hours = self._check_request(space, req.attendees, req.start_at, req.end_at)

        booking_id = db.session.scalar(
            select(func.nextval(func.pg_get_serial_sequence("bookings", "booking_id")))
        )
        booking = Booking(
            booking_id=booking_id,
            booking_no=f"B{local_date(now):%Y%m%d}-{booking_id:04d}",
            user_id=member.user_id,
            space_id=space.space_id,
            start_at=req.start_at,
            end_at=req.end_at,
            attendees=req.attendees,
            note=req.note or None,
            hourly_price_snapshot=space.hourly_price,
            total_amount=pricing.amount(space.hourly_price, hours),
            expires_at=now + timedelta(minutes=PAYMENT_DEADLINE_MINUTES),
            reschedule_count=0,
        )
        booking.transition(
            BookingStatus.PENDING_PAYMENT, BookingAction.CREATE, member.user_id, None
        )
        db.session.add(booking)
        try:
            db.session.flush()  # 重疊由資料庫排除約束保證
        except IntegrityError as exc:
            if _is_exclusion_violation(exc):
                raise ConflictError("SLOT_TAKEN") from exc
            raise
        db.session.commit()
        return self.to_dto(booking)

    def _expire_overdue_for(self, user_id: int, space_id: int, now) -> None:
        """BR-08：建立訂單時先在同一交易中處理該使用者與該空間的逾時待付款訂單。"""
        rows = db.session.execute(
            select(Booking)
            .where(
                Booking.status == BookingStatus.PENDING_PAYMENT.value,
                Booking.expires_at <= now,
                or_(Booking.user_id == user_id, Booking.space_id == space_id),
            )
            .with_for_update(skip_locked=True)
        ).scalars()
        for booking in rows:
            booking.transition(BookingStatus.EXPIRED, BookingAction.EXPIRE, None, "付款逾時")
        db.session.flush()

    # ================= 付款（6.2） =================
    @_transactional
    def pay(
        self, user: UserDTO, booking_id: int, method: str, card_no: str | None, key: str
    ) -> PayResultDTO:
        now = self.clock.now()
        booking = self._lock(booking_id, user.user_id)  # 先鎖再查冪等鍵

        existing = self.payments.find_by_key(key)
        if existing is not None:
            if existing.booking_id != booking.booking_id or existing.type != PaymentType.PAYMENT:
                raise ConflictError("IDEMPOTENCY_KEY_REUSED")
            return self._pay_result(booking, existing.status == PaymentStatus.SUCCESS)

        if booking.status == BookingStatus.EXPIRED:
            raise ConflictError("BOOKING_EXPIRED")
        if booking.status != BookingStatus.PENDING_PAYMENT:
            raise ConflictError("INVALID_STATE", details={"status": booking.status})
        member = db.session.get(User, user.user_id)
        self._require_can_book(member)
        if not booking.space.is_bookable():  # BR-18：停用後待付款訂單也不能付款
            raise BusinessRuleError("SPACE_UNAVAILABLE", "此空間已暫停開放，無法付款，請取消訂單")
        if booking.is_payment_overdue(now):
            booking.transition(BookingStatus.EXPIRED, BookingAction.EXPIRE, None, "付款逾時")
            db.session.commit()
            raise ConflictError("BOOKING_EXPIRED")

        try:
            result = self.payments.charge(
                booking.booking_id,
                booking.total_amount,
                method,
                card_no,
                key,
                user.user_id,
            )
        except IntegrityError:  # 極少見的鍵競爭：回傳既有結果
            db.session.rollback()
            existing = self.payments.find_by_key(key)
            if existing is None or existing.booking_id != booking_id:
                raise ConflictError("IDEMPOTENCY_KEY_REUSED") from None
            return self._pay_result(
                db.session.get(Booking, booking_id), existing.status == "SUCCESS"
            )

        if not result.success:  # 付款失敗不是錯誤：訂單維持待付款，期限內可重付
            db.session.commit()
            return self._pay_result(booking, False)

        booking.transition(BookingStatus.CONFIRMED, BookingAction.PAY, user.user_id, None)
        self.access_codes.issue(booking)
        self.notifications.enqueue(member, NotificationType.BOOKING_CONFIRMED, booking)
        db.session.commit()
        self.notifications.send_pending()
        return self._pay_result(booking, True)

    def _pay_result(self, booking: Booking, success: bool) -> PayResultDTO:
        return PayResultDTO(
            status="SUCCESS" if success else "FAILED",
            reason=None if success else "CARD_DECLINED",
            booking=self.to_dto(booking),
        )

    # ================= 查詢 =================
    def get_for_owner(self, user: UserDTO, booking_id: int) -> BookingDTO:
        return self.to_dto(self._owned(user, booking_id))

    def list_for_owner(
        self, user: UserDTO, tab: str, page: int = 1, page_size: int = 10
    ) -> Page[BookingDTO]:
        """FR-30：待付款、即將到來、已完成、已取消／已失效。"""
        if tab not in TABS:
            raise ValidationError("VALIDATION_ERROR", details={"tab": list(TABS)})
        now = self.clock.now()
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
        stmt = select(Booking).where(Booking.user_id == user.user_id, cond)
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            db.session.execute(stmt.order_by(order).limit(page_size).offset((page - 1) * page_size))
            .scalars()
            .all()
        )
        return Page[BookingDTO](
            items=[self.to_dto(b) for b in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def list_affected(self, space_ids: list[int]) -> list[BookingDTO]:
        """BR-18：指定空間的未來有效訂單（待付款與已確認），供管理員逐筆處理。"""
        if not space_ids:
            return []
        now = self.clock.now()
        rows = db.session.execute(
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
        return [self.to_dto(b) for b in rows]

    # ================= 取消（6.3） =================
    def _require_cancellable(self, b: Booking) -> None:
        if b.status == BookingStatus.CONFIRMED and b.end_at <= self.clock.now():
            raise ConflictError("INVALID_STATE", "訂單時段已結束，無法取消")

    def _member_ratio(self, b: Booking) -> Decimal:
        if b.status == BookingStatus.PENDING_PAYMENT:
            return Decimal(0)  # 待付款取消不涉及退款
        return refund.member_ratio(b.start_at, self.clock.now())

    def cancel_quote(self, user: UserDTO, booking_id: int) -> RefundQuoteDTO:
        """FR-32：確認前顯示預計退款金額與比例（與正式取消呼叫同一個 RefundPolicy）。"""
        b = self._owned(user, booking_id)
        if b.status not in (BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED):
            raise ConflictError("INVALID_STATE", details={"status": b.status})
        self._require_cancellable(b)
        ratio = self._member_ratio(b)
        amount = refund.refund_amount(b.net_paid(), ratio)
        note = (
            "待付款訂單取消不涉及退款"
            if b.status == BookingStatus.PENDING_PAYMENT
            else f"退款比例 {int(ratio * 100)}%"
        )
        return RefundQuoteDTO(
            status=b.status,
            net_paid=b.net_paid(),
            ratio=float(ratio),
            refund_amount=amount,
            note=note,
        )

    @_transactional
    def cancel_by_member(self, user: UserDTO, booking_id: int) -> BookingDTO:
        b = self._lock(booking_id, user.user_id)
        if b.status == BookingStatus.CANCELLED:  # 冪等：回傳原結果
            return self.to_dto(b)
        self._require_cancellable(b)
        self._cancel(b, self._member_ratio(b), user.user_id, None)
        return self.to_dto(b)

    @_transactional
    def cancel_by_admin(self, admin: UserDTO, booking_id: int, reason: str) -> BookingDTO:
        self._require_admin(admin)
        if not reason or not reason.strip():
            raise ValidationError("VALIDATION_ERROR", "請填寫取消原因", {"reason": "必填"})
        b = self._lock(booking_id)
        if b.status == BookingStatus.CANCELLED:
            return self.to_dto(b)
        self._require_cancellable(b)
        self._cancel(b, refund.admin_ratio(), admin.user_id, reason.strip())
        return self.to_dto(b)

    def _cancel(self, b: Booking, ratio: Decimal, actor_id: int, reason: str | None) -> None:
        """共用核心：退款（以實收為基準）、記錄取消者、轉 CANCELLED、撤銷房間密碼、通知。"""
        amount = (
            0
            if b.status == BookingStatus.PENDING_PAYMENT
            else refund.refund_amount(b.net_paid(), ratio)
        )
        if amount > 0:
            self.payments.refund(b.booking_id, amount, f"refund-cancel-{b.booking_id}", actor_id)
        b.cancelled_by, b.cancel_reason, b.cancelled_at = (
            actor_id,
            reason,
            self.clock.now(),
        )
        b.transition(BookingStatus.CANCELLED, BookingAction.CANCEL, actor_id, reason)
        self.access_codes.revoke(b)
        self.notifications.enqueue(b.user, NotificationType.BOOKING_CANCELLED, b)
        db.session.commit()
        self.notifications.send_pending()

    # ================= 改期（6.4） =================
    def _check_member_reschedule(self, b: Booking, member: User) -> None:
        if b.status != BookingStatus.CONFIRMED:
            raise ConflictError("INVALID_STATE", "只有已確認的訂單可以改期")
        self._require_can_book(member)
        if b.start_at - self.clock.now() < RESCHEDULE_MIN_LEAD:
            raise BusinessRuleError(
                "RESCHEDULE_NOT_ALLOWED",
                "距離原訂單開始不足 24 小時，無法改期；如需協助請聯絡客服",
            )
        if b.reschedule_count >= 1:
            raise BusinessRuleError("RESCHEDULE_NOT_ALLOWED", "每筆訂單最多只能改期 1 次")

    def _slot_conflicts(self, b: Booking, slot: NewSlot) -> bool:
        return (
            db.session.scalar(
                select(func.count()).where(
                    Booking.space_id == b.space_id,
                    Booking.booking_id != b.booking_id,
                    Booking.occupying(self.clock.now()),
                    Booking.start_at < slot.end_at,
                    Booking.end_at > slot.start_at,
                )
            )
            > 0
        )

    def reschedule_quote(self, user: UserDTO, booking_id: int, slot: NewSlot) -> RescheduleQuoteDTO:
        """FR-33：新時段的價差試算（與正式改期呼叫同一個 PricingPolicy）。"""
        b = self._owned(user, booking_id)
        self._check_member_reschedule(b, db.session.get(User, user.user_id))
        if not b.space.is_bookable():
            raise BusinessRuleError("SPACE_UNAVAILABLE")
        self.availability.validate_slot(b.space, slot.start_at, slot.end_at)
        if self._slot_conflicts(b, slot):
            raise ConflictError("SLOT_TAKEN")
        new_hours = int((slot.end_at - slot.start_at).total_seconds() // 3600)
        diff = pricing.reschedule_diff(b.hourly_price_snapshot, b.hours(), new_hours)
        return RescheduleQuoteDTO(
            old_amount=b.total_amount,
            new_amount=pricing.amount(b.hourly_price_snapshot, new_hours),
            diff=diff,
            new_hours=new_hours,
            requires_payment=diff > 0,
            refund_amount=max(-diff, 0),
        )

    @_transactional
    def reschedule_by_member(
        self,
        user: UserDTO,
        booking_id: int,
        slot: NewSlot,
        method: str | None,
        card_no: str | None,
        key: str | None,
    ) -> BookingDTO:
        b = self._lock(booking_id, user.user_id)
        if b.start_at == slot.start_at and b.end_at == slot.end_at:  # 重送請求的冪等處理
            return self.to_dto(b)
        self._check_member_reschedule(b, db.session.get(User, user.user_id))
        new_hours = int((slot.end_at - slot.start_at).total_seconds() // 3600)
        needs_payment = pricing.reschedule_diff(b.hourly_price_snapshot, b.hours(), new_hours) > 0
        if needs_payment and (not method or not key):
            raise ValidationError(
                "VALIDATION_ERROR", "改期需補付差額，請選擇付款方式", {"method": "必填"}
            )
        b.reschedule_count += 1
        self._reschedule(b, slot, user.user_id, None, (method, card_no, key))
        return self.to_dto(b)

    @_transactional
    def reschedule_by_admin(
        self, admin: UserDTO, booking_id: int, slot: NewSlot, reason: str
    ) -> BookingDTO:
        """BR-19：只能選相同時數（不涉及補付或退款），不受 24 小時與 1 次限制，不計入 reschedule_count。"""
        self._require_admin(admin)
        if not reason or not reason.strip():
            raise ValidationError("VALIDATION_ERROR", "請填寫改期原因", {"reason": "必填"})
        b = self._lock(booking_id)
        if b.start_at == slot.start_at and b.end_at == slot.end_at:
            return self.to_dto(b)
        if b.status not in (BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED):
            raise ConflictError("INVALID_STATE", details={"status": b.status})
        if int((slot.end_at - slot.start_at).total_seconds() // 3600) != b.hours():
            raise BusinessRuleError(
                "RESCHEDULE_NOT_ALLOWED", "管理員代為改期的時數必須與原訂單相同"
            )
        self._reschedule(b, slot, admin.user_id, reason.strip(), None)
        return self.to_dto(b)

    def _reschedule(
        self,
        b: Booking,
        slot: NewSlot,
        actor_id: int,
        note: str | None,
        pay: tuple[str | None, str | None, str | None] | None,
    ) -> None:
        """共用核心：驗證新時段、更新時段與金額、補付或退差額、同步房間密碼、寫紀錄、通知。"""
        if not b.space.is_bookable():
            raise BusinessRuleError("SPACE_UNAVAILABLE")
        self.availability.validate_slot(b.space, slot.start_at, slot.end_at)
        old = f"{format_local(b.start_at)}～{to_taipei(b.end_at):%H:%M}"
        new_hours = int((slot.end_at - slot.start_at).total_seconds() // 3600)
        diff = pricing.reschedule_diff(b.hourly_price_snapshot, b.hours(), new_hours)

        b.start_at, b.end_at = slot.start_at, slot.end_at
        b.total_amount = pricing.amount(b.hourly_price_snapshot, new_hours)
        try:
            db.session.flush()  # 與他人重疊時由排除約束拒絕，整個交易回滾
        except IntegrityError as exc:
            if _is_exclusion_violation(exc):
                raise ConflictError("SLOT_TAKEN") from exc
            raise

        if diff > 0:
            method, card_no, key = pay
            if self.payments.find_by_key(key) is not None:
                raise ConflictError("IDEMPOTENCY_KEY_REUSED")
            charged = self.payments.charge(b.booking_id, diff, method, card_no, key, actor_id)
            if not charged.success:
                raise BusinessRuleError(
                    "RESCHEDULE_NOT_ALLOWED",
                    "補付差額時卡片遭拒，原訂單未變更，請更換付款方式後重試",
                    {"reason": "CARD_DECLINED"},
                )
        elif diff < 0:
            if -diff > b.net_paid():
                raise BusinessRuleError("REFUND_EXCEEDS_PAID")
            self.payments.refund(b.booking_id, -diff, f"refund-resched-{b.booking_id}", actor_id)

        self.access_codes.sync_validity(b)
        reason = f"{old} → {format_local(b.start_at)}～{to_taipei(b.end_at):%H:%M}"
        if note:
            reason += f"（{note}）"
        b.record(BookingAction.RESCHEDULE, actor_id, reason[:200])
        self.notifications.enqueue(b.user, NotificationType.BOOKING_RESCHEDULED, b)
        db.session.commit()
        self.notifications.send_pending()

    # ================= 部分退款（6.5） =================
    @_transactional
    def refund_partially(
        self,
        admin: UserDTO,
        booking_id: int,
        amount: int,
        key: str,
        reason: str | None = None,
    ) -> PaymentDTO:
        self._require_admin(admin)
        b = self._lock(booking_id)
        existing = self.payments.find_by_key(key)
        if existing is not None:
            if existing.booking_id != b.booking_id or existing.type != PaymentType.REFUND:
                raise ConflictError("IDEMPOTENCY_KEY_REUSED")
            return PaymentDTO.model_validate(existing)
        if amount <= 0:
            raise ValidationError("VALIDATION_ERROR", details={"amount": "須大於 0"})
        if amount > b.net_paid():
            raise BusinessRuleError(
                "REFUND_EXCEEDS_PAID",
                details={"net_paid": b.net_paid(), "amount": amount},
            )
        payment = self.payments.refund(b.booking_id, amount, key, admin.user_id)
        b.record(
            BookingAction.REFUND,
            admin.user_id,
            (reason or f"部分退款 NT$ {amount}")[:200],
        )
        db.session.commit()
        return PaymentDTO.model_validate(payment)

    # ================= 排程 =================
    def expire_overdue(self) -> int:
        """FR-50：逾時待付款轉 EXPIRED；SKIP LOCKED 避開正在付款的訂單，重跑不影響已處理者。"""
        rows = (
            db.session.execute(
                select(Booking)
                .where(
                    Booking.status == BookingStatus.PENDING_PAYMENT.value,
                    Booking.expires_at <= self.clock.now(),
                )
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )
        for b in rows:
            b.transition(BookingStatus.EXPIRED, BookingAction.EXPIRE, None, "付款逾時")
        db.session.commit()
        return len(rows)

    def complete_finished(self) -> int:
        """FR-51：結束時間到達的已確認訂單轉 COMPLETED（BR-15）。"""
        rows = (
            db.session.execute(
                select(Booking)
                .where(
                    Booking.status == BookingStatus.CONFIRMED.value,
                    Booking.end_at <= self.clock.now(),
                )
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )
        for b in rows:
            b.transition(BookingStatus.COMPLETED, BookingAction.COMPLETE, None, None)
        db.session.commit()
        return len(rows)
