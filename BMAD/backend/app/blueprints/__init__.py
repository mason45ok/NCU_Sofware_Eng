"""Controller 層：Flask Blueprint。只解析請求、呼叫 Service、轉換回應。"""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from . import admin, auth, bookings, catalog, dev, me

    for module in (auth, me, catalog, bookings, admin):
        app.register_blueprint(module.bp)
    if app.config["APP_ENV"] in ("development", "testing"):
        app.register_blueprint(dev.bp)
