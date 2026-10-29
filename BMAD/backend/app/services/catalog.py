"""CatalogService：搜尋、空間詳細、篩選選項（FR-10～13）。"""

from __future__ import annotations

from datetime import time
from urllib.parse import quote

from sqlalchemy import Float, cast, exists, false, func, select

from ..errors import NotFoundError
from ..extensions import db
from ..models import (
    Booking,
    Branch,
    BranchStatus,
    Equipment,
    Review,
    Space,
    SpaceEquipment,
    SpacePhoto,
    SpaceStatus,
    SpaceType,
)
from ..policies.refund import CANCEL_POLICY_TEXT
from ..schemas.base import Page
from ..schemas.catalog import (
    BranchInfo,
    EquipmentItemDTO,
    FilterOptions,
    PhotoDTO,
    SpaceDetail,
    SpaceFilters,
    SpaceSummary,
)
from ..utils.clock import Clock
from ..utils.time import day_hour
from .availability import AvailabilityService

NEARBY_KM = 5
SORTS = {"price_asc", "price_desc", "capacity_asc", "capacity_desc", "distance"}


def _rating_subquery():
    """每個空間未隱藏評論的平均分與則數。"""
    return (
        select(
            Booking.space_id.label("space_id"),
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.review_id).label("review_count"),
        )
        .join(Review, Review.booking_id == Booking.booking_id)
        .where(Review.is_hidden.is_(False))
        .group_by(Booking.space_id)
        .subquery()
    )


def maps_url(branch: Branch) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote(
        f"{branch.city}{branch.district}{branch.address}"
    )


