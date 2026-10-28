"""單次使用權杖與房間密碼的產生。資料庫只存權杖的 SHA-256。"""

import hashlib
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_access_code() -> str:
    """6 位數房間密碼（補零）。"""
    return f"{secrets.randbelow(10**6):06d}"


def new_transaction_no() -> str:
    return "SIM" + secrets.token_hex(8).upper()
