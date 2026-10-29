"""列舉（D1、D2）。資料庫以 VARCHAR＋CHECK 儲存，程式以 StrEnum 表示。"""

from enum import StrEnum


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    BLACKLISTED = "BLACKLISTED"


class TokenPurpose(StrEnum):
    VERIFY_EMAIL = "VERIFY_EMAIL"
    RESET_PASSWORD = "RESET_PASSWORD"
    SET_PASSWORD = "SET_PASSWORD"


class BranchStatus(StrEnum):
    OPEN = "OPEN"
    DISABLED = "DISABLED"


class SpaceType(StrEnum):
    MEETING = "MEETING"
    CLASSROOM = "CLASSROOM"
    PARTY = "PARTY"
    STUDIO = "STUDIO"
    MULTI = "MULTI"


class SpaceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    MAINTENANCE = "MAINTENANCE"
    DISABLED = "DISABLED"


class EquipmentCategory(StrEnum):
    AV = "AV"
    FURNITURE = "FURNITURE"
    KITCHEN = "KITCHEN"
    NETWORK = "NETWORK"
    OTHER = "OTHER"


class BookingStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class BookingAction(StrEnum):
    CREATE = "CREATE"
    PAY = "PAY"
    CANCEL = "CANCEL"
    EXPIRE = "EXPIRE"
    COMPLETE = "COMPLETE"
    RESCHEDULE = "RESCHEDULE"
    REFUND = "REFUND"


class PaymentType(StrEnum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"


class PaymentMethod(StrEnum):
    CREDIT_CARD = "CREDIT_CARD"
    LINE_PAY = "LINE_PAY"


class PaymentStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AccessCodeState(StrEnum):
    NOT_YET_VALID = "NOT_YET_VALID"
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class NotificationType(StrEnum):
    VERIFY_EMAIL = "VERIFY_EMAIL"
    RESET_PASSWORD = "RESET_PASSWORD"
    SET_PASSWORD = "SET_PASSWORD"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"


class SendStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
