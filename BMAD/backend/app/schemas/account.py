"""帳號相關的請求與回應。"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field

from .base import DTO, Email, Request, TPDatetime


class UserDTO(DTO):
    user_id: int
    email: str
    name: str
    phone: str | None = None
    role: str
    status: str
    status_reason: str | None = None
    email_verified: bool
    has_password: bool
    last_login_at: TPDatetime | None = None
    created_at: TPDatetime | None = None


class RegisterReq(Request):
    email: Email
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class LoginReq(Request):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenReq(Request):
    token: str = Field(min_length=1, max_length=200)


class EmailReq(Request):
    email: Email


class TokenPasswordReq(Request):
    token: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordReq(Request):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ProfileReq(Request):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=20)


class GoogleLinkReq(Request):
    password: str = Field(min_length=1, max_length=128)


@dataclass(frozen=True)
class GoogleIdentity:
    """Google 回傳的身分（已驗證簽章）。"""

    sub: str
    email: str
    name: str
    email_verified: bool


@dataclass(frozen=True)
class GoogleLoginResult:
    """status：LOGGED_IN（情況①②）或 NEEDS_LINK（情況③）。"""

    status: str
    user: UserDTO | None = None
