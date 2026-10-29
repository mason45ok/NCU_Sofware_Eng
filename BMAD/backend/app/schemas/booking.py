"""訂單、付款的請求與回應。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import Field

from .base import DTO, InDatetime, Request, TPDatetime


class QuoteReq(Request):
    space_id: int
    start_at: InDatetime
    end_at: InDatetime
    attendees: int = Field(default=1, ge=1)
    note: str | None = Field(default=None, max_length=500)


class CreateBookingReq(QuoteReq):
    pass


@dataclass(frozen=True)
class NewSlot:
    start_at: datetime
    end_at: datetime


class PayReq(Request):
    method: str = Field(pattern="^(CREDIT_CARD|LINE_PAY)$")
    card_no: str | None = Field(default=None, max_length=32)


class CancelReq(Request):
    reason: str | None = Field(default=None, max_length=200)


class RescheduleQuoteReq(Request):
    start_at: InDatetime
    end_at: InDatetime


class RescheduleReq(RescheduleQuoteReq):
    method: str | None = Field(default=None, pattern="^(CREDIT_CARD|LINE_PAY)$")
    card_no: str | None = Field(default=None, max_length=32)


class AdminRescheduleReq(RescheduleQuoteReq):
    reason: str = Field(min_length=1, max_length=200)


class AdminCancelReq(Request):
    reason: str = Field(min_length=1, max_length=200)


class RefundReq(Request):
    amount: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=200)


class QuoteDTO(DTO):
    space_id: int
    hours: int
    hourly_price: int
    total_amount: int
    payment_deadline_minutes: int
    cancel_policy: list[str]


class PaymentDTO(DTO):
    payment_id: int
    type: str
    amount: int
    method: str
    status: str
    transaction_no: str | None = None
    created_at: TPDatetime


class AccessCodeView(DTO):
    """code 只在有效期間內回傳（BR-11）。"""

    state: str
    code: str | None = None
    valid_from: TPDatetime
    valid_until: TPDatetime


class BookingDTO(DTO):
    booking_id: int
    booking_no: str
    status: str
    space_id: int
    space_name: str
    branch_name: str
    branch_address: str
    branch_phone: str
    entry_guide: str | None = None
    user_id: int
    user_email: str | None = None
    start_at: TPDatetime
    end_at: TPDatetime
    hours: int
    attendees: int
    note: str | None = None
    hourly_price_snapshot: int
    total_amount: int
    expires_at: TPDatetime
    reschedule_count: int
    cancelled_by: int | None = None
    cancel_reason: str | None = None
    cancelled_at: TPDatetime | None = None
    net_paid: int
    payments: list[PaymentDTO] = []
    access_code: AccessCodeView | None = None
    can_cancel: bool = False
    can_reschedule: bool = False
    can_review: bool = False
    reviewed: bool = False
    created_at: TPDatetime


class PayResultDTO(DTO):
    """付款失敗不是錯誤回應：status 為 FAILED、reason 為 CARD_DECLINED（回 200）。"""

    status: str
    reason: str | None = None
    booking: BookingDTO


class RefundQuoteDTO(DTO):
    status: str
    net_paid: int
    ratio: float
    refund_amount: int
    note: str


class RescheduleQuoteDTO(DTO):
    old_amount: int
    new_amount: int
    diff: int
    new_hours: int
    requires_payment: bool
    refund_amount: int
