"""NotificationService：通知紀錄與寄信。

enqueue() 在交易內寫入 PENDING 紀錄；send_pending() 在交易提交後才寄信（C13、D6）。
信件內容不存入資料庫（含權杖連結）：訂單類信件重寄時由訂單資料重新組出。
"""

from __future__ import annotations

import threading

from sqlalchemy import func, select

from ..errors import NotFoundError, ValidationError
from ..extensions import db
from ..mail.sender import Mailer
from ..mail.templates import booking_mail, token_mail
from ..models import Booking, NotificationLog, NotificationType, SendStatus, User
from ..schemas.admin import NotificationDTO
from ..schemas.base import Page
from ..utils.clock import Clock

_BOOKING_TYPES = (
    NotificationType.BOOKING_CONFIRMED,
    NotificationType.BOOKING_CANCELLED,
    NotificationType.BOOKING_RESCHEDULED,
)
MAX_ATTEMPTS = 3


class NotificationService:
    def __init__(self, clock: Clock, mailer: Mailer) -> None:
        self.clock = clock
        self.mailer = mailer
        self._local = threading.local()

    @property
    def _outbox(self) -> dict[int, str]:
        """本執行緒暫存的信件內文（尚未寄出的）。"""
        if not hasattr(self._local, "box"):
            self._local.box = {}
        return self._local.box

    def enqueue(
        self,
        user: User,
        type_: NotificationType,
        booking: Booking | None = None,
        context: dict | None = None,
    ) -> NotificationLog:
        if booking is not None:
            subject, body = booking_mail(type_, booking)
        else:
            subject, body = token_mail(type_, user.name, (context or {})["link"])
        log = NotificationLog(
            user_id=user.user_id,
            booking_id=booking.booking_id if booking is not None else None,
            type=type_.value,
            recipient=user.email,
            subject=subject,
            status=SendStatus.PENDING.value,
            attempts=0,
        )
        db.session.add(log)
        db.session.flush()
        self._outbox[log.notification_id] = body
        return log

    def send_pending(self, ids: list[int] | None = None) -> None:
        """寄出本執行緒暫存的信件並更新結果。須在交易提交後呼叫；寄信失敗不影響訂單。"""
        targets = list(self._outbox) if ids is None else ids
        for nid in targets:
            body = self._outbox.pop(nid, None)
            log = db.session.get(NotificationLog, nid)
            if log is not None and body is not None:
                self._deliver(log, body)
        db.session.commit()

    def _deliver(self, log: NotificationLog, body: str) -> None:
        log.attempts += 1
        try:
            self.mailer.send(log.recipient, log.subject, body)
            log.status = SendStatus.SENT.value
            log.sent_at = self.clock.now()
            log.error_message = None
        except Exception as exc:  # noqa: BLE001 寄信失敗只記錄，不影響主流程
            log.status = SendStatus.FAILED.value
            log.error_message = str(exc)[:500]

    def _rebuild_body(self, log: NotificationLog) -> str:
        booking = db.session.get(Booking, log.booking_id) if log.booking_id else None
        if booking is None or log.type not in _BOOKING_TYPES:
            raise ValidationError("VALIDATION_ERROR", "此類通知含單次權杖，請請使用者重新申請")
        return booking_mail(NotificationType(log.type), booking)[1]

    def retry(self, notification_id: int) -> NotificationDTO:
        log = db.session.execute(
            select(NotificationLog).where(NotificationLog.notification_id == notification_id)
        ).scalar_one_or_none()
        if log is None:
            raise NotFoundError()
        self._deliver(log, self._rebuild_body(log))
        db.session.commit()
        return NotificationDTO.model_validate(log)

    def retry_failed(self) -> int:
        """排程：重試 FAILED 且 attempts < 3 的訂單類通知；鎖定避免重複寄送。"""
        rows = (
            db.session.execute(
                select(NotificationLog)
                .where(
                    NotificationLog.status == SendStatus.FAILED.value,
                    NotificationLog.attempts < MAX_ATTEMPTS,
                    NotificationLog.type.in_([t.value for t in _BOOKING_TYPES]),
                )
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )
        count = 0
        for log in rows:
            self._deliver(log, self._rebuild_body(log))
            count += 1
        db.session.commit()
        return count

    def search(self, status: str | None, page: int, page_size: int = 20) -> Page[NotificationDTO]:
        stmt = select(NotificationLog)
        if status:
            stmt = stmt.where(NotificationLog.status == status)
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            db.session.execute(
                stmt.order_by(NotificationLog.notification_id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            .scalars()
            .all()
        )
        return Page[NotificationDTO](
            items=[NotificationDTO.model_validate(r) for r in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def count_failed(self) -> int:
        return (
            db.session.scalar(
                select(func.count()).where(NotificationLog.status == SendStatus.FAILED.value)
            )
            or 0
        )
