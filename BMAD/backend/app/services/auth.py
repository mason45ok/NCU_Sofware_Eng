"""AuthService：註冊、email 驗證、登入（C7）。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..errors import AppError, NotFoundError
from ..extensions import db
from ..models import TokenPurpose, User
from ..schemas.account import UserDTO
from ..utils.clock import Clock
from .notification import NotificationService
from .password import PasswordService


def user_to_dto(user: User) -> UserDTO:
    return UserDTO(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        role=user.role,
        status=user.status,
        status_reason=user.status_reason,
        email_verified=user.is_email_verified(),
        has_password=user.has_password(),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


class AuthService:
    def __init__(
        self,
        clock: Clock,
        passwords: PasswordService,
        notifications: NotificationService,
    ) -> None:
        self.clock = clock
        self.passwords = passwords
        self.notifications = notifications

    def find_by_email(self, email: str) -> User | None:
        return db.session.execute(
            select(User).where(func.lower(User.email) == email.strip().lower())
        ).scalar_one_or_none()

    def get(self, user_id: int) -> UserDTO | None:
        user = db.session.get(User, user_id)
        return user_to_dto(user) if user else None

    def register(self, email: str, name: str, password: str) -> UserDTO | None:
        """FR-01。email 已存在時不建立帳號、不透露存在與否（回傳 None）；
        若該帳號只用 Google 登入，改寄「設定密碼」信。"""
        self.passwords.validate_strength(password)
        existing = self.find_by_email(email)
        if existing is not None:
            if not existing.has_password():
                self.passwords.send_token_mail(existing, TokenPurpose.SET_PASSWORD)
                db.session.commit()
                self.notifications.send_pending()
            return None
        try:
            user = User(email=email.strip(), name=name)
            db.session.add(user)
            db.session.flush()
            self.passwords.set_initial(user.user_id, password)
            self.passwords.send_token_mail(user, TokenPurpose.VERIFY_EMAIL)
            db.session.commit()
        except IntegrityError:  # 併發註冊同一 email
            db.session.rollback()
            return None
        self.notifications.send_pending()
        return user_to_dto(user)

    def create_from_google(self, email: str, name: str, verified: bool) -> User:
        """FR-04 情況②：Google 已驗證的 email 視為已驗證。呼叫端負責提交。"""
        user = User(
            email=email.strip(),
            name=(name or email.split("@")[0])[:50],
            email_verified_at=self.clock.now() if verified else None,
        )
        db.session.add(user)
        db.session.flush()
        return user

    def verify_email(self, token: str) -> None:
        user = self.passwords.consume_token(token, TokenPurpose.VERIFY_EMAIL)
        if user.email_verified_at is None:
            user.email_verified_at = self.clock.now()
        db.session.commit()

    def resend_verification(self, email: str) -> None:
        """不論 email 是否存在都回傳相同結果。"""
        user = self.find_by_email(email)
        if user is not None and not user.is_email_verified():
            self.passwords.send_token_mail(user, TokenPurpose.VERIFY_EMAIL)
            db.session.commit()
            self.notifications.send_pending()

    def login(self, email: str, password: str) -> UserDTO:
        """FR-03：帳號或密碼錯誤統一回 INVALID_CREDENTIALS；FROZEN／BLACKLISTED 仍可登入。"""
        user = self.find_by_email(email)
        if user is None:
            self.passwords.verify(-1, password)  # 消耗相同時間
            raise AppError("INVALID_CREDENTIALS")
        user_id = user.user_id
        if not self.passwords.verify(user_id, password):
            raise AppError("INVALID_CREDENTIALS")
        user = db.session.get(User, user_id)
        self.mark_login(user)
        db.session.commit()
        return user_to_dto(user)

    def mark_login(self, user: User) -> None:
        user.last_login_at = self.clock.now()

    def update_profile(self, user: UserDTO, name: str | None, phone: str | None) -> UserDTO:
        """FR-07：只能改姓名與電話，email 不開放修改。"""
        row = db.session.get(User, user.user_id)
        if row is None:
            raise NotFoundError()
        if name is not None:
            row.name = name
        if phone is not None:
            row.phone = phone or None
        db.session.commit()
        return user_to_dto(row)
