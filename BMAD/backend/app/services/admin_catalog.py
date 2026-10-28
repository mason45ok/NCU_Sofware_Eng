"""AdminCatalogService：場館、空間、照片、設備的後台維護（FR-40～43）。"""

from __future__ import annotations

import os
import uuid
from datetime import time

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from ..errors import NotFoundError, ValidationError
from ..extensions import db
from ..models import (
    Branch,
    BranchStatus,
    Equipment,
    EquipmentCategory,
    Space,
    SpaceEquipment,
    SpacePhoto,
    SpaceStatus,
    SpaceType,
)
from ..schemas.admin import (
    AdminSpaceDTO,
    AffectedResult,
    BranchDTO,
    BranchReq,
    EquipmentDTO,
    EquipmentPatchReq,
    EquipmentReq,
    SpaceEquipmentItem,
    SpaceReq,
)
from ..schemas.catalog import PhotoDTO
from .booking import BookingService

MAX_PHOTO_BYTES = 5 * 1024 * 1024
_SIGNATURES = {
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"],
}


def _enum_value(enum_cls, value: str, field: str) -> str:
    if value not in {e.value for e in enum_cls}:
        raise ValidationError("VALIDATION_ERROR", details={field: "選項不正確"})
    return value


class AdminCatalogService:
    def __init__(self, bookings: BookingService) -> None:
        self.bookings = bookings

    # ---- 場館 ----
    @staticmethod
    def _branch_dto(branch: Branch) -> BranchDTO:
        return BranchDTO(
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
            status=branch.status,
            space_count=len(branch.spaces),
        )

    def list_branches(self) -> list[BranchDTO]:
        rows = db.session.execute(select(Branch).order_by(Branch.branch_id)).scalars()
        return [self._branch_dto(b) for b in rows]

    def save_branch(self, branch_id: int | None, data: BranchReq) -> BranchDTO:
        """新增（branch_id 為 None）或修改場館。"""
        if data.close_hour <= data.open_hour:
            raise ValidationError(
                "VALIDATION_ERROR",
                details={"close_hour": "結束營業時間須晚於開始營業時間"},
            )
        branch = db.session.get(Branch, branch_id) if branch_id else Branch()
        if branch is None:
            raise NotFoundError()
        for field in (
            "name",
            "city",
            "district",
            "address",
            "phone",
            "latitude",
            "longitude",
        ):
            setattr(branch, field, getattr(data, field))
        branch.open_time, branch.close_time = (
            time(data.open_hour),
            time(data.close_hour),
        )
        db.session.add(branch)
        db.session.commit()
        return self._branch_dto(branch)

    def set_branch_status(self, branch_id: int, status: str) -> AffectedResult:
        """停用時回傳受影響的未來訂單（BR-18）；不會自動取消。"""
        branch = db.session.get(Branch, branch_id)
        if branch is None:
            raise NotFoundError()
        branch.status = _enum_value(BranchStatus, status, "status")
        db.session.commit()
        affected = (
            self.bookings.list_affected([s.space_id for s in branch.spaces])
            if status == BranchStatus.DISABLED
            else []
        )
        return AffectedResult(affected_bookings=affected)

    # ---- 空間 ----
    @staticmethod
    def _space_dto(space: Space) -> AdminSpaceDTO:
        return AdminSpaceDTO(
            space_id=space.space_id,
            branch_id=space.branch_id,
            branch_name=space.branch.name,
            name=space.name,
            space_type=space.space_type,
            capacity=space.capacity,
            area=float(space.area) if space.area is not None else None,
            hourly_price=space.hourly_price,
            description=space.description,
            rules=space.rules,
            entry_guide=space.entry_guide,
            status=space.status,
        )

    def list_spaces(self) -> list[AdminSpaceDTO]:
        rows = db.session.execute(select(Space).order_by(Space.space_id)).scalars()
        return [self._space_dto(s) for s in rows]

    def get_space(self, space_id: int) -> AdminSpaceDTO:
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        return self._space_dto(space)

    def save_space(self, space_id: int | None, data: SpaceReq) -> AdminSpaceDTO:
        """修改時租只影響之後的新訂單，既有訂單使用下訂當下的快照（BR-07）。"""
        _enum_value(SpaceType, data.space_type, "space_type")
        if db.session.get(Branch, data.branch_id) is None:
            raise ValidationError("VALIDATION_ERROR", details={"branch_id": "場館不存在"})
        space = db.session.get(Space, space_id) if space_id else Space()
        if space is None:
            raise NotFoundError()
        for field in (
            "branch_id",
            "name",
            "space_type",
            "capacity",
            "area",
            "hourly_price",
            "description",
            "rules",
            "entry_guide",
        ):
            setattr(space, field, getattr(data, field))
        db.session.add(space)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValidationError(
                "VALIDATION_ERROR", details={"name": "同一場館已有相同名稱的空間"}
            ) from None
        return self._space_dto(space)

    def set_space_status(self, space_id: int, status: str) -> AffectedResult:
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        space.status = _enum_value(SpaceStatus, status, "status")
        db.session.commit()
        affected = (
            self.bookings.list_affected([space_id]) if status != SpaceStatus.AVAILABLE else []
        )
        return AffectedResult(affected_bookings=affected)

    # ---- 照片 ----
    def list_photos(self, space_id: int) -> list[PhotoDTO]:
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        return [PhotoDTO.model_validate(p) for p in space.photos]

    def upload_photo(self, space_id: int, file: FileStorage | None) -> PhotoDTO:
        """FR-42：jpg、png、webp，單檔 ≤ 5 MB；檢查副檔名與檔案標頭，以 UUID 重新命名。"""
        if db.session.get(Space, space_id) is None:
            raise NotFoundError()
        if file is None or not file.filename:
            raise ValidationError("INVALID_UPLOAD")
        ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
        data = file.read(MAX_PHOTO_BYTES + 1)
        if ext not in _SIGNATURES or len(data) > MAX_PHOTO_BYTES or not data:
            raise ValidationError("INVALID_UPLOAD")
        if not any(data.startswith(sig) for sig in _SIGNATURES[ext]) or (
            ext == "webp" and data[8:12] != b"WEBP"
        ):
            raise ValidationError("INVALID_UPLOAD")
        name = f"{uuid.uuid4().hex}.{'jpg' if ext == 'jpeg' else ext}"
        folder = os.path.join(current_app.config["UPLOAD_DIR"], "spaces", str(space_id))
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "wb") as fh:
            fh.write(data)
        next_order = db.session.scalar(
            select(func.coalesce(func.max(SpacePhoto.sort_order) + 1, 0)).where(
                SpacePhoto.space_id == space_id
            )
        )
        photo = SpacePhoto(
            space_id=space_id,
            image_url=f"/uploads/spaces/{space_id}/{name}",
            sort_order=next_order,
        )
        db.session.add(photo)
        db.session.commit()
        return PhotoDTO.model_validate(photo)

    def update_photo(self, photo_id: int, caption: str | None) -> PhotoDTO:
        photo = db.session.get(SpacePhoto, photo_id)
        if photo is None:
            raise NotFoundError()
        photo.caption = caption or None
        db.session.commit()
        return PhotoDTO.model_validate(photo)

    def delete_photo(self, photo_id: int) -> None:
        photo = db.session.get(SpacePhoto, photo_id)
        if photo is None:
            raise NotFoundError()
        path = os.path.join(
            current_app.config["UPLOAD_DIR"], photo.image_url.removeprefix("/uploads/")
        )
        db.session.delete(photo)
        db.session.commit()
        if os.path.isfile(path):
            os.remove(path)

    def reorder_photos(self, space_id: int, photo_ids: list[int]) -> list[PhotoDTO]:
        """依給定順序重新排序，第一張為封面（sort_order = 0）。"""
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        by_id = {p.photo_id: p for p in space.photos}
        if set(photo_ids) != set(by_id) or len(photo_ids) != len(by_id):
            raise ValidationError("VALIDATION_ERROR", details={"photo_ids": "須包含此空間全部照片"})
        for index, pid in enumerate(photo_ids):
            by_id[pid].sort_order = index
        db.session.commit()
        return self.list_photos(space_id)

    # ---- 設備 ----
    def list_equipment(self) -> list[EquipmentDTO]:
        rows = db.session.execute(select(Equipment).order_by(Equipment.equipment_id)).scalars()
        return [EquipmentDTO.model_validate(e) for e in rows]

    def create_equipment(self, data: EquipmentReq) -> EquipmentDTO:
        _enum_value(EquipmentCategory, data.category, "category")
        equipment = Equipment(name=data.name, category=data.category, is_active=data.is_active)
        db.session.add(equipment)
        return self._commit_equipment(equipment)

    def update_equipment(self, equipment_id: int, data: EquipmentPatchReq) -> EquipmentDTO:
        equipment = db.session.get(Equipment, equipment_id)
        if equipment is None:
            raise NotFoundError()
        if data.category is not None:
            equipment.category = _enum_value(EquipmentCategory, data.category, "category")
        if data.name is not None:
            equipment.name = data.name
        if data.is_active is not None:
            equipment.is_active = data.is_active
        return self._commit_equipment(equipment)

    @staticmethod
    def _commit_equipment(equipment: Equipment) -> EquipmentDTO:
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValidationError(
                "VALIDATION_ERROR", details={"name": "已有相同名稱的設備"}
            ) from None
        return EquipmentDTO.model_validate(equipment)

    def set_space_equipment(self, space_id: int, items: list[SpaceEquipmentItem]) -> None:
        """整批設定空間設備；已停用的設備不可新加入。"""
        space = db.session.get(Space, space_id)
        if space is None:
            raise NotFoundError()
        ids = [i.equipment_id for i in items]
        if len(set(ids)) != len(ids):
            raise ValidationError("VALIDATION_ERROR", details={"items": "設備不可重複"})
        valid = {
            e.equipment_id: e
            for e in db.session.execute(
                select(Equipment).where(Equipment.equipment_id.in_(ids))
            ).scalars()
        }
        current = {i.equipment_id for i in space.equipment_items}
        for item in items:
            eq = valid.get(item.equipment_id)
            if eq is None or (not eq.is_active and item.equipment_id not in current):
                raise ValidationError(
                    "VALIDATION_ERROR",
                    details={"items": f"設備 {item.equipment_id} 不可使用"},
                )
        space.equipment_items.clear()
        db.session.flush()
        for item in items:
            space.equipment_items.append(
                SpaceEquipment(
                    equipment_id=item.equipment_id,
                    quantity=item.quantity,
                    note=item.note,
                )
            )
        db.session.commit()
