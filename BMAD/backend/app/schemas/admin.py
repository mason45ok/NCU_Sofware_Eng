"""管理後台的請求與回應。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from .base import DTO, Request, TPDatetime
from .booking import BookingDTO


class BranchReq(Request):
    name: str = Field(min_length=1, max_length=50)
    city: str = Field(min_length=1, max_length=20)
    district: str = Field(min_length=1, max_length=20)
    address: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=20)
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    open_hour: int = Field(ge=0, le=23)
    close_hour: int = Field(ge=1, le=23)


class BranchDTO(DTO):
    branch_id: int
    name: str
    city: str
    district: str
    address: str
    phone: str
    latitude: float
    longitude: float
    open_hour: int
    close_hour: int
    status: str
    space_count: int = 0


class StatusReq(Request):
    status: str


class SpaceReq(Request):
    branch_id: int
    name: str = Field(min_length=1, max_length=50)
    space_type: str
    capacity: int = Field(gt=0)
    area: Decimal | None = Field(default=None, gt=0)
    hourly_price: int = Field(gt=0)
    description: str | None = None
    rules: str | None = None
    entry_guide: str | None = None


class AdminSpaceDTO(DTO):
    space_id: int
    branch_id: int
    branch_name: str
    name: str
    space_type: str
    capacity: int
    area: float | None = None
    hourly_price: int
    description: str | None = None
    rules: str | None = None
    entry_guide: str | None = None
    status: str


class AffectedResult(DTO):
    """停用場館或空間時，受影響的未來訂單（BR-18）。"""

    affected_bookings: list[BookingDTO]


class PhotoOrderReq(Request):
    photo_ids: list[int]


class PhotoPatchReq(Request):
    caption: str | None = Field(default=None, max_length=100)


class EquipmentReq(Request):
    name: str = Field(min_length=1, max_length=50)
    category: str
    is_active: bool = True


class EquipmentPatchReq(Request):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    category: str | None = None
    is_active: bool | None = None


class EquipmentDTO(DTO):
    equipment_id: int
    name: str
    category: str
    is_active: bool


class SpaceEquipmentItem(Request):
    equipment_id: int
    quantity: int = Field(default=1, gt=0)
    note: str | None = Field(default=None, max_length=100)


class SpaceEquipmentReq(Request):
    items: list[SpaceEquipmentItem]


class UserStatusReq(Request):
    status: str
    reason: str | None = Field(default=None, max_length=200)


class BookingFilters(BaseModel):
    no: str | None = None
    email: str | None = None
    space_id: int | None = None
    date_from: date | None = Field(default=None, alias="from")
    date_to: date | None = Field(default=None, alias="to")
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class StatusLogDTO(DTO):
    log_id: int
    from_status: str | None = None
    to_status: str
    action: str
    changed_by: int | None = None
    reason: str | None = None
    created_at: TPDatetime


class NotificationDTO(DTO):
    notification_id: int
    user_id: int
    booking_id: int | None = None
    type: str
    recipient: str
    subject: str
    status: str
    attempts: int
    error_message: str | None = None
    sent_at: TPDatetime | None = None
    created_at: TPDatetime


class AdminBookingDetail(DTO):
    booking: BookingDTO
    logs: list[StatusLogDTO]
    notifications: list[NotificationDTO]


class AdminSummary(DTO):
    today_bookings: int
    pending_affected_bookings: int
    failed_notifications: int
