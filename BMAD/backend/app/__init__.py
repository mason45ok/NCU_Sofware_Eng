"""聚點 空間租借系統：Flask 應用程式工廠。"""

from __future__ import annotations

import os

from flask import Flask

from .config import Config
from .errors import register_error_handlers
from .extensions import csrf, db, limiter, login_manager, migrate
from .mail.sender import Mailer
from .utils.clock import Clock


def create_app(
    config: type | dict | None = None,
    clock: Clock | None = None,
    mailer: Mailer | None = None,
) -> Flask:
    """clock、mailer 可注入替換（測試時使用固定時間與假寄信）。"""
    app = Flask(__name__)
    app.config.from_object(Config)
    if isinstance(config, dict):
        app.config.update(config)
    elif config is not None:
        app.config.from_object(config)

    db.init_app(app)
    from . import models  # noqa: F401  讓 Alembic 看見全部資料表

    migrate.init_app(
        app,
        db,
        directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"),
    )
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    from .security.permissions import SessionUser
    from .services import build_services

    app.extensions["services"] = build_services(clock or Clock(), mailer or Mailer())

    @login_manager.user_loader
    def load_user(user_id: str):
        dto = app.extensions["services"].auth.get(int(user_id))
        return SessionUser(dto) if dto else None

    register_error_handlers(app)
    from .blueprints import register_blueprints

    register_blueprints(app)

    from .cli import register_commands

    register_commands(app)
    return app
