"""密碼雜湊：PBKDF2-SHA256（600,000 次）、16 bytes 隨機鹽值，比對使用 compare_digest。"""

import hashlib
import hmac
import re
import secrets

ITERATIONS = 600_000


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """回傳 (hash_hex, salt_hex)；每次設定密碼都重新產生鹽值。"""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    candidate, _ = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate, hash_hex)


def is_strong(password: str) -> bool:
    """BR-22：至少 8 碼且含英文與數字。"""
    return (
        len(password) >= 8
        and re.search(r"[A-Za-z]", password) is not None
        and re.search(r"\d", password) is not None
    )
