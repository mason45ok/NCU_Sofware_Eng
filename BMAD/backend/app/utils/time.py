"""UTC 與 Asia/Taipei 的轉換工具。資料庫與 API 用含時區時間，畫面以台北時間顯示。"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
_WEEKDAYS = "一二三四五六日"


def to_taipei(value: datetime) -> datetime:
    """轉成台北時間；沒有時區的時間視為 UTC。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(TAIPEI)


def to_utc(value: datetime) -> datetime:
    """轉成 UTC；沒有時區的時間視為台北時間。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=TAIPEI)
    return value.astimezone(UTC)


def local_date(value: datetime) -> date:
    """該時間點在台北的日期。"""
    return to_taipei(value).date()


def combine_local(day: date, at: time) -> datetime:
    """台北當地日期＋時間 → UTC 時間點。"""
    return datetime.combine(day, at, tzinfo=TAIPEI).astimezone(UTC)


def day_hour(day: date, hour: int) -> datetime:
    """台北當地日期的整點（hour 可為 24，代表隔日 00:00）→ UTC。"""
    base = datetime.combine(day, time(0), tzinfo=TAIPEI)
    return (base + timedelta(hours=hour)).astimezone(UTC)


def next_full_hour(now: datetime) -> datetime:
    """下一個整點（現在剛好是整點時為下一小時）。"""
    now = now.astimezone(UTC)
    floor = now.replace(minute=0, second=0, microsecond=0)
    return floor + timedelta(hours=1)


def format_local(value: datetime) -> str:
    """格式：2026/11/20（五）14:00。"""
    local = to_taipei(value)
    return f"{local:%Y/%m/%d}（{_WEEKDAYS[local.weekday()]}）{local:%H:%M}"
