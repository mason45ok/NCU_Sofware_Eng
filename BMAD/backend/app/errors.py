"""例外類別、錯誤碼與 HTTP 狀態碼對照（D4）。Service 只拋出帶錯誤碼的例外，不知道 HTTP。"""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from flask_wtf.csrf import CSRFError

# 錯誤碼 → HTTP 狀態碼（ARCHITECTURE.md 5.1）
HTTP_STATUS: dict[str, int] = {
    "VALIDATION_ERROR": 400,
    "TOKEN_INVALID": 400,
    "INVALID_UPLOAD": 400,
    "UNAUTHENTICATED": 401,
    "INVALID_CREDENTIALS": 401,
    "FORBIDDEN": 403,
    "ACCOUNT_RESTRICTED": 403,
    "EMAIL_NOT_VERIFIED": 403,
    "NOT_FOUND": 404,
    "SLOT_TAKEN": 409,
    "BOOKING_EXPIRED": 409,
    "INVALID_STATE": 409,
    "PENDING_LIMIT": 409,
    "IDEMPOTENCY_KEY_REUSED": 409,
    "ACCOUNT_ALREADY_LINKED": 409,
    "INVALID_TIME_SLOT": 422,
    "OUTSIDE_OPENING_HOURS": 422,
    "OUT_OF_RANGE": 422,
    "OVER_CAPACITY": 422,
    "SPACE_UNAVAILABLE": 422,
    "RESCHEDULE_NOT_ALLOWED": 422,
    "REFUND_EXCEEDS_PAID": 422,
    "REVIEW_NOT_ALLOWED": 422,
    "PASSWORD_TOO_WEAK": 422,
    "ACCOUNT_LOCKED": 423,
    "RATE_LIMITED": 429,
}

# 預設訊息：告訴使用者下一步怎麼做
DEFAULT_MESSAGES: dict[str, str] = {
    "VALIDATION_ERROR": "輸入的資料格式不正確，請檢查標示的欄位後重新送出",
    "TOKEN_INVALID": "連結無效、已過期或已使用，請重新申請",
    "INVALID_UPLOAD": "照片格式或大小不符，請改用 5 MB 以內的 jpg、png 或 webp",
    "UNAUTHENTICATED": "請先登入",
    "INVALID_CREDENTIALS": "帳號或密碼錯誤",
    "FORBIDDEN": "您沒有權限執行此操作",
    "ACCOUNT_RESTRICTED": "您的帳號目前受限，無法執行此操作，請聯絡客服",
    "EMAIL_NOT_VERIFIED": "請先到信箱點擊驗證連結，完成 email 驗證後再預約",
    "NOT_FOUND": "找不到資料",
    "SLOT_TAKEN": "此時段已被預約，請選擇其他時段",
    "BOOKING_EXPIRED": "訂單已失效，請重新預約",
    "INVALID_STATE": "目前訂單狀態不允許此操作",
    "PENDING_LIMIT": "待付款訂單已達 3 筆，請先完成付款或取消其中一筆",
    "IDEMPOTENCY_KEY_REUSED": "此請求識別碼已用於其他訂單，請重新操作",
    "ACCOUNT_ALREADY_LINKED": "此帳號已綁定另一個 Google 帳號，請改用原本的 Google 帳號登入",
    "INVALID_TIME_SLOT": "時段須為整點、同一天且結束晚於開始",
    "OUTSIDE_OPENING_HOURS": "所選時段超出場館營業時間，請調整時段",
    "OUT_OF_RANGE": "只能預約下一個整點起 60 天內的時段",
    "OVER_CAPACITY": "使用人數超過空間容量，請調整人數或改選較大的空間",
    "SPACE_UNAVAILABLE": "此空間目前暫停開放，請選擇其他空間",
    "RESCHEDULE_NOT_ALLOWED": "不符合改期條件",
    "REFUND_EXCEEDS_PAID": "退款總額不可超過實收金額",
    "REVIEW_NOT_ALLOWED": "此訂單目前無法評論",
    "PASSWORD_TOO_WEAK": "密碼至少 8 碼，且須同時包含英文與數字",
    "ACCOUNT_LOCKED": "登入失敗次數過多，帳號暫時鎖定，請稍後再試或使用忘記密碼",
    "RATE_LIMITED": "操作太頻繁，請稍後再試",
}


class AppError(Exception):
    """所有業務例外的基底類別；只帶錯誤碼，HTTP 狀態碼由 HTTP_STATUS 對照。"""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or DEFAULT_MESSAGES.get(code, code)
        self.details = details or {}
        super().__init__(f"{code}: {self.message}")


class ValidationError(AppError):
    """VALIDATION_ERROR、TOKEN_INVALID、INVALID_UPLOAD"""


class AuthError(AppError):
    """UNAUTHENTICATED、INVALID_CREDENTIALS"""


class ForbiddenError(AppError):
    """FORBIDDEN、ACCOUNT_RESTRICTED、EMAIL_NOT_VERIFIED"""


class NotFoundError(AppError):
    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__("NOT_FOUND", message, details)


class ConflictError(AppError):
    """SLOT_TAKEN、BOOKING_EXPIRED、INVALID_STATE、PENDING_LIMIT 等"""


class BusinessRuleError(AppError):
    """INVALID_TIME_SLOT、OUT_OF_RANGE、OVER_CAPACITY、REFUND_EXCEEDS_PAID 等"""


class LockedError(AppError):
    """ACCOUNT_LOCKED"""


def error_response(err: AppError):
    """統一錯誤格式 {"error": {"code", "message", "details"}}。"""
    body = {"error": {"code": err.code, "message": err.message, "details": err.details}}
    return jsonify(body), HTTP_STATUS.get(err.code, 400)


def register_error_handlers(app: Flask) -> None:
    """全域錯誤處理器（Controller 層）。"""
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(AppError)
    def _app_error(err: AppError):
        return error_response(err)

    @app.errorhandler(CSRFError)
    def _csrf(err: CSRFError):
        return error_response(AppError("FORBIDDEN", "安全驗證失敗，請重新整理頁面後再試"))

    @app.errorhandler(HTTPException)
    def _http(err: HTTPException):
        mapping = {
            404: ("NOT_FOUND", None),
            401: ("UNAUTHENTICATED", None),
            429: ("RATE_LIMITED", None),
            413: ("INVALID_UPLOAD", "檔案過大，請上傳 5 MB 以內的照片"),
            405: ("FORBIDDEN", "不支援的操作"),
        }
        code, message = mapping.get(err.code or 500, ("VALIDATION_ERROR", err.description))
        return error_response(AppError(code, message))

    @app.errorhandler(Exception)
    def _unhandled(err: Exception):
        app.logger.exception("未處理的例外")
        body = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "系統發生錯誤，請稍後再試",
                "details": {},
            }
        }
        return jsonify(body), 500
