"""PasswordService：雜湊、變更、重設、失敗鎖定、權杖（C7）。"""

from __future__ import annotations

from datetime import timedelta

from flask import current_app
from sqlalchemy import delete, or_, select

from ..errors import (
    AppError,
    BusinessRuleError,
    LockedError,
    NotFoundError,
    ValidationError,
)
from ..extensions import db
from ..models import AccountToken, NotificationType, TokenPurpose, User, UserPassword
from ..schemas.account import UserDTO
from ..security import passwords, tokens
from ..utils.clock import Clock
from .notification import NotificationService

MAX_FAILED = 5
LOCK_MINUTES = 15
_TTL = {
    TokenPurpose.VERIFY_EMAIL: timedelta(hours=24),
    TokenPurpose.RESET_PASSWORD: timedelta(minutes=30),
    TokenPurpose.SET_PASSWORD: timedelta(minutes=30),
}
_PATHS = {
    TokenPurpose.VERIFY_EMAIL: ("/verify-email", NotificationType.VERIFY_EMAIL),
    TokenPurpose.RESET_PASSWORD: ("/reset-password", NotificationType.RESET_PASSWORD),
    TokenPurpose.SET_PASSWORD: ("/set-password", NotificationType.SET_PASSWORD),
}
_DUMMY_HASH, _DUMMY_SALT = passwords.hash_password("dummy-password-1")


