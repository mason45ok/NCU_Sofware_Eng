"""可替換的時鐘：Service 一律透過注入的 Clock 取得現在時間（C13）。"""

from datetime import UTC, datetime, timedelta


class Clock:
    """正式環境使用的系統時鐘（回傳含時區的 UTC 時間）。"""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """測試用固定時鐘，可手動設定或前進。"""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now

    def advance(self, **kwargs: float) -> None:
        self._now = self._now + timedelta(**kwargs)
