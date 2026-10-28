"""PaymentService：只負責模擬金流與寫入 payments，不依賴其他 Service（C1）。

charge()、refund() 不開交易，由 BookingService 的交易包住。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select

from ..extensions import db
from ..models import Booking, Payment, PaymentMethod, PaymentStatus, PaymentType
from ..security.tokens import new_transaction_no

DECLINED_CARD = "4000000000000002"


@dataclass(frozen=True)
class ChargeResult:
    payment: Payment
    success: bool


class PaymentService:
    def find_by_key(self, key: str) -> Payment | None:
        return db.session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        ).scalar_one_or_none()

    def simulate_gateway(self, method: str, card_no: str | None) -> bool:
        """模擬金流：信用卡號 4000 0000 0000 0002 一律遭拒（BR-09），其餘成功。"""
        if method == PaymentMethod.CREDIT_CARD and card_no:
            return re.sub(r"\D", "", card_no) != DECLINED_CARD
        return True

    def charge(
        self,
        booking_id: int,
        amount: int,
        method: str,
        card_no: str | None,
        key: str,
        actor_id: int | None,
    ) -> ChargeResult:
        ok = self.simulate_gateway(method, card_no)
        payment = Payment(
            type=PaymentType.PAYMENT.value,
            amount=amount,
            method=method,
            status=(PaymentStatus.SUCCESS if ok else PaymentStatus.FAILED).value,
            idempotency_key=key,
            transaction_no=new_transaction_no() if ok else None,
            created_by=actor_id,
        )
        booking = db.session.get(Booking, booking_id)
        booking.payments.append(payment)
        db.session.flush()
        return ChargeResult(payment, ok)

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
