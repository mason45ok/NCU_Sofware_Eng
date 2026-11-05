"""Google OpenID Connect Adapter：把 Authlib 的 userinfo 轉成系統的 GoogleIdentity。"""

from __future__ import annotations

from typing import Any

from flask import Response

from ...schemas.account import GoogleIdentity
from .base import IdentityProvider


class GoogleAuthlibProvider(IdentityProvider):
    def __init__(self, google_client: Any) -> None:
        """google_client：以 Authlib 註冊的 google 用戶端（由 factory 建立，測試時可換成替身）。"""
        self.google = google_client

    def begin(self, callback_url: str) -> Response:
        return self.google.authorize_redirect(callback_url)

    def complete(self) -> GoogleIdentity:
        info = self.google.authorize_access_token()["userinfo"]
        return GoogleIdentity(
            sub=info["sub"],
            email=info["email"],
            name=info.get("name", ""),
            email_verified=bool(info.get("email_verified")),
        )
