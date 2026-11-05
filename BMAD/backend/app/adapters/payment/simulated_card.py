"""模擬信用卡金流（Adapter）。實際串接銀行 API 時，只需新增一個同介面的類別。"""

from __future__ import annotations

import re

from .base import GatewayResult, PaymentGateway

DECLINED_CARD = "4000000000000002"


class SimulatedCardGateway(PaymentGateway):
    def pay(self, amount: int, ref: str, card_no: str | None) -> GatewayResult:
        """BR-09：信用卡號 4000 0000 0000 0002 一律遭拒，其餘成功。"""
        if card_no and re.sub(r"\D", "", card_no) == DECLINED_CARD:
            return GatewayResult(False, "CARD_DECLINED")
        return GatewayResult(True)
