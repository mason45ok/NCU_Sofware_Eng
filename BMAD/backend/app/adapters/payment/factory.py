"""PaymentGatewayFactory：以註冊表依付款方式取得金流 Adapter（取代 if/elif 鏈）。

新增付款方式 = 新增一個 PaymentGateway 類別，並在 build_default_factory() 多一行 register。
"""

from __future__ import annotations

from collections.abc import Callable

from ...errors import ValidationError
from ...models import PaymentMethod
from .base import PaymentGateway
from .simulated_card import SimulatedCardGateway
from .simulated_linepay import SimulatedLinePayGateway


class PaymentGatewayFactory:
    def __init__(self) -> None:
        self._makers: dict[str, Callable[[], PaymentGateway]] = {}

    def register(self, method: str, maker: Callable[[], PaymentGateway]) -> None:
        self._makers[str(method)] = maker

    def methods(self) -> list[str]:
        return list(self._makers)

    def create(self, method: str) -> PaymentGateway:
        maker = self._makers.get(str(method))
        if maker is None:
            raise ValidationError(
                "VALIDATION_ERROR",
                "不支援的付款方式，請改選其他付款方式",
                {"method": "不支援"},
            )
        return maker()


def build_default_factory() -> PaymentGatewayFactory:
    factory = PaymentGatewayFactory()
    factory.register(PaymentMethod.CREDIT_CARD, SimulatedCardGateway)
    factory.register(PaymentMethod.LINE_PAY, SimulatedLinePayGateway)
    return factory
