"""種子資料：測試帳號（密碼皆為 Passw0rd!）、場館、空間、設備、示範訂單與評論。"""

from __future__ import annotations

import os
from datetime import UTC, datetime, time, timedelta

from flask import current_app
from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    AccessCode,
    Booking,
    BookingAction,
    BookingStatus,
    Branch,
    Equipment,
    ExternalAccount,
    Payment,
    Review,
    Role,
    Space,
    SpaceEquipment,
    SpacePhoto,
    User,
    UserPassword,
    UserStatus,
)
from app.security.passwords import hash_password
from app.utils.time import day_hour, local_date

PASSWORD = "Passw0rd!"

EQUIPMENT = [
    ("投影機", "AV"),
    ("白板", "FURNITURE"),
    ("音響", "AV"),
    ("麥克風", "AV"),
    ("Wi-Fi", "NETWORK"),
    ("飲水機", "KITCHEN"),
    ("冷氣", "OTHER"),
    ("攝影燈", "AV"),
    ("長桌", "FURNITURE"),
    ("簡易廚房", "KITCHEN"),
]

BRANCHES = [
    dict(
        name="聚點 中壢中央店",
        city="桃園市",
        district="中壢區",
        address="中大路 300 號 2 樓",
        phone="03-4227151",
        latitude=24.9677,
        longitude=121.1916,
        open_time=time(9),
        close_time=time(22),
    ),
    dict(
        name="聚點 台北信義店",
        city="台北市",
        district="信義區",
        address="松仁路 100 號 5 樓",
        phone="02-27201234",
        latitude=25.0330,
        longitude=121.5654,
        open_time=time(8),
        close_time=time(22),
    ),
    dict(
        name="聚點 台中西屯店",
        city="台中市",
        district="西屯區",
        address="台灣大道三段 99 號 3 樓",
        phone="04-23581234",
        latitude=24.1790,
        longitude=120.6460,
        open_time=time(9),
        close_time=time(21),
    ),
]

# (場館索引, 名稱, 類型, 容量, 坪數, 時租, 介紹, 設備名稱)
SPACES = [
    (
        0,
        "201 會議室",
        "MEETING",
        8,
        8.0,
        300,
        "明亮的小型會議室，適合讀書會與小組討論。",
        ["投影機", "白板", "Wi-Fi", "冷氣"],
    ),
    (
        0,
        "202 討論室",
        "CLASSROOM",
        12,
        12.0,
        400,
        "可排成教室式座位，適合工作坊與課後輔導。",
        ["投影機", "白板", "Wi-Fi", "冷氣", "長桌"],
    ),
    (
        0,
        "301 派對廳",
        "PARTY",
        20,
        20.0,
        800,
        "木質風格聚會空間，附簡易廚房與音響。",
        ["音響", "麥克風", "簡易廚房", "飲水機", "Wi-Fi"],
    ),
    (
        1,
        "A1 會議室",
        "MEETING",
        10,
        10.0,
        500,
        "信義商圈精緻會議室。",
        ["投影機", "白板", "Wi-Fi", "冷氣"],
    ),
    (
        1,
        "A2 攝影棚",
        "STUDIO",
        6,
        9.0,
        700,
        "附攝影燈與背景布，適合小型拍攝。",
        ["攝影燈", "Wi-Fi", "冷氣"],
    ),
    (
        1,
        "B1 多功能室",
        "MULTI",
        30,
        30.0,
        1200,
        "大型多功能空間，活動、講座皆適用。",
        ["投影機", "音響", "麥克風", "Wi-Fi", "冷氣"],
    ),
    (
        2,
        "101 小教室",
        "CLASSROOM",
        10,
        11.0,
        350,
        "安靜的小教室。",
        ["白板", "投影機", "Wi-Fi"],
    ),
    (
        2,
        "102 聚會室",
        "PARTY",
        16,
        16.0,
        600,
        "適合慶生與朋友聚會。",
        ["音響", "簡易廚房", "飲水機", "冷氣"],
    ),
    (
        2,
        "103 會議室",
        "MEETING",
        6,
        6.0,
        250,
        "四到六人的小型會議室。",
        ["白板", "Wi-Fi", "冷氣"],
    ),
]
COLORS = ["#B4632E", "#5F7A45", "#8C6A4F", "#C9A27A", "#6E8B6B", "#A15C38"]


def _svg(path: str, title: str, color: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500">'
            f'<rect width="800" height="500" fill="{color}"/>'
            f'<text x="400" y="260" font-size="48" fill="#FAF6F0" text-anchor="middle" '
            f'font-family="sans-serif">{title}</text></svg>'
        )


def _user(
    email,
    name,
    *,
    role=Role.USER,
    status=UserStatus.ACTIVE,
    reason=None,
    verified=True,
    password=True,
):
    now = datetime.now(UTC)
    user = User(
        email=email,
        name=name,
        role=role.value,
        status=status.value,
        status_reason=reason,
        email_verified_at=now if verified else None,
        last_login_at=now,
    )
    if password:
        hash_hex, salt_hex = hash_password(PASSWORD)
        user.password = UserPassword(password_hash=hash_hex, password_salt=salt_hex)
    db.session.add(user)
    return user


