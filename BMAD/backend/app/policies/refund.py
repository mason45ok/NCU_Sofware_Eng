"""RefundPolicy：退款比例與金額的純函式（BR-12、BR-13）。不碰資料庫。"""

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

# 全站取消規則（顯示用文字；與下方函式的門檻一致）
CANCEL_POLICY_TEXT = [
    "開始前 24 小時以上取消：全額退款",
    "開始前 3～24 小時取消：退款 50%",
    "開始前不到 3 小時取消：不退款",
    "付款期限為建立訂單後 15 分鐘，逾時訂單自動失效",
]


def member_ratio(start_at: datetime, now: datetime) -> Decimal:
    """會員取消：開始前 ≥24 小時 100%；≥3 小時 50%；不到 3 小時 0%。"""
    delta = start_at - now
    if delta >= timedelta(hours=24):
        return Decimal(1)
    if delta >= timedelta(hours=3):
        return Decimal("0.5")
    return Decimal(0)


def admin_ratio() -> Decimal:
    """管理員因場地因素取消：一律全額退款。"""
    return Decimal(1)


def refund_amount(net_paid: int, ratio: Decimal) -> int:
    """以實收金額計算退款，四捨五入到元。"""
    return int((Decimal(net_paid) * ratio).quantize(Decimal(1), rounding=ROUND_HALF_UP))
