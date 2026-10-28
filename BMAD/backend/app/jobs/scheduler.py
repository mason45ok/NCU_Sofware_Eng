"""APScheduler 設定。獨立的 scheduler 容器執行（flask run-scheduler），避免多個 worker 重複執行。"""

from __future__ import annotations

import logging
from functools import partial

from apscheduler.schedulers.blocking import BlockingScheduler
from flask import Flask

from . import (
    complete_finished_bookings,
    expire_pending_bookings,
    freeze_inactive_users,
    purge_access_codes,
    purge_account_tokens,
    retry_failed_notifications,
)

log = logging.getLogger("scheduler")

# (函式, cron 設定)；時區 Asia/Taipei
SCHEDULE = [
    (expire_pending_bookings, {"minute": "*"}),  # FR-50 每分鐘
    (complete_finished_bookings, {"minute": "*/5"}),  # FR-51 每 5 分鐘
    (purge_access_codes, {"hour": 3, "minute": 0}),  # FR-52
    (purge_account_tokens, {"hour": 3, "minute": 10}),  # FR-53
    (freeze_inactive_users, {"hour": 3, "minute": 20}),  # FR-54
    (retry_failed_notifications, {"minute": "*/10"}),  # FR-55
]


def _run(app: Flask, job) -> None:
    """每次執行寫入日誌；工作本身冪等，失敗不影響其他工作。"""
    with app.app_context():
        try:
            log.info("%s 完成，處理 %s 筆", job.__name__, job())
        except Exception:
            log.exception("%s 失敗", job.__name__)


def build_scheduler(app: Flask) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Taipei")
    for job, cron in SCHEDULE:
        scheduler.add_job(
            partial(_run, app, job),
            "cron",
            id=job.__name__,
            max_instances=1,
            coalesce=True,
            **cron,
        )
    return scheduler
