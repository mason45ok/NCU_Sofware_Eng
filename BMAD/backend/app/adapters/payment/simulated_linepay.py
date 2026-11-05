"""模擬 LINE Pay 金流（Adapter）。模擬模式下一律成功。"""

from __future__ import annotations

from .base import GatewayResult, PaymentGateway


class SimulatedLinePayGateway(PaymentGateway):
    def pay(self, amount: int, ref: str, card_no: str | None) -> GatewayResult:
        return GatewayResult(True)
