"""信件範本。回傳 (主旨, 內文)；訂單類信件從訂單資料即時組出，重寄時內容一致。"""

from __future__ import annotations

from flask import current_app

from ..models import Booking, BookingAction, NotificationType
from ..utils.time import format_local


def _footer() -> str:
    return f"\n\n如有問題請聯絡客服：{current_app.config['SUPPORT_EMAIL']}\n聚點 空間租借"


def token_mail(type_: NotificationType, name: str, link: str) -> tuple[str, str]:
    if type_ == NotificationType.VERIFY_EMAIL:
        subject = "【聚點】請驗證您的 email"
        body = f"{name} 您好，\n\n請於 24 小時內點擊下方連結完成 email 驗證：\n{link}"
    elif type_ == NotificationType.RESET_PASSWORD:
        subject = "【聚點】重設密碼"
        body = f"{name} 您好，\n\n請於 30 分鐘內點擊下方連結重設密碼（連結僅能使用一次）：\n{link}"
    else:
        subject = "【聚點】設定登入密碼"
        body = (
            f"{name} 您好，\n\n請於 30 分鐘內點擊下方連結設定密碼，之後即可用 email 與密碼登入"
            f"（連結僅能使用一次）：\n{link}"
        )
    return subject, body + _footer()


def _booking_lines(booking: Booking) -> str:
    space = booking.space
    branch = space.branch
    return (
        f"訂單編號：{booking.booking_no}\n"
        f"空間：{branch.name} {space.name}\n"
        f"地址：{branch.city}{branch.district}{branch.address}\n"
        f"時段：{format_local(booking.start_at)} ～ {format_local(booking.end_at)}\n"
        f"金額：NT$ {booking.total_amount}\n"
        f"場館電話：{branch.phone}"
    )


def booking_mail(type_: NotificationType, booking: Booking) -> tuple[str, str]:
    name = booking.user.name
    lines = _booking_lines(booking)
    code = booking.access_code
    if type_ == NotificationType.BOOKING_CONFIRMED:
        subject = f"【聚點】預約成功 {booking.booking_no}"
        body = f"{name} 您好，\n\n您的預約已確認。\n\n{lines}\n"
        if code:
            body += (
                f"\n房間密碼：{code.code}\n有效時間：{format_local(code.valid_from)} ～ "
                f"{format_local(code.valid_until)}\n"
            )
        if booking.space.entry_guide:
            body += f"\n進入方式：\n{booking.space.entry_guide}\n"
    elif type_ == NotificationType.BOOKING_CANCELLED:
        subject = f"【聚點】訂單已取消 {booking.booking_no}"
        body = f"{name} 您好，\n\n您的訂單已取消。\n\n{lines}\n\n退款金額：NT$ {booking.refunded_amount()}"
        if booking.cancel_reason:
            body += f"\n取消原因：{booking.cancel_reason}"
    else:
        subject = f"【聚點】訂單已改期 {booking.booking_no}"
        reschedule = [log for log in booking.logs if log.action == BookingAction.RESCHEDULE]
        change = reschedule[-1].reason if reschedule else ""
        body = f"{name} 您好，\n\n您的訂單已改期。\n變更：{change}\n\n{lines}\n"
        if code:
            body += (
                f"\n房間密碼：{code.code}\n新的有效時間：{format_local(code.valid_from)} ～ "
                f"{format_local(code.valid_until)}\n"
            )
    return subject, body + _footer()
