"""PricingPolicy：金額與改期價差的純函式（BR-07、BR-14）。不碰資料庫。"""


def amount(hourly_price: int, hours: int) -> int:
    """訂單金額 = 時租 × 時數（時租為下訂當下的快照）。"""
    return hourly_price * hours


def reschedule_diff(snapshot: int, old_hours: int, new_hours: int) -> int:
    """改期價差：以原訂單時租快照計算；正數為需補付，負數為應退。"""
    return amount(snapshot, new_hours) - amount(snapshot, old_hours)