def _demo_booking(user, space, start, end, status_flow, *, paid=True):
    """建立示範訂單，狀態一律透過 transition()。"""
    hours = int((end - start).total_seconds() // 3600)
    now = datetime.now(UTC)
    booking = Booking(
        booking_no=f"B{local_date(now):%Y%m%d}-{900 + db.session.scalar(select(func.count(Booking.booking_id)))}",
        user_id=user.user_id,
        space_id=space.space_id,
        start_at=start,
        end_at=end,
        attendees=2,
        hourly_price_snapshot=space.hourly_price,
        total_amount=space.hourly_price * hours,
        expires_at=now + timedelta(minutes=15),
        reschedule_count=0,
    )
    booking.transition(BookingStatus.PENDING_PAYMENT, BookingAction.CREATE, user.user_id, None)
    db.session.add(booking)
    db.session.flush()
    if paid:
        booking.payments.append(
            Payment(
                type="PAYMENT",
                amount=booking.total_amount,
                method="CREDIT_CARD",
                status="SUCCESS",
                idempotency_key=f"seed-pay-{booking.booking_id}",
                transaction_no=f"SIMSEED{booking.booking_id}",
                created_by=user.user_id,
            )
        )
        booking.transition(BookingStatus.CONFIRMED, BookingAction.PAY, user.user_id, None)
        booking.access_code = AccessCode(
            code=f"{(booking.booking_id * 7919) % 10**6:06d}",
            valid_from=start - timedelta(minutes=10),
            valid_until=end,
        )
    for target, action in status_flow:
        booking.transition(target, action, None, None)
    db.session.flush()
    return booking


def run() -> str:
    if db.session.scalar(select(func.count(User.user_id))):
        return "已有資料，略過種子資料"

    _user("admin@judian.local", "管理員", role=Role.ADMIN)
    user1 = _user("user1@judian.local", "王小明")
    user2 = _user("user2@judian.local", "林小美")
    _user("unverified@judian.local", "未驗證會員", verified=False)
    _user(
        "frozen@judian.local",
        "被凍結會員",
        status=UserStatus.FROZEN,
        reason="測試用：違反使用規定",
    )
    _user(
        "blacklisted@judian.local",
        "黑名單會員",
        status=UserStatus.BLACKLISTED,
        reason="測試用：多次未到場",
    )
    google = _user("g1@gmail.com", "Google 使用者一號", password=False)
    db.session.flush()
    google.external_accounts.append(
        ExternalAccount(
            provider="GOOGLE",
            provider_user_id="google-001",
            provider_email="g1@gmail.com",
        )
    )

    equipment = {}
    for name, category in EQUIPMENT:
        equipment[name] = Equipment(name=name, category=category)
        db.session.add(equipment[name])
    branches = [Branch(**b) for b in BRANCHES]
    db.session.add_all(branches)
    db.session.flush()

    upload_dir = current_app.config["UPLOAD_DIR"]
    spaces = []
    for index, (b, name, kind, cap, area, price, desc, items) in enumerate(SPACES):
        space = Space(
            branch_id=branches[b].branch_id,
            name=name,
            space_type=kind,
            capacity=cap,
            area=area,
            hourly_price=price,
            description=desc,
            rules="請愛惜設備、保持整潔；禁止吸菸；離場前請將桌椅歸位並帶走垃圾。",
            entry_guide="抵達後請至一樓電梯上樓，於房門輸入訂單的 6 位數房間密碼即可進入；離場時關閉電源與冷氣。",
        )
        db.session.add(space)
        db.session.flush()
        for order in range(2):
            filename = f"space-{space.space_id}-{order}.svg"
            _svg(
                os.path.join(upload_dir, "seed", filename),
                name,
                COLORS[(index + order) % len(COLORS)],
            )
            db.session.add(
                SpacePhoto(
                    space_id=space.space_id,
                    image_url=f"/uploads/seed/{filename}",
                    caption=name,
                    sort_order=order,
                )
            )
        for item in items:
            db.session.add(
                SpaceEquipment(space_id=space.space_id, equipment_id=equipment[item].equipment_id)
            )
        spaces.append(space)
    db.session.flush()

    today = local_date(datetime.now(UTC))
    # 已完成並已評論的訂單（示範評論與歷史訂單）
    done = _demo_booking(
        user1,
        spaces[0],
        day_hour(today - timedelta(days=3), 10),
        day_hour(today - timedelta(days=3), 12),
        [(BookingStatus.COMPLETED, BookingAction.COMPLETE)],
    )
    db.session.add(
        Review(
            booking_id=done.booking_id,
            rating=5,
            comment="空間乾淨、設備齊全，很適合讀書會！",
        )
    )
    # 未來已確認的訂單
    _demo_booking(
        user2,
        spaces[2],
        day_hour(today + timedelta(days=5), 14),
        day_hour(today + timedelta(days=5), 17),
        [],
    )
    db.session.commit()
    return "種子資料已建立（測試帳號密碼：Passw0rd!）"
