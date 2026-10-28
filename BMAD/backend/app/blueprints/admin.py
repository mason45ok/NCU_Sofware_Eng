"""admin_bp：管理後台。所有路由須為 ADMIN；寫入訂單一律經 BookingService。"""

from __future__ import annotations

from flask import Blueprint, request

from ..schemas.admin import (
    BookingFilters,
    BranchReq,
    EquipmentPatchReq,
    EquipmentReq,
    PhotoOrderReq,
    PhotoPatchReq,
    SpaceEquipmentReq,
    SpaceReq,
    StatusReq,
    UserStatusReq,
)
from ..schemas.booking import AdminCancelReq, AdminRescheduleReq, NewSlot, RefundReq
from ..schemas.catalog import ReviewHiddenReq
from ..security.permissions import admin_required
from ._common import idempotency_key, me, ok, parse_body, parse_query, svc

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


@bp.before_request
@admin_required
def _require_admin():
    return None


def _page_args() -> tuple[int, int]:
    return int(request.args.get("page", 1)), int(request.args.get("page_size", 20))


# ---- 場館 ----
@bp.get("/branches")
def list_branches():
    return ok({"items": [b.model_dump(mode="json") for b in svc().admin_catalog.list_branches()]})


@bp.post("/branches")
def create_branch():
    return ok(svc().admin_catalog.save_branch(None, parse_body(BranchReq)), 201)


@bp.patch("/branches/<int:branch_id>")
def update_branch(branch_id: int):
    return ok(svc().admin_catalog.save_branch(branch_id, parse_body(BranchReq)))


@bp.post("/branches/<int:branch_id>/status")
def branch_status(branch_id: int):
    return ok(svc().admin_catalog.set_branch_status(branch_id, parse_body(StatusReq).status))


# ---- 空間 ----
@bp.get("/spaces")
def list_spaces():
    return ok({"items": [s.model_dump(mode="json") for s in svc().admin_catalog.list_spaces()]})


@bp.post("/spaces")
def create_space():
    return ok(svc().admin_catalog.save_space(None, parse_body(SpaceReq)), 201)


@bp.get("/spaces/<int:space_id>")
def get_space(space_id: int):
    s = svc()
    return ok(
        {
            "space": s.admin_catalog.get_space(space_id).model_dump(mode="json"),
            "detail": s.catalog.get_space(space_id).model_dump(mode="json"),
        }
    )


@bp.patch("/spaces/<int:space_id>")
def update_space(space_id: int):
    return ok(svc().admin_catalog.save_space(space_id, parse_body(SpaceReq)))


@bp.post("/spaces/<int:space_id>/status")
def space_status(space_id: int):
    return ok(svc().admin_catalog.set_space_status(space_id, parse_body(StatusReq).status))


@bp.post("/spaces/<int:space_id>/photos")
def upload_photo(space_id: int):
    return ok(svc().admin_catalog.upload_photo(space_id, request.files.get("file")), 201)


@bp.put("/spaces/<int:space_id>/photos/order")
def reorder_photos(space_id: int):
    photos = svc().admin_catalog.reorder_photos(space_id, parse_body(PhotoOrderReq).photo_ids)
    return ok({"items": [p.model_dump(mode="json") for p in photos]})


@bp.patch("/photos/<int:photo_id>")
def update_photo(photo_id: int):
    return ok(svc().admin_catalog.update_photo(photo_id, parse_body(PhotoPatchReq).caption))


@bp.delete("/photos/<int:photo_id>")
def delete_photo(photo_id: int):
    svc().admin_catalog.delete_photo(photo_id)
    return ok(message="已刪除")


@bp.put("/spaces/<int:space_id>/equipment")
def set_space_equipment(space_id: int):
    svc().admin_catalog.set_space_equipment(space_id, parse_body(SpaceEquipmentReq).items)
    return ok(message="已更新設備")


# ---- 設備 ----
@bp.get("/equipment")
def list_equipment():
    return ok({"items": [e.model_dump(mode="json") for e in svc().admin_catalog.list_equipment()]})


@bp.post("/equipment")
def create_equipment():
    return ok(svc().admin_catalog.create_equipment(parse_body(EquipmentReq)), 201)


@bp.patch("/equipment/<int:equipment_id>")
def update_equipment(equipment_id: int):
    return ok(svc().admin_catalog.update_equipment(equipment_id, parse_body(EquipmentPatchReq)))


# ---- 訂單 ----
@bp.get("/bookings")
def search_bookings():
    return ok(svc().admin_bookings.search(parse_query(BookingFilters)))


@bp.get("/bookings/<int:booking_id>")
def booking_detail(booking_id: int):
    return ok(svc().admin_bookings.detail(booking_id))


@bp.post("/bookings/<int:booking_id>/cancel")
def cancel_booking(booking_id: int):
    req = parse_body(AdminCancelReq)
    return ok(svc().bookings.cancel_by_admin(me(), booking_id, req.reason))


@bp.post("/bookings/<int:booking_id>/reschedule")
def reschedule_booking(booking_id: int):
    req = parse_body(AdminRescheduleReq)
    slot = NewSlot(req.start_at, req.end_at)
    return ok(svc().bookings.reschedule_by_admin(me(), booking_id, slot, req.reason))


@bp.post("/bookings/<int:booking_id>/refunds")
def partial_refund(booking_id: int):
    req = parse_body(RefundReq)
    payment = svc().bookings.refund_partially(
        me(), booking_id, req.amount, idempotency_key(), req.reason
    )
    return ok(payment, 201)


# ---- 會員 ----
@bp.get("/users")
def search_users():
    page, size = _page_args()
    args = request.args
    return ok(
        svc().admin_users.search(
            args.get("email"), args.get("name"), args.get("status"), page, size
        )
    )


@bp.patch("/users/<int:user_id>/status")
def set_user_status(user_id: int):
    req = parse_body(UserStatusReq)
    return ok(svc().admin_users.set_status(me(), user_id, req.status, req.reason))


# ---- 評論 ----
@bp.get("/reviews")
def list_reviews():
    page, size = _page_args()
    return ok(svc().reviews.list_all(page, size))


@bp.patch("/reviews/<int:review_id>")
def hide_review(review_id: int):
    return ok(svc().reviews.set_hidden(review_id, parse_body(ReviewHiddenReq).is_hidden))


# ---- 通知 ----
@bp.get("/notifications")
def list_notifications():
    page, size = _page_args()
    return ok(svc().notifications.search(request.args.get("status"), page, size))


@bp.post("/notifications/<int:notification_id>/retry")
def retry_notification(notification_id: int):
    return ok(svc().notifications.retry(notification_id))


@bp.get("/summary")
def summary():
    return ok(svc().admin_bookings.summary())
