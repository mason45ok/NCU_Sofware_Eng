"""設定：機密與環境差異一律從環境變數讀取。"""

import os


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/judian"
    )
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8080")
    SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "聚點 <no-reply@judian.local>")
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@judian.local")
    GOOGLE_MOCK = _bool("GOOGLE_MOCK", True)
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.abspath("uploads"))
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("APP_ENV", "development") == "production"
    WTF_CSRF_TIME_LIMIT = None
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_ENABLED = True
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}


class TestingConfig(Config):
    TESTING = True
    APP_ENV = "testing"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/judian_test"
    )
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    GOOGLE_MOCK = True
    SECRET_KEY = "test-secret"
    # 併發測試同時使用數十條連線
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_size": 30, "max_overflow": 0}
