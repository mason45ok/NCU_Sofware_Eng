"""Flask CLI：seed（種子資料）、run-scheduler（排程）。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from flask import Flask


def register_commands(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        """建立種子資料與測試帳號（已有資料時略過）。"""
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import seed

        click.echo(seed.run())

    @app.cli.command("run-scheduler")
    def run_scheduler_command() -> None:
        """啟動排程（獨立容器執行）。"""
        from .jobs.scheduler import build_scheduler

        logging.basicConfig(level=logging.INFO)
        build_scheduler(app).start()
