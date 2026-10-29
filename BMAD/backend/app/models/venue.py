"""branches、spaces、space_photos、equipment、space_equipment（D2-1）。"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..utils.time import combine_local
from .columns import BigId
from .enums import BranchStatus, SpaceStatus


class Branch(db.Model):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint("close_time > open_time", name="ck_branches_hours"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_branches_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_branches_lng"),
        CheckConstraint(
            "extract(minute FROM open_time) = 0 AND extract(second FROM open_time) = 0",
            name="ck_branches_open_hour",
        ),
        CheckConstraint(
            "extract(minute FROM close_time) = 0 AND extract(second FROM close_time) = 0",
            name="ck_branches_close_hour",
        ),
        CheckConstraint("status IN ('OPEN','DISABLED')", name="ck_branches_status"),
        Index("ix_branches_area", "city", "district"),
    )

    branch_id: Mapped[BigId] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    city: Mapped[str] = mapped_column(String(20))
    district: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    latitude: Mapped[Decimal] = mapped_column(db.Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(db.Numeric(9, 6))
    open_time: Mapped[time] = mapped_column(db.Time)
    close_time: Mapped[time] = mapped_column(db.Time)
    status: Mapped[str] = mapped_column(
        String(10), default=BranchStatus.OPEN.value, server_default="OPEN"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    spaces: Mapped[list[Space]] = relationship(back_populates="branch")

    def is_open(self) -> bool:
        return self.status == BranchStatus.OPEN

    def opening_range(self, local_day: date) -> tuple[datetime, datetime]:
        """該日營業起訖時間（UTC 時間點）。"""
        return combine_local(local_day, self.open_time), combine_local(local_day, self.close_time)


class Space(db.Model):
    __tablename__ = "spaces"
    __table_args__ = (
        CheckConstraint(
            "space_type IN ('MEETING','CLASSROOM','PARTY','STUDIO','MULTI')",
            name="ck_spaces_type",
        ),
        CheckConstraint("capacity > 0", name="ck_spaces_capacity"),
        CheckConstraint("area > 0", name="ck_spaces_area"),
        CheckConstraint("hourly_price > 0", name="ck_spaces_price"),
        CheckConstraint(
            "status IN ('AVAILABLE','MAINTENANCE','DISABLED')", name="ck_spaces_status"
        ),
        db.UniqueConstraint("branch_id", "name", name="uq_spaces_branch_name"),
    )

    space_id: Mapped[BigId] = mapped_column(primary_key=True)
    branch_id: Mapped[BigId] = mapped_column(db.ForeignKey("branches.branch_id"))
    name: Mapped[str] = mapped_column(String(50))
    space_type: Mapped[str] = mapped_column(String(10))
    capacity: Mapped[int]
    area: Mapped[Decimal | None] = mapped_column(db.Numeric(5, 1))
    hourly_price: Mapped[int]
    description: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[str | None] = mapped_column(Text)
    entry_guide: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(12), default=SpaceStatus.AVAILABLE.value, server_default="AVAILABLE"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    branch: Mapped[Branch] = relationship(back_populates="spaces")
    photos: Mapped[list[SpacePhoto]] = relationship(
        back_populates="space",
        order_by="SpacePhoto.sort_order",
        cascade="all, delete-orphan",
    )
    equipment_items: Mapped[list[SpaceEquipment]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )

    def is_bookable(self) -> bool:
        """BR-04：空間 AVAILABLE 且場館 OPEN。"""
        return self.status == SpaceStatus.AVAILABLE and self.branch.is_open()

    def cover_photo(self) -> SpacePhoto | None:
        return self.photos[0] if self.photos else None


class SpacePhoto(db.Model):
    __tablename__ = "space_photos"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="ck_space_photos_order"),
        Index("ix_space_photos_space", "space_id", "sort_order"),
    )

    photo_id: Mapped[BigId] = mapped_column(primary_key=True)
    space_id: Mapped[BigId] = mapped_column(db.ForeignKey("spaces.space_id", ondelete="CASCADE"))
    image_url: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    space: Mapped[Space] = relationship(back_populates="photos")


class Equipment(db.Model):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint(
            "category IN ('AV','FURNITURE','KITCHEN','NETWORK','OTHER')",
            name="ck_equipment_category",
        ),
    )

    equipment_id: Mapped[BigId] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    category: Mapped[str] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpaceEquipment(db.Model):
    __tablename__ = "space_equipment"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_space_equipment_qty"),)

    space_id: Mapped[BigId] = mapped_column(
        db.ForeignKey("spaces.space_id", ondelete="CASCADE"), primary_key=True
    )
    equipment_id: Mapped[BigId] = mapped_column(
        db.ForeignKey("equipment.equipment_id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    note: Mapped[str | None] = mapped_column(String(100))

    space: Mapped[Space] = relationship(back_populates="equipment_items")
    equipment: Mapped[Equipment] = relationship()
