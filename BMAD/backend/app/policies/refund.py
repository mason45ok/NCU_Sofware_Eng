"""RefundPolicy：退款比例（Strategy）與退款金額（純函式），BR-12、BR-13。不碰資料庫。

新增退款規則 = 新增一個 RefundPolicy 子類別，BookingService 的取消流程不必修改。
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

# 全站取消規則（顯示用文字；門檻須與 MemberRefundPolicy.TIERS 一致，test_policies 有檢查）
CANCEL_POLICY_TEXT = [
    "開始前 24 小時以上取消：全額退款",
    "開始前 3～24 小時取消：退款 50%",
    "開始前不到 3 小時取消：不退款",
    "付款期限為建立訂單後 15 分鐘，逾時訂單自動失效",
]


class RefundPolicy(ABC):
    """退款比例策略：依訂單開始時間與現在時間，決定退款比例（0～1）。"""

    @abstractmethod
    def ratio(self, start_at: datetime, now: datetime) -> Decimal: ...


class MemberRefundPolicy(RefundPolicy):
    """會員取消：開始前 ≥24 小時 100%；≥3 小時 50%；不到 3 小時 0%（階梯以資料表示）。"""

    TIERS: tuple[tuple[timedelta, Decimal], ...] = (
        (timedelta(hours=24), Decimal(1)),
        (timedelta(hours=3), Decimal("0.5")),
    )

    def ratio(self, start_at: datetime, now: datetime) -> Decimal:
        lead = start_at - now
        for threshold, ratio in self.TIERS:
            if lead >= threshold:
                return ratio
        return Decimal(0)


class AdminRefundPolicy(RefundPolicy):
    """管理員因場地因素取消：一律全額退款。"""

    def ratio(self, start_at: datetime, now: datetime) -> Decimal:
        return Decimal(1)


class NoRefundPolicy(RefundPolicy):
    """待付款訂單取消：沒有付款，不涉及退款（取代流程中的 if 判斷）。"""

    def ratio(self, start_at: datetime, now: datetime) -> Decimal:
        return Decimal(0)


def refund_amount(net_paid: int, ratio: Decimal) -> int:
    """以實收金額計算退款，四捨五入到元。"""
    return int((Decimal(net_paid) * ratio).quantize(Decimal(1), rounding=ROUND_HALF_UP))
