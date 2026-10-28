"""排程工作（FR-50～55）：每個工作只呼叫一個 Service 方法，本身不寫商業邏輯（C8）。"""

from __future__ import annotations

from flask import current_app


def _svc():
    return current_app.extensions["services"]


def expire_pending_bookings() -> int:
    return _svc().bookings.expire_overdue()


def complete_finished_bookings() -> int:
    return _svc().bookings.complete_finished()


def purge_access_codes() -> int:
    return _svc().access_codes.purge_expired()


def purge_account_tokens() -> int:
    return _svc().passwords.purge_tokens()


def freeze_inactive_users() -> int:
    return _svc().admin_users.freeze_inactive()


def retry_failed_notifications() -> int:
    return _svc().notifications.retry_failed()
