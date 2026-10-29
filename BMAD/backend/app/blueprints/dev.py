"""dev_bp：僅 APP_ENV=development 註冊。假的 Google 登入頁，可模擬 FR-04 的三種情況。"""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from flask import Blueprint

bp = Blueprint("dev", __name__, url_prefix="/api/v1/dev")

PRESETS = [
    (
        "① 已綁定的 Google 帳號（g1@gmail.com）",
        "google-001",
        "g1@gmail.com",
        "Google 使用者一號",
    ),
    (
        "② 全新的 Google 帳號（新增帳號）",
        "google-new",
        "newgoogle@gmail.com",
        "新 Google 使用者",
    ),
    (
        "③ email 已存在但未綁定（user1@judian.local）",
        "google-777",
        "user1@judian.local",
        "王小明",
    ),
]


@bp.get("/google-mock")
def google_mock():
    links = "".join(
        f'<li><a href="/api/v1/auth/google/callback?'
        f'{escape(urlencode({"sub": sub, "email": email, "name": name, "email_verified": "true"}))}">'
        f"{escape(label)}</a></li>"
        for label, sub, email, name in PRESETS
    )
    html = f"""<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<title>Google 登入（開發模擬）</title>
<body style="font-family:sans-serif;max-width:560px;margin:40px auto;padding:0 16px">
<h1>Google 登入（開發模擬）</h1><p>選擇要模擬的身分：</p><ul>{links}</ul>
<h2>自訂身分</h2>
<form method="get" action="/api/v1/auth/google/callback">
<p><label>sub <input name="sub" required></label></p>
<p><label>email <input name="email" type="email" required></label></p>
<p><label>name <input name="name"></label></p>
<p><label>email_verified
<select name="email_verified"><option>true</option><option>false</option></select></label></p>
<button>送出</button></form></body></html>"""
    return html
