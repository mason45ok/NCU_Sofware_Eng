"""bookings_bp：訂單（試算、建立、付款、取消、改期、評論）。付款一律經 BookingService。"""

from __future__ import annotations

from flask import Blueprint

from ..schemas.booking import (
    CreateBookingReq,
    NewSlot,
    PayReq,
    QuoteReq,
    RescheduleQuoteReq,
    RescheduleReq,
)
from ..schemas.catalog import ReviewReq
from ..security.permissions import login_required
from ._common import idempotency_key, me, ok, parse_body, svc

bp = Blueprint("bookings", __name__, url_prefix="/api/v1/bookings")


@bp.before_request
@login_required
def _require_login():
    return None


@bp.post("/quote")
def quote():
    return ok(svc().bookings.quote(me(), parse_body(QuoteReq)))


@bp.post("")
def create():
    return ok(svc().bookings.create(me(), parse_body(CreateBookingReq)), 201)


@bp.get("/<int:booking_id>")
def detail(booking_id: int):
    return ok(svc().bookings.get_for_owner(me(), booking_id))


@bp.post("/<int:booking_id>/pay")
def pay(booking_id: int):
    req = parse_body(PayReq)
    result = svc().bookings.pay(me(), booking_id, req.method, req.card_no, idempotency_key())
    return ok(result)  # 付款失敗仍回 200（status=FAILED）


@bp.get("/<int:booking_id>/cancel-quote")
def cancel_quote(booking_id: int):
    return ok(svc().bookings.cancel_quote(me(), booking_id))


@bp.post("/<int:booking_id>/cancel")
def cancel(booking_id: int):
    return ok(svc().bookings.cancel_by_member(me(), booking_id))


@bp.post("/<int:booking_id>/reschedule-quote")
def reschedule_quote(booking_id: int):
    req = parse_body(RescheduleQuoteReq)
    return ok(svc().bookings.reschedule_quote(me(), booking_id, NewSlot(req.start_at, req.end_at)))


@bp.post("/<int:booking_id>/reschedule")
def reschedule(booking_id: int):
    req = parse_body(RescheduleReq)
    booking = svc().bookings.reschedule_by_member(
        me(),
        booking_id,
        NewSlot(req.start_at, req.end_at),
        req.method,
        req.card_no,
        idempotency_key(required=False),
    )
    return ok(booking)


@bp.post("/<int:booking_id>/review")
def review(booking_id: int):
    req = parse_body(ReviewReq)
    return ok(svc().reviews.create(me(), booking_id, req.rating, req.comment), 201)