class PasswordService:
    def __init__(self, clock: Clock, notifications: NotificationService) -> None:
        self.clock = clock
        self.notifications = notifications

    # ---- 密碼 ----
    def validate_strength(self, password: str) -> None:
        if not passwords.is_strong(password):
            raise BusinessRuleError("PASSWORD_TOO_WEAK")

    def set_initial(self, user_id: int, password: str) -> None:
        """建立或覆蓋密碼（每次重新產生鹽值），並解除鎖定。呼叫端負責提交。"""
        self.validate_strength(password)
        hash_hex, salt_hex = passwords.hash_password(password)
        row = db.session.execute(
            select(UserPassword).where(UserPassword.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            db.session.add(
                UserPassword(user_id=user_id, password_hash=hash_hex, password_salt=salt_hex)
            )
        else:
            row.password_hash, row.password_salt = hash_hex, salt_hex
            row.failed_attempts, row.locked_until = 0, None
        db.session.flush()

    def verify(self, user_id: int, password: str) -> bool:
        """比對密碼；失敗累計 5 次鎖定 15 分鐘（BR-22）。計數會立即提交。"""
        row = db.session.execute(
            select(UserPassword).where(UserPassword.user_id == user_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            passwords.verify_password(password, _DUMMY_HASH, _DUMMY_SALT)  # 避免時間差洩漏
            return False
        now = self.clock.now()
        if row.is_locked(now):
            db.session.rollback()
            raise LockedError(
                "ACCOUNT_LOCKED", details={"locked_until": row.locked_until.isoformat()}
            )
        if passwords.verify_password(password, row.password_hash, row.password_salt):
            row.failed_attempts, row.locked_until = 0, None
            db.session.commit()
            return True
        row.failed_attempts += 1
        locked_until = None
        if row.failed_attempts >= MAX_FAILED:
            row.failed_attempts = 0
            row.locked_until = locked_until = now + timedelta(minutes=LOCK_MINUTES)
        db.session.commit()
        if locked_until is not None:
            raise LockedError("ACCOUNT_LOCKED", details={"locked_until": locked_until.isoformat()})
        return False

    def change(self, user: UserDTO, old_password: str, new_password: str) -> None:
        if not user.has_password:
            raise ValidationError("VALIDATION_ERROR", "尚未設定密碼，請使用「設定密碼」寄送設定信")
        self.validate_strength(new_password)
        if not self.verify(user.user_id, old_password):
            raise AppError("INVALID_CREDENTIALS", "舊密碼錯誤")
        self.set_initial(user.user_id, new_password)
        db.session.commit()

    # ---- 權杖 ----
    def issue_token(self, user: User, purpose: TokenPurpose) -> str:
        """產生單次權杖並使同用途的舊權杖失效；回傳明文（只出現在信件連結）。"""
        now = self.clock.now()
        for old in db.session.execute(
            select(AccountToken).where(
                AccountToken.user_id == user.user_id,
                AccountToken.purpose == purpose.value,
                AccountToken.used_at.is_(None),
            )
        ).scalars():
            old.used_at = now
        plain = tokens.new_token()
        db.session.add(
            AccountToken(
                user_id=user.user_id,
                purpose=purpose.value,
                token_hash=tokens.hash_token(plain),
                expires_at=now + _TTL[purpose],
                created_at=now,
            )
        )
        db.session.flush()
        return plain

    def send_token_mail(self, user: User, purpose: TokenPurpose) -> None:
        """在目前交易內建立權杖與通知紀錄；呼叫端提交後再呼叫 send_pending()。"""
        plain = self.issue_token(user, purpose)
        path, ntype = _PATHS[purpose]
        link = f"{current_app.config['APP_BASE_URL']}{path}?token={plain}"
        self.notifications.enqueue(user, ntype, context={"link": link})

    def consume_token(self, token: str, purpose: TokenPurpose) -> User:
        row = db.session.execute(
            select(AccountToken)
            .where(AccountToken.token_hash == tokens.hash_token(token))
            .with_for_update()
        ).scalar_one_or_none()
        if row is None or row.purpose != purpose.value or not row.is_usable(self.clock.now()):
            raise ValidationError("TOKEN_INVALID")
        row.used_at = self.clock.now()
        user = db.session.get(User, row.user_id)
        if user is None:
            raise NotFoundError()
        return user

    # ---- 忘記／重設／設定密碼 ----
    def request_reset(self, email: str) -> None:
        """FR-05：不論 email 是否存在都不報錯。只用 Google 登入者改寄「設定密碼」信。"""
        user = db.session.execute(
            select(User).where(db.func.lower(User.email) == email.lower())
        ).scalar_one_or_none()
        if user is None:
            return
        purpose = TokenPurpose.RESET_PASSWORD if user.has_password() else TokenPurpose.SET_PASSWORD
        self.send_token_mail(user, purpose)
        db.session.commit()
        self.notifications.send_pending()

    def request_setup(self, user: UserDTO) -> None:
        """FR-06：只用 Google 登入者申請設定密碼信。"""
        if user.has_password:
            raise ValidationError("VALIDATION_ERROR", "您已設定密碼，請使用「變更密碼」")
        orm_user = db.session.get(User, user.user_id)
        self.send_token_mail(orm_user, TokenPurpose.SET_PASSWORD)
        db.session.commit()
        self.notifications.send_pending()

    def reset(self, token: str, new_password: str) -> None:
        self.validate_strength(new_password)  # 先檢查，避免權杖被弱密碼請求耗用
        user = self.consume_token(token, TokenPurpose.RESET_PASSWORD)
        self.set_initial(user.user_id, new_password)
        self._invalidate(user.user_id, TokenPurpose.RESET_PASSWORD)
        db.session.commit()

    def set_password(self, token: str, new_password: str) -> None:
        self.validate_strength(new_password)
        user = self.consume_token(token, TokenPurpose.SET_PASSWORD)
        self.set_initial(user.user_id, new_password)
        if user.email_verified_at is None:  # 能收到信即證明擁有該信箱
            user.email_verified_at = self.clock.now()
        self._invalidate(user.user_id, TokenPurpose.SET_PASSWORD)
        db.session.commit()

    def _invalidate(self, user_id: int, purpose: TokenPurpose) -> None:
        now = self.clock.now()
        for t in db.session.execute(
            select(AccountToken).where(
                AccountToken.user_id == user_id,
                AccountToken.purpose == purpose.value,
                AccountToken.used_at.is_(None),
            )
        ).scalars():
            t.used_at = now

    def purge_tokens(self) -> int:
        """排程：刪除過期或已使用超過 7 天的權杖（冪等）。"""
        cutoff = self.clock.now() - timedelta(days=7)
        res = db.session.execute(
            delete(AccountToken).where(
                or_(AccountToken.expires_at < cutoff, AccountToken.used_at < cutoff)
            )
        )
        db.session.commit()
        return res.rowcount
