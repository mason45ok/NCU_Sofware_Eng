"""金流介面：系統自己要的 pay()；各家金流的參數、單位與回傳格式由 Adapter 負責轉換。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewayResult:
    """請款結果。失敗時 reason 為給前端的失敗原因代碼（例如 CARD_DECLINED）。"""

    success: bool
    reason: str | None = None


class PaymentGateway(ABC):
    @abstractmethod
    def pay(self, amount: int, ref: str, card_no: str | None) -> GatewayResult:
        """請款。amount 為新台幣元；ref 為對帳用的訂單編號；card_no 僅信用卡使用。"""
