"""AdminUserService：會員查詢、凍結／黑名單／解除、久未登入自動凍結（FR-46、BR-20、21）。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select, update

from ..errors import ForbiddenError, NotFoundError, ValidationError
from ..extensions import db
from ..models import Role, User, UserStatus
from ..schemas.account import UserDTO
from ..schemas.base import Page
from ..utils.clock import Clock
from .auth import user_to_dto

INACTIVE_DAYS = 180
INACTIVE_REASON = "久未登入（超過 180 天），請聯絡客服解除"


class AdminUserService:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def search(
        self,
        email: str | None,
        name: str | None,
        status: str | None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[UserDTO]:
        stmt = select(User)
        if email:
            stmt = stmt.where(User.email.ilike(f"%{email}%"))
        if name:
            stmt = stmt.where(User.name.ilike(f"%{name}%"))
        if status:
            stmt = stmt.where(User.status == status)
        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = (
            db.session.execute(
                stmt.order_by(User.user_id).limit(page_size).offset((page - 1) * page_size)
            )
            .scalars()
            .all()
        )
        return Page[UserDTO](
            items=[user_to_dto(u) for u in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def set_status(self, admin: UserDTO, user_id: int, status: str, reason: str | None) -> UserDTO:
        """BR-20：凍結或黑名單須填原因；解除時清除原因。管理員帳號不可被限制。"""
        if admin.role != Role.ADMIN:
            raise ForbiddenError("FORBIDDEN")
        if status not in {s.value for s in UserStatus}:
            raise ValidationError("VALIDATION_ERROR", details={"status": "選項不正確"})
        user = db.session.get(User, user_id)
        if user is None:
            raise NotFoundError()
        if user.role == Role.ADMIN:
            raise ForbiddenError("FORBIDDEN", "不可變更管理員帳號的狀態")
        if status == UserStatus.ACTIVE:
            user.status, user.status_reason = status, None
        else:
            if not reason or not reason.strip():
                raise ValidationError("VALIDATION_ERROR", "請填寫原因", {"reason": "必填"})
            user.status, user.status_reason = status, reason.strip()
        db.session.commit()
        return user_to_dto(user)

    def freeze_inactive(self) -> int:
        """FR-54：條件式 UPDATE，重跑結果不變；管理員帳號不受影響。"""
        cutoff = self.clock.now() - timedelta(days=INACTIVE_DAYS)
        res = db.session.execute(
            update(User)
            .where(
                User.role == Role.USER.value,
                User.status == UserStatus.ACTIVE.value,
                func.coalesce(User.last_login_at, User.created_at) < cutoff,
            )
            .values(status=UserStatus.FROZEN.value, status_reason=INACTIVE_REASON)
        )
        db.session.commit()
        return res.rowcount
