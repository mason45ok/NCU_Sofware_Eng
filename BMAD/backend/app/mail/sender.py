"""以 smtplib 寄信。開發環境寄到 Mailpit；測試時以 FakeMailer 取代。"""

import smtplib
from email.message import EmailMessage

from flask import current_app


class Mailer:
    def send(self, to: str, subject: str, body: str) -> None:
        cfg = current_app.config
        msg = EmailMessage()
        msg["From"] = cfg["MAIL_FROM"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as smtp:
            if cfg["SMTP_USER"]:
                smtp.starttls()
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)


class FakeMailer(Mailer):
    """測試用：不真的寄信，只記錄；fail=True 時模擬寄送失敗。"""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    def send(self, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise ConnectionError("模擬寄信失敗")
        self.sent.append((to, subject, body))
