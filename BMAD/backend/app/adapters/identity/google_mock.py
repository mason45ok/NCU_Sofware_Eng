"""開發與測試用的 Google 模擬 Adapter：身分由 /api/v1/dev/google-mock 頁面以網址參數帶入。"""

from __future__ import annotations

from flask import Response, redirect, request

from ...errors import ValidationError
from ...schemas.account import GoogleIdentity
from .base import IdentityProvider


class MockGoogleProvider(IdentityProvider):
    def begin(self, callback_url: str) -> Response:
        return redirect("/api/v1/dev/google-mock")

    def complete(self) -> GoogleIdentity:
        try:
            return GoogleIdentity(
                sub=request.args["sub"],
                email=request.args["email"],
                name=request.args.get("name", ""),
                email_verified=request.args.get("email_verified", "true") == "true",
            )
        except KeyError:
            raise ValidationError("VALIDATION_ERROR") from None