class CatalogService:
    def __init__(self, clock: Clock, availability: AvailabilityService) -> None:
        self.clock = clock
        self.availability = availability

    # ---- 搜尋 ----
    def search(self, f: SpaceFilters) -> Page[SpaceSummary]:
        now = self.clock.now()
        rating = _rating_subquery()
        columns = [Space, Branch, rating.c.avg_rating, rating.c.review_count]
        dist = None
        if f.lat is not None and f.lng is not None:
            lat1, lng1 = func.radians(f.lat), func.radians(f.lng)
            lat2 = func.radians(cast(Branch.latitude, Float))
            lng2 = func.radians(cast(Branch.longitude, Float))
            cos_angle = func.cos(lat1) * func.cos(lat2) * func.cos(lng2 - lng1) + func.sin(
                lat1
            ) * func.sin(lat2)
            dist = (6371.0 * func.acos(func.least(1.0, func.greatest(-1.0, cos_angle)))).label(
                "dist"
            )
            columns.append(dist)

        stmt = (
            select(*columns)
            .join(Branch, Branch.branch_id == Space.branch_id)
            .outerjoin(rating, rating.c.space_id == Space.space_id)
            .where(
                Space.status == SpaceStatus.AVAILABLE.value,
                Branch.status == BranchStatus.OPEN.value,
            )
        )
        if f.city:
            stmt = stmt.where(Branch.city == f.city)
        if f.district:
            stmt = stmt.where(Branch.district == f.district)
        if f.people:
            stmt = stmt.where(Space.capacity >= f.people)
        if f.min_price is not None:
            stmt = stmt.where(Space.hourly_price >= f.min_price)
        if f.max_price is not None:
            stmt = stmt.where(Space.hourly_price <= f.max_price)
        if f.type:
            stmt = stmt.where(Space.space_type == f.type)
        for equipment_id in f.equipment:  # 須全部具備
            stmt = stmt.where(
                exists().where(
                    SpaceEquipment.space_id == Space.space_id,
                    SpaceEquipment.equipment_id == equipment_id,
                )
            )
        if f.date and f.start is not None and f.end is not None and f.end > f.start:
            start_at, end_at = day_hour(f.date, f.start), day_hour(f.date, f.end)
            stmt = stmt.where(
                Branch.open_time <= time(f.start),
                Branch.close_time >= time(f.end) if f.end < 24 else false(),
                ~exists().where(
                    Booking.space_id == Space.space_id,
                    Booking.occupying(now),
                    Booking.start_at < end_at,
                    Booking.end_at > start_at,
                ),
            )
        if dist is not None:
            stmt = stmt.where(dist <= NEARBY_KM)

        total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order = {
            "price_asc": [Space.hourly_price.asc()],
            "price_desc": [Space.hourly_price.desc()],
            "capacity_asc": [Space.capacity.asc()],
            "capacity_desc": [Space.capacity.desc()],
        }.get(f.sort or "")
        if dist is not None and f.sort in (None, "distance"):
            order = [dist.asc()]
        stmt = stmt.order_by(*(order or [Space.space_id.desc()]), Space.space_id)
        rows = db.session.execute(stmt.limit(f.page_size).offset((f.page - 1) * f.page_size)).all()
        covers = self._covers([r[0].space_id for r in rows])
        items = [
            self._summary(
                r[0],
                r[1],
                covers.get(r[0].space_id),
                r[2],
                r[3],
                r[4] if dist is not None else None,
            )
            for r in rows
        ]
        return Page[SpaceSummary](items=items, page=f.page, page_size=f.page_size, total=total)

    def summaries(self, space_ids: list[int]) -> list[SpaceSummary]:
        """依給定順序回傳空間摘要（含已停用者，供收藏清單顯示「已下架」）。"""
        if not space_ids:
            return []
        rating = _rating_subquery()
        rows = db.session.execute(
            select(Space, Branch, rating.c.avg_rating, rating.c.review_count)
            .join(Branch, Branch.branch_id == Space.branch_id)
            .outerjoin(rating, rating.c.space_id == Space.space_id)
            .where(Space.space_id.in_(space_ids))
        ).all()
        covers = self._covers(space_ids)
        by_id = {
            r[0].space_id: self._summary(r[0], r[1], covers.get(r[0].space_id), r[2], r[3], None)
            for r in rows
        }
        return [by_id[i] for i in space_ids if i in by_id]

    def _covers(self, space_ids: list[int]) -> dict[int, str]:
        if not space_ids:
            return {}
        covers: dict[int, str] = {}
        for sid, url in db.session.execute(
            select(SpacePhoto.space_id, SpacePhoto.image_url)
            .where(SpacePhoto.space_id.in_(space_ids))
            .order_by(SpacePhoto.space_id, SpacePhoto.sort_order, SpacePhoto.photo_id)
        ).all():
            covers.setdefault(sid, url)
        return covers

    @staticmethod
    def _summary(space, branch, cover, avg, count, dist) -> SpaceSummary:
        return SpaceSummary(
            space_id=space.space_id,
            name=space.name,
            branch_name=branch.name,
            city=branch.city,
            district=branch.district,
            space_type=space.space_type,
            capacity=space.capacity,
            hourly_price=space.hourly_price,
            status=space.status if branch.is_open() else SpaceStatus.DISABLED.value,
            cover_url=cover,
            avg_rating=round(float(avg), 1) if avg is not None else None,
            review_count=count or 0,
            distance_km=round(float(dist), 1) if dist is not None else None,
        )

    # ---- 詳細 ----
    def get_space(self, space_id: int) -> SpaceDetail:
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        branch = space.branch
        avg, count = db.session.execute(
            select(func.avg(Review.rating), func.count(Review.review_id))
            .join(Booking, Booking.booking_id == Review.booking_id)
            .where(Booking.space_id == space_id, Review.is_hidden.is_(False))
        ).one()
        return SpaceDetail(
            space_id=space.space_id,
            name=space.name,
            space_type=space.space_type,
            capacity=space.capacity,
            area=float(space.area) if space.area is not None else None,
            hourly_price=space.hourly_price,
            description=space.description,
            rules=space.rules,
            entry_guide=space.entry_guide,
            status=space.status,
            bookable=space.is_bookable(),
            cancel_policy=CANCEL_POLICY_TEXT,
            branch=BranchInfo(
                branch_id=branch.branch_id,
                name=branch.name,
                city=branch.city,
                district=branch.district,
                address=branch.address,
                phone=branch.phone,
                latitude=float(branch.latitude),
                longitude=float(branch.longitude),
                open_hour=branch.open_time.hour,
                close_hour=branch.close_time.hour,
                maps_url=maps_url(branch),
            ),
            photos=[PhotoDTO.model_validate(p) for p in space.photos],
            equipment=[
                EquipmentItemDTO(
                    equipment_id=item.equipment_id,
                    name=item.equipment.name,
                    category=item.equipment.category,
                    quantity=item.quantity,
                    note=item.note,
                )
                for item in space.equipment_items
            ],
            avg_rating=round(float(avg), 1) if avg is not None else None,
            review_count=count or 0,
        )

    def filter_options(self) -> FilterOptions:
        cities: dict[str, list[str]] = {}
        for city, district in db.session.execute(
            select(Branch.city, Branch.district)
            .where(Branch.status == BranchStatus.OPEN.value)
            .distinct()
            .order_by(Branch.city, Branch.district)
        ).all():
            cities.setdefault(city, []).append(district)
        equipment = [
            {"equipment_id": e.equipment_id, "name": e.name, "category": e.category}
            for e in db.session.execute(
                select(Equipment).where(Equipment.is_active.is_(True)).order_by(Equipment.name)
            ).scalars()
        ]
        return FilterOptions(
            cities=cities, space_types=[t.value for t in SpaceType], equipment=equipment
        )
