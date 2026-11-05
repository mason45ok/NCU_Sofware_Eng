"""依設定（GOOGLE_MOCK）決定使用模擬或真實的 Google Adapter。只有兩種實作，不需要註冊表。"""

from __future__ import annotations

from flask import Flask

from .base import IdentityProvider
from .google_mock import MockGoogleProvider


def build_identity_provider(app: Flask) -> IdentityProvider:
    if app.config["GOOGLE_MOCK"]:
        return MockGoogleProvider()

    from authlib.integrations.flask_client import OAuth

    from .google_authlib import GoogleAuthlibProvider

    oauth = OAuth(app)
    oauth.register(
        "google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return GoogleAuthlibProvider(oauth.google)
