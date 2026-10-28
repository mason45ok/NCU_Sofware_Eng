"""me_bp：本人資料、密碼、訂單列表、收藏。"""

from __future__ import annotations

from flask import Blueprint, request

from ..schemas.account import ChangePasswordReq, ProfileReq
from ..security.permissions import login_required
from ._common import me, ok, parse_body, svc

bp = Blueprint("me", __name__, url_prefix="/api/v1/me")


@bp.before_request
@login_required
def _require_login():
    return None


@bp.patch("")
def update_profile():
    req = parse_body(ProfileReq)
    user = svc().auth.update_profile(me(), req.name, req.phone)
    return ok({"user": user.model_dump(mode="json")})


@bp.put("/password")
def change_password():
    req = parse_body(ChangePasswordReq)
    svc().passwords.change(me(), req.old_password, req.new_password)
    return ok(message="密碼已變更")


@bp.post("/password/setup-email")
def setup_password_email():
    svc().passwords.request_setup(me())
    return ok(message="設定密碼信已寄出，請查收")


@bp.get("/bookings")
def my_bookings():
    page = svc().bookings.list_for_owner(
        me(),
        request.args.get("tab", "upcoming"),
        int(request.args.get("page", 1)),
        int(request.args.get("page_size", 10)),
    )
    return ok(page)


@bp.get("/favorites")
def my_favorites():
    return ok({"items": [s.model_dump(mode="json") for s in svc().favorites.list(me())]})


@bp.put("/favorites/<int:space_id>")
def add_favorite(space_id: int):
    svc().favorites.add(me(), space_id)
    return ok(message="已收藏")


@bp.delete("/favorites/<int:space_id>")
def remove_favorite(space_id: int):
    svc().favorites.remove(me(), space_id)
    return ok(message="已取消收藏")
