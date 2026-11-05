"""依賴規則（Layer 4）：業務邏輯不得直接 import 外部服務 SDK；規則寫成測試，違反即紅燈。

不需要資料庫。
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[2] / "app"

# 層 → 不得 import 的套件（頂層名稱）
FORBIDDEN = {
    "policies": {"sqlalchemy", "flask", "authlib", "smtplib", "requests"},
    "services": {"authlib", "smtplib", "requests"},
    "blueprints": {"authlib", "smtplib", "requests"},
}


def _imports(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or "").split(".")[0])
    return names


def test_layers_do_not_import_infrastructure_sdks():
    violations = [
        f"{path.relative_to(APP)}: {name}"
        for layer, banned in FORBIDDEN.items()
        for path in (APP / layer).rglob("*.py")
        for name in sorted(_imports(path) & banned)
    ]
    assert violations == []


def test_payment_services_use_the_gateway_factory_not_concrete_adapters():
    """services/ 只能經由 PaymentGatewayFactory 取得金流，不得直接 import 具體 Adapter。"""
    offenders = []
    for path in (APP / "services").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                module = node.module or ""
                if module.startswith("adapters.payment.simulated"):
                    offenders.append(str(path.relative_to(APP)))
    assert offenders == []


def test_booking_thresholds_are_defined_only_in_booking_rules():
    """改期 24 小時、評論 30 天、待付款上限等門檻只能在 policies/booking_rules.py 賦值一次。"""
    names = {"PENDING_LIMIT", "RESCHEDULE_MIN_LEAD", "MAX_RESCHEDULES", "REVIEW_WINDOW"}
    offenders = []
    for path in APP.rglob("*.py"):
        if path.name == "booking_rules.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assign):
                targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
                if targets & names:
                    offenders.append(str(path.relative_to(APP)))
    assert offenders == []


def test_booking_service_accesses_data_only_through_repository():
    """BookingService 不得直接使用 db.session、select 或 sqlalchemy（IntegrityError 例外轉譯除外）。"""
    path = APP / "services" / "booking.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(("." * node.level) + (node.module or ""))
    assert "..extensions" not in imported
    assert [m for m in imported if m.startswith("sqlalchemy") and m != "sqlalchemy.exc"] == []
    assert "db.session" not in path.read_text(encoding="utf-8")
