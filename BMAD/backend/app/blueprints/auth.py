"""auth_bp：帳號（註冊、驗證、登入、忘記密碼、Google）。呼叫 AuthService、PasswordService、GoogleAuthService。"""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, current_app, jsonify, redirect, request, session
from flask_login import current_user, login_user, logout_user
from flask_wtf.csrf import generate_csrf

from ..errors import AppError, ValidationError
from ..extensions import limiter
from ..schemas.account import (
    EmailReq,
    GoogleIdentity,
    GoogleLinkReq,
    LoginReq,
    RegisterReq,
    TokenPasswordReq,
    TokenReq,
)
from ..security.permissions import SessionUser, login_required
from ._common import ok, parse_body, svc

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

RATE = "10 per minute"  # NFR-02
PENDING_MINUTES = 10


def _login(dto) -> None:
    session.clear()  # 登入時更新 session，防止 session fixation
    login_user(SessionUser(dto))


@bp.get("/csrf")
def csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


@bp.post("/register")
@limiter.limit(RATE)
def register():
    req = parse_body(RegisterReq)
    user = svc().auth.register(req.email, req.name, req.password)
    if user is not None:
        _login(user)
    # 不論 email 是否已存在都回相同內容，不透露帳號是否存在
    return jsonify({"message": "請查收驗證信件"}), 201


@bp.post("/verify-email")
def verify_email():
    svc().auth.verify_email(parse_body(TokenReq).token)
    return ok(message="email 驗證完成")


@bp.post("/resend-verification")
@limiter.limit(RATE)
def resend_verification():
    svc().auth.resend_verification(parse_body(EmailReq).email)
    return ok(message="若此 email 已註冊且尚未驗證，驗證信已寄出，請查收")


@bp.post("/login")
@limiter.limit(RATE)
def login():
    req = parse_body(LoginReq)
    user = svc().auth.login(req.email, req.password)
    _login(user)
    return ok({"user": user.model_dump(mode="json")})


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return ok(message="已登出")


@bp.get("/me")
def whoami():
    if not current_user.is_authenticated:
        return jsonify({"user": None})
    fresh = svc().auth.get(current_user.dto.user_id)
    return ok({"user": fresh.model_dump(mode="json") if fresh else None})


@bp.post("/forgot-password")
@limiter.limit(RATE)
def forgot_password():
    svc().passwords.request_reset(parse_body(EmailReq).email)
    return ok(message="若此 email 已註冊，重設密碼信已寄出，請查收")


@bp.post("/reset-password")
def reset_password():
    req = parse_body(TokenPasswordReq)
    svc().passwords.reset(req.token, req.password)
    return ok(message="密碼已重設，請重新登入")


@bp.post("/set-password")
def set_password():
    req = parse_body(TokenPasswordReq)
    svc().passwords.set_password(req.token, req.password)
    return ok(message="密碼已設定，之後可用 email 與密碼登入")


# ---------- Google 登入（FR-04） ----------
def _oauth():
    """正式模式才建立 Authlib 用戶端（開發期以 mock 代替）。"""
    from authlib.integrations.flask_client import OAuth

    oauth = current_app.extensions.get("authlib_oauth")
    if oauth is None:
        oauth = OAuth(current_app)
        oauth.register(
            "google",
            client_id=current_app.config["GOOGLE_CLIENT_ID"],
            client_secret=current_app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
        current_app.extensions["authlib_oauth"] = oauth
    return oauth.google


@bp.get("/google/start")
def google_start():
    if current_app.config["GOOGLE_MOCK"]:
        return redirect("/api/v1/dev/google-mock")
    callback = current_app.config["APP_BASE_URL"] + "/api/v1/auth/google/callback"
    return _oauth().authorize_redirect(callback)


@bp.get("/google/callback")
def google_callback():
    if current_app.config["GOOGLE_MOCK"]:  # 開發模式：身分由 mock 頁面帶入
        try:
            identity = GoogleIdentity(
                sub=request.args["sub"],
                email=request.args["email"],
                name=request.args.get("name", ""),
                email_verified=request.args.get("email_verified", "true") == "true",
            )
        except KeyError:
            raise ValidationError("VALIDATION_ERROR") from None
    else:
        token = _oauth().authorize_access_token()
        info = token["userinfo"]
        identity = GoogleIdentity(
            sub=info["sub"],
            email=info["email"],
            name=info.get("name", ""),
            email_verified=bool(info.get("email_verified")),
        )
    try:
        result = svc().google.handle_callback(identity)
    except AppError as err:
        return redirect(f"/login?error={err.code}")
    if result.status == "LOGGED_IN":
        _login(result.user)
        return redirect("/")
    session.clear()
    session["google_pending"] = {
        "sub": identity.sub,
        "email": identity.email,
        "name": identity.name,
        "email_verified": identity.email_verified,
        "expires": (svc().clock.now() + timedelta(minutes=PENDING_MINUTES)).timestamp(),
    }
    return redirect(f"/auth/google/link?email={identity.email}")


@bp.post("/google/link")
def google_link():
    req = parse_body(GoogleLinkReq)
    pending = session.get("google_pending")
    if not pending or pending["expires"] < svc().clock.now().timestamp():
        session.pop("google_pending", None)
        raise ValidationError("TOKEN_INVALID", "綁定逾時，請重新使用 Google 登入")
    identity = GoogleIdentity(
        sub=pending["sub"],
        email=pending["email"],
        name=pending["name"],
        email_verified=pending["email_verified"],
    )
    user = svc().google.link(identity, identity.email, req.password)
    _login(user)
    return ok({"user": user.model_dump(mode="json")})
