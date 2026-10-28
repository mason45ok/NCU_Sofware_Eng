"""目錄、可預約時段、評論的請求與回應。"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field

from .base import DTO, Request, TPDatetime


class SpaceFilters(BaseModel):
    """搜尋條件（FR-10～12）；start/end 為當地整點（0～24）。"""

    city: str | None = None
    district: str | None = None
    people: int | None = Field(default=None, ge=1)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    type: str | None = None
    equipment: list[int] = Field(default_factory=list)
    date: dt.date | None = None
    start: int | None = Field(default=None, ge=0, le=23)
    end: int | None = Field(default=None, ge=1, le=24)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    sort: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=50)


class SpaceSummary(DTO):
    space_id: int
    name: str
    branch_name: str
    city: str
    district: str
    space_type: str
    capacity: int
    hourly_price: int
    status: str
    cover_url: str | None = None
    avg_rating: float | None = None
    review_count: int = 0
    distance_km: float | None = None


class PhotoDTO(DTO):
    photo_id: int
    image_url: str
    caption: str | None = None
    sort_order: int


class EquipmentItemDTO(DTO):
    equipment_id: int
    name: str
    category: str
    quantity: int
    note: str | None = None


class BranchInfo(DTO):
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
    maps_url: str


class SpaceDetail(DTO):
    space_id: int
    name: str
    space_type: str
    capacity: int
    area: float | None = None
    hourly_price: int
    description: str | None = None
    rules: str | None = None
    entry_guide: str | None = None
    status: str
    bookable: bool
    cancel_policy: list[str]
    branch: BranchInfo
    photos: list[PhotoDTO]
    equipment: list[EquipmentItemDTO]
    avg_rating: float | None = None
    review_count: int = 0


class FilterOptions(DTO):
    cities: dict[str, list[str]]
    space_types: list[str]
    equipment: list[dict]


class Slot(DTO):
    """status：AVAILABLE（可預約）、BOOKED（已被預約）、PAST（已過去）。"""

    start: int
    end: int
    start_at: TPDatetime
    end_at: TPDatetime
    status: str


class AvailabilityDTO(DTO):
    space_id: int
    date: dt.date
    bookable: bool
    reason: str | None = None
    open_hour: int | None = None
    close_hour: int | None = None
    slots: list[Slot]


class ReviewDTO(DTO):
    review_id: int
    booking_id: int | None = None
    space_id: int | None = None
    space_name: str | None = None
    reviewer: str
    rating: int
    comment: str | None = None
    is_hidden: bool = False
    created_at: TPDatetime


class ReviewReq(Request):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class ReviewHiddenReq(Request):
    is_hidden: bool


class RatingSummary(BaseModel):
    avg: Decimal | None
    count: int
