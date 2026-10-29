"""密碼雜湊與強度規則（BR-22；不需資料庫）。"""

import pytest

from app.security import passwords, tokens


@pytest.mark.parametrize(
    ("password", "ok"),
    [
        ("Passw0rd!", True),
        ("abcdefg1", True),
        ("short1A", False),
        ("onlyletters", False),
        ("12345678", False),
    ],
)
def test_br22_password_strength(password, ok):
    assert passwords.is_strong(password) is ok


def test_hash_verify_and_unique_salt():
    h1, s1 = passwords.hash_password("Passw0rd!")
    h2, s2 = passwords.hash_password("Passw0rd!")
    assert s1 != s2 and h1 != h2  # 每次重新產生鹽值
    assert len(h1) == 64 and len(s1) == 32  # 對應 CHAR(64)／CHAR(32)
    assert passwords.verify_password("Passw0rd!", h1, s1)
    assert not passwords.verify_password("wrong-pass1", h1, s1)


def test_tokens_are_hashed_and_codes_are_six_digits():
    token = tokens.new_token()
    assert tokens.hash_token(token) != token and len(tokens.hash_token(token)) == 64
    assert all(len(tokens.new_access_code()) == 6 for _ in range(50))
