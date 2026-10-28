"""權限裝飾器與 Flask-Login 的使用者包裝。資料所有權由 Service 檢查（不屬於本人回 404）。"""

from __future__ import annotations

from functools import wraps

from flask_login import UserMixin, current_user

from ..errors import AuthError, ForbiddenError
from ..models import Role
from ..schemas.account import UserDTO


class SessionUser(UserMixin):
    """把 UserDTO 包成 Flask-Login 使用者，避免 ORM 物件離開 Service 層。"""

    def __init__(self, dto: UserDTO) -> None:
        self.dto = dto

    def get_id(self) -> str:
        return str(self.dto.user_id)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            raise AuthError("UNAUTHENTICATED")
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            raise AuthError("UNAUTHENTICATED")
        if current_user.dto.role != Role.ADMIN:
            raise ForbiddenError("FORBIDDEN")
        return fn(*args, **kwargs)

    return wrapper
