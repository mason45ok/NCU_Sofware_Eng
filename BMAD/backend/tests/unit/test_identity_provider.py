"""Google 身分提供者 Adapter 與 Factory（FR-04；Layer 4：外部服務隔離）。

真實的 Google OAuth 流程需要實際憑證與網路，無法自動測試；這裡測的是 Adapter 的轉換邏輯
（以替身取代 Authlib 用戶端）、Factory 的選擇，以及 Controller 只依賴 IdentityProvider。
"""

import pytest
from flask import Flask, redirect

from app.adapters.identity import IdentityProvider, build_identity_provider
from app.adapters.identity.google_authlib import GoogleAuthlibProvider
from app.adapters.identity.google_mock import MockGoogleProvider
from app.errors import AppError
from app.schemas.account import GoogleIdentity

API = "/api/v1"


# ---------- Mock Adapter ----------
def test_fr04_mock_adapter_reads_identity_from_query(app):
    with app.test_request_context("/cb?sub=g-1&email=a@gmail.com&name=A&email_verified=false"):
        identity = MockGoogleProvider().complete()
    assert identity == GoogleIdentity("g-1", "a@gmail.com", "A", False)


def test_fr04_mock_adapter_requires_sub_and_email(app):
    with app.test_request_context("/cb?sub=g-1"), pytest.raises(AppError) as exc:
        MockGoogleProvider().complete()
    assert exc.value.code == "VALIDATION_ERROR"


def test_fr04_mock_adapter_begin_redirects_to_mock_page(app):
    with app.test_request_context("/start"):
        res = MockGoogleProvider().begin("http://x/cb")
    assert res.status_code == 302 and res.headers["Location"] == "/api/v1/dev/google-mock"


# ---------- Authlib Adapter（以替身取代用戶端，不需要憑證與網路） ----------
class StubGoogleClient:
    def __init__(self, userinfo):
        self.userinfo, self.callback = userinfo, None

    def authorize_redirect(self, callback_url):
        self.callback = callback_url
        return redirect("https://accounts.google.test/auth")

    def authorize_access_token(self):
        return {"userinfo": self.userinfo}


def test_fr04_authlib_adapter_maps_userinfo_to_identity():
    client = StubGoogleClient(
        {"sub": "s1", "email": "a@gmail.com", "name": "A", "email_verified": True}
    )
    assert GoogleAuthlibProvider(client).complete() == GoogleIdentity(
        "s1", "a@gmail.com", "A", True
    )


def test_fr04_authlib_adapter_treats_missing_email_verified_as_false():
    client = StubGoogleClient({"sub": "s1", "email": "a@gmail.com"})
    identity = GoogleAuthlibProvider(client).complete()
    assert identity.email_verified is False and identity.name == ""


def test_fr04_authlib_adapter_begin_delegates_with_callback_url(app):
    client = StubGoogleClient({})
    with app.test_request_context("/start"):
        res = GoogleAuthlibProvider(client).begin("http://x/cb")
    assert client.callback == "http://x/cb" and res.status_code == 302


# ---------- Factory ----------
def _flask_app(mock: bool) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="x", GOOGLE_MOCK=mock, GOOGLE_CLIENT_ID="id", GOOGLE_CLIENT_SECRET="secret"
    )
    return app


def test_factory_returns_mock_provider_when_google_mock_is_on():
    assert isinstance(build_identity_provider(_flask_app(True)), MockGoogleProvider)


def test_factory_returns_authlib_provider_when_google_mock_is_off():
    assert isinstance(build_identity_provider(_flask_app(False)), GoogleAuthlibProvider)


# ---------- Controller 只依賴 IdentityProvider ----------
class FakeProvider(IdentityProvider):
    def __init__(self, identity):
        self.identity, self.callback = identity, None

    def begin(self, callback_url):
        self.callback = callback_url
        return redirect("/fake-idp")

    def complete(self):
        return self.identity


def test_fr04_controller_uses_whatever_provider_is_registered(app, client, monkeypatch):
    fake = FakeProvider(GoogleIdentity("g-fake", "fake@gmail.com", "Fake", True))
    monkeypatch.setitem(app.extensions, "identity_provider", fake)

    start = client.get(f"{API}/auth/google/start", follow_redirects=False)
    assert start.status_code == 302 and start.headers["Location"] == "/fake-idp"
    assert fake.callback.endswith("/api/v1/auth/google/callback")

    done = client.get(f"{API}/auth/google/callback", follow_redirects=False)
    assert done.status_code == 302 and done.headers["Location"] == "/"
    assert client.get(f"{API}/auth/me").get_json()["user"]["email"] == "fake@gmail.com"
