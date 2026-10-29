"""GoogleAuthService：Google 登入的三種情況與綁定（FR-04、D9）。"""

from __future__ import annotations

from sqlalchemy import select

from ..errors import AppError, ConflictError, ValidationError
from ..extensions import db
from ..models import ExternalAccount
from ..schemas.account import GoogleIdentity, GoogleLoginResult, UserDTO
from .auth import AuthService, user_to_dto
from .password import PasswordService

PROVIDER = "GOOGLE"


class GoogleAuthService:
    def __init__(self, auth: AuthService, passwords: PasswordService) -> None:
        self.auth = auth
        self.passwords = passwords

    def _has_google(self, user_id: int) -> bool:
        return (
            db.session.execute(
                select(ExternalAccount.ext_id).where(
                    ExternalAccount.user_id == user_id,
                    ExternalAccount.provider == PROVIDER,
                )
            ).first()
            is not None
        )

    def _link_row(self, user_id: int, identity: GoogleIdentity) -> None:
        db.session.add(
            ExternalAccount(
                user_id=user_id,
                provider=PROVIDER,
                provider_user_id=identity.sub,
                provider_email=identity.email,
            )
        )

    def handle_callback(self, identity: GoogleIdentity) -> GoogleLoginResult:
        ext = db.session.execute(
            select(ExternalAccount).where(
                ExternalAccount.provider == PROVIDER,
                ExternalAccount.provider_user_id == identity.sub,
            )
        ).scalar_one_or_none()
        if ext is not None:  # ① 已綁定
            self.auth.mark_login(ext.user)
            db.session.commit()
            return GoogleLoginResult("LOGGED_IN", user_to_dto(ext.user))

        existing = self.auth.find_by_email(identity.email)
        if existing is None:  # ② 新帳號
            user = self.auth.create_from_google(
                identity.email, identity.name, identity.email_verified
            )
            self._link_row(user.user_id, identity)
            self.auth.mark_login(user)
            db.session.commit()
            return GoogleLoginResult("LOGGED_IN", user_to_dto(user))

        # ③ email 已存在：不自動合併（BR-24）
        if self._has_google(existing.user_id):
            raise ConflictError("ACCOUNT_ALREADY_LINKED")
        return GoogleLoginResult("NEEDS_LINK")

    def link(self, pending: GoogleIdentity, email: str, password: str) -> UserDTO:
        """情況③：輸入既有帳號密碼正確後才綁定並登入。"""
        user = self.auth.find_by_email(email)
        if user is None:
            raise ValidationError("TOKEN_INVALID")
        user_id = user.user_id
        if self._has_google(user_id):
            raise ConflictError("ACCOUNT_ALREADY_LINKED")
        if not self.passwords.verify(user_id, password):
            raise AppError("INVALID_CREDENTIALS")
        user = db.session.get(type(user), user_id)
        self._link_row(user_id, pending)
        if pending.email_verified and not user.is_email_verified():
            user.email_verified_at = self.auth.clock.now()
        self.auth.mark_login(user)
        db.session.commit()
        return user_to_dto(user)
