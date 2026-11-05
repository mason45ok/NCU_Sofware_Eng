"""金流 Adapter 與 Factory（BR-09、BR-10；Layer 4：Adapter + 註冊表 Factory）。

前半不需要資料庫；後半以假金流驗證「新增付款方式不必修改 PaymentService／BookingService」。
"""

import pytest

from app.adapters.payment import (
    GatewayResult,
    PaymentGateway,
    PaymentGatewayFactory,
    build_default_factory,
)
from app.adapters.payment.simulated_card import SimulatedCardGateway
from app.adapters.payment.simulated_linepay import SimulatedLinePayGateway
from app.errors import AppError
from app.models import PaymentMethod
from tests.helpers import CARD_DECLINED, CARD_OK, error_code, req


# ---------- Adapter（純邏輯，無資料庫） ----------
def test_br09_card_adapter_declines_only_the_magic_card():
    gateway = SimulatedCardGateway()
    assert gateway.pay(300, "B1", CARD_DECLINED) == GatewayResult(False, "CARD_DECLINED")
    assert gateway.pay(300, "B1", "4000000000000002") == GatewayResult(False, "CARD_DECLINED")
    assert gateway.pay(300, "B1", CARD_OK) == GatewayResult(True)
    assert gateway.pay(300, "B1", None) == GatewayResult(True)  # 未填卡號沿用原本行為


def test_br10_linepay_adapter_succeeds():
    assert SimulatedLinePayGateway().pay(300, "B1", None) == GatewayResult(True)


# ---------- Factory（註冊表，無資料庫） ----------
def test_default_factory_covers_every_payment_method():
    """新增 PaymentMethod 卻忘了註冊 Adapter 時，這個測試會失敗。"""
    factory = build_default_factory()
    assert set(factory.methods()) == {m.value for m in PaymentMethod}
    assert isinstance(factory.create("CREDIT_CARD"), SimulatedCardGateway)
    assert isinstance(factory.create(PaymentMethod.LINE_PAY), SimulatedLinePayGateway)


def test_factory_rejects_unregistered_method():
    with pytest.raises(AppError) as exc:
        build_default_factory().create("JKO_PAY")
    assert exc.value.code == "VALIDATION_ERROR"


def test_factory_register_adds_method_without_modifying_existing_code():
    class AlwaysOk(PaymentGateway):
        def pay(self, amount, ref, card_no):
            return GatewayResult(True)

    factory = PaymentGatewayFactory()
    factory.register("JKO_PAY", AlwaysOk)
    assert isinstance(factory.create("JKO_PAY"), AlwaysOk)


# ---------- 與 BookingService 整合（需要資料庫） ----------
class RecordingGateway(PaymentGateway):
    def __init__(self, calls, result):
        self.calls, self.result = calls, result

    def pay(self, amount, ref, card_no):
        self.calls.append((amount, ref, card_no))
        return self.result


@pytest.fixture
def fake_gateway(services, monkeypatch):
    """讓 PaymentService 改用只註冊假金流的 Factory（測完自動還原）。"""
    calls: list = []

    def install(result: GatewayResult):
        factory = PaymentGatewayFactory()
        factory.register("CREDIT_CARD", lambda: RecordingGateway(calls, result))
        monkeypatch.setattr(services.payments, "gateways", factory)
        return calls

    return install


@pytest.mark.usefixtures("db_clean")
def test_br10_booking_pay_goes_through_the_registered_gateway(
    services, make_user, space_id, fake_gateway
):
    calls = fake_gateway(GatewayResult(True))
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    result = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", "any-card", "k1")
    assert result.status == "SUCCESS"
    assert calls == [(created.total_amount, created.booking_no, "any-card")]


@pytest.mark.usefixtures("db_clean")
def test_br09_gateway_failure_reason_is_returned_and_booking_stays_pending(
    services, make_user, space_id, fake_gateway
):
    fake_gateway(GatewayResult(False, "INSUFFICIENT_FUNDS"))
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    result = services.bookings.pay(user, created.booking_id, "CREDIT_CARD", None, "k1")
    assert result.status == "FAILED" and result.reason == "INSUFFICIENT_FUNDS"
    assert result.booking.status == "PENDING_PAYMENT"


@pytest.mark.usefixtures("db_clean")
def test_unregistered_method_is_rejected_before_any_payment_is_written(
    services, make_user, space_id
):
    user = make_user()
    created = services.bookings.create(user, req(space_id))
    assert (
        error_code(services.bookings.pay, user, created.booking_id, "JKO_PAY", None, "k1")
        == "VALIDATION_ERROR"
    )
    assert services.payments.find_by_key("k1") is None
