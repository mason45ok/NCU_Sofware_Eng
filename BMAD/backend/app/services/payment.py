"""PaymentService：只負責呼叫金流 Adapter 與寫入 payments，不依賴其他 Service（C1）。

金流由 PaymentGatewayFactory 依付款方式提供；charge()、refund() 不開交易，由 BookingService 的交易包住。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from ..adapters.payment import PaymentGatewayFactory, build_default_factory
from ..extensions import db
from ..models import Booking, Payment, PaymentMethod, PaymentStatus, PaymentType
from ..security.tokens import new_transaction_no


@dataclass(frozen=True)
class ChargeResult:
    payment: Payment
    success: bool
    reason: str | None = None


class PaymentService:
    def __init__(self, gateways: PaymentGatewayFactory | None = None) -> None:
        self.gateways = gateways or build_default_factory()

    def find_by_key(self, key: str) -> Payment | None:
        return db.session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        ).scalar_one_or_none()

    def charge(
        self,
        booking_id: int,
        amount: int,
        method: str,
        card_no: str | None,
        key: str,
        actor_id: int | None,
    ) -> ChargeResult:
        booking = db.session.get(Booking, booking_id)
        outcome = self.gateways.create(method).pay(amount, booking.booking_no, card_no)
        ok = outcome.success
        payment = Payment(
            type=PaymentType.PAYMENT.value,
            amount=amount,
            method=method,
            status=(PaymentStatus.SUCCESS if ok else PaymentStatus.FAILED).value,
            idempotency_key=key,
            transaction_no=new_transaction_no() if ok else None,
            created_by=actor_id,
        )
        booking.payments.append(payment)
        db.session.flush()
        return ChargeResult(payment, ok, outcome.reason)

    def refund(self, booking_id: int, amount: int, key: str, actor_id: int | None) -> Payment:
        """新增 REFUND 紀錄（不修改原付款）；退款方式沿用原付款；同一鍵只退一次。"""
        existing = self.find_by_key(key)
        if existing is not None:
            return existing
        booking = db.session.get(Booking, booking_id)
        original = next(
            (
                p
                for p in reversed(booking.payments)
                if p.type == PaymentType.PAYMENT and p.status == PaymentStatus.SUCCESS
            ),
            None,
        )
        payment = Payment(
            type=PaymentType.REFUND.value,
            amount=amount,
            method=original.method if original else PaymentMethod.CREDIT_CARD.value,
            status=PaymentStatus.SUCCESS.value,
            idempotency_key=key,
            transaction_no=new_transaction_no(),
            created_by=actor_id,
        )
        booking.payments.append(payment)
        db.session.flush()
        return payment
