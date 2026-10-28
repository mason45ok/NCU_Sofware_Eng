"""catalog_bp：公開目錄（搜尋、空間詳細、可預約時段、評論）。"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, request

from ..errors import ValidationError
from ..schemas.catalog import SpaceFilters
from ._common import ok, parse_query, svc

bp = Blueprint("catalog", __name__, url_prefix="/api/v1")


@bp.get("/catalog/filters")
def filters():
    return ok(svc().catalog.filter_options())


@bp.get("/spaces")
def search_spaces():
    f = parse_query(SpaceFilters, list_fields=("equipment",))
    return ok(svc().catalog.search(f))


@bp.get("/spaces/<int:space_id>")
def space_detail(space_id: int):
    return ok(svc().catalog.get_space(space_id))


@bp.get("/spaces/<int:space_id>/availability")
def space_availability(space_id: int):
    try:
        day = date.fromisoformat(request.args.get("date", ""))
    except ValueError:
        raise ValidationError("VALIDATION_ERROR", details={"date": "格式須為 YYYY-MM-DD"}) from None
    return ok(svc().availability.availability(space_id, day))


@bp.get("/spaces/<int:space_id>/reviews")
def space_reviews(space_id: int):
    page = svc().reviews.list_for_space(
        space_id,
        int(request.args.get("page", 1)),
        int(request.args.get("page_size", 10)),
    )
    return ok(page)
