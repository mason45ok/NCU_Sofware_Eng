"""搜尋、收藏、後台場館／空間／照片／設備（FR-10～15、40～43）。使用實際 PostgreSQL。"""

from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.errors import AppError
from app.extensions import db
from app.models import Space
from app.schemas.admin import BranchReq, EquipmentReq, SpaceEquipmentItem, SpaceReq
from app.schemas.catalog import SpaceFilters
from app.utils.time import local_date
from tests.conftest import NOW
from tests.helpers import booked, error_code, req

pytestmark = pytest.mark.usefixtures("db_clean")

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def search(services, **kw):
    return services.catalog.search(SpaceFilters(**kw))


def test_fr10_filters_people_price_type_and_hide_unavailable(services, make_space):
    small = make_space("小", capacity=4, price=200)
    big = make_space("大", capacity=20, price=900)
    hidden = make_space("維修", capacity=20, price=900)
    db.session.get(Space, hidden).status = "MAINTENANCE"
    db.session.commit()
    assert {s.space_id for s in search(services).items} == {small, big}  # 只顯示 AVAILABLE
    assert {s.space_id for s in search(services, people=10).items} == {big}
    assert {s.space_id for s in search(services, max_price=300).items} == {small}
    assert {s.space_id for s in search(services, min_price=500).items} == {big}
    assert search(services, type="PARTY").total == 0


def test_fr10_equipment_must_have_all(services, make_space, make_equipment):
    a, b = make_space("A"), make_space("B")
    projector, board = make_equipment("投影機"), make_equipment("白板", "FURNITURE")
    for space, items in ((a, [projector, board]), (b, [projector])):
        services.admin_catalog.set_space_equipment(
            space, [SpaceEquipmentItem(equipment_id=i) for i in items]
        )
    assert {s.space_id for s in search(services, equipment=[projector]).items} == {a, b}
    assert {s.space_id for s in search(services, equipment=[projector, board]).items} == {a}


def test_fr10_date_time_filter_excludes_booked_spaces(services, make_user, make_space):
    free, busy = make_space("空"), make_space("忙")
    booked(services, make_user(), busy, 2, 10, 12)
    day = local_date(NOW).replace(day=4)
    assert {s.space_id for s in search(services, date=day, start=10, end=12).items} == {free}
    assert {s.space_id for s in search(services, date=day, start=12, end=14).items} == {free, busy}


def test_fr11_nearby_sorted_by_distance_within_5km(services, make_space):
    near = make_space("近")
    far = make_space("遠")
    db.session.get(Space, far).branch.latitude = 25.05  # 約 12 公里外
    db.session.commit()
    result = search(services, lat=24.9677, lng=121.1916)
    assert [s.space_id for s in result.items] == [near]
    assert result.items[0].distance_km is not None and result.items[0].distance_km < 1


def test_fr12_sorting_and_pagination(services, make_space):
    ids = [make_space(f"S{i}", price=100 * (i + 1), capacity=5 * (i + 1)) for i in range(3)]
    assert [s.space_id for s in search(services, sort="price_desc").items] == ids[::-1]
    assert [s.space_id for s in search(services, sort="capacity_asc").items] == ids
    page = search(services, page_size=2, page=2)
    assert (page.total, len(page.items)) == (3, 1)


def test_fr13_space_detail_has_cancel_policy_and_maps_link(services, space_id):
    detail = services.catalog.get_space(space_id)
    assert detail.bookable and detail.cancel_policy
    assert detail.branch.maps_url.startswith("https://www.google.com/maps/")
    assert error_code(services.catalog.get_space, 9999) == "NOT_FOUND"


def test_fr15_favorites_idempotent_and_list_shows_disabled(services, make_user, space_id):
    user = make_user()
    services.favorites.add(user, space_id)
    services.favorites.add(user, space_id)  # 冪等
    assert [s.space_id for s in services.favorites.list(user)] == [space_id]
    db.session.get(Space, space_id).status = "DISABLED"
    db.session.commit()
    assert services.favorites.list(user)[0].status == "DISABLED"  # 前端顯示「已下架」
    services.favorites.remove(user, space_id)
    services.favorites.remove(user, space_id)
    assert services.favorites.list(user) == []
    assert error_code(services.favorites.add, user, 9999) == "NOT_FOUND"


def branch_req(**kw):
    data = dict(
        name="新館",
        city="台北市",
        district="信義區",
        address="松仁路 1 號",
        phone="02-1",
        latitude=25.03,
        longitude=121.56,
        open_hour=9,
        close_hour=21,
    )
    return BranchReq(**{**data, **kw})


def test_fr40_branch_crud_and_disable_lists_affected_bookings(services, make_user, space_id):
    created = services.admin_catalog.save_branch(None, branch_req())
    assert (created.open_hour, created.close_hour) == (9, 21)
    updated = services.admin_catalog.save_branch(created.branch_id, branch_req(name="改名"))
    assert updated.name == "改名"
    assert (
        error_code(
            services.admin_catalog.save_branch, None, branch_req(open_hour=10, close_hour=10)
        )
        == "VALIDATION_ERROR"
    )

    user = make_user()
    dto = booked(services, user, space_id, 2, 10, 12)
    branch_id = db.session.get(Space, space_id).branch_id
    result = services.admin_catalog.set_branch_status(branch_id, "DISABLED")
    assert [b.booking_id for b in result.affected_bookings] == [dto.booking_id]
    assert search(services).total == 0  # 場館停用後搜尋不到
    assert services.admin_catalog.set_branch_status(branch_id, "OPEN").affected_bookings == []
    assert (
        error_code(services.admin_catalog.set_branch_status, branch_id, "BAD") == "VALIDATION_ERROR"
    )


def test_fr41_space_save_validates_and_price_change_keeps_snapshot(services, make_user, space_id):
    branch_id = db.session.get(Space, space_id).branch_id
    data = SpaceReq(
        branch_id=branch_id, name="新空間", space_type="PARTY", capacity=8, hourly_price=500
    )
    created = services.admin_catalog.save_space(None, data)
    assert created.status == "AVAILABLE"
    assert (
        error_code(services.admin_catalog.save_space, None, data) == "VALIDATION_ERROR"
    )  # 同館重名
    bad_type = SpaceReq(branch_id=branch_id, name="X", space_type="BAD", capacity=1, hourly_price=1)
    assert error_code(services.admin_catalog.save_space, None, bad_type) == "VALIDATION_ERROR"

    user = make_user()
    dto = services.bookings.create(user, req(space_id))
    changed = SpaceReq(
        branch_id=branch_id, name="201 會議室", space_type="MEETING", capacity=10, hourly_price=777
    )
    services.admin_catalog.save_space(space_id, changed)
    assert services.bookings.get_for_owner(user, dto.booking_id).hourly_price_snapshot == 300


def test_fr42_photo_upload_validation_order_and_delete(services, space_id):
    def upload(name, data):
        return services.admin_catalog.upload_photo(
            space_id, FileStorage(BytesIO(data), filename=name)
        )

    first, second = upload("a.png", PNG), upload("b.PNG", PNG)
    assert (first.sort_order, second.sort_order) == (0, 1)
    assert (
        first.image_url.startswith(f"/uploads/spaces/{space_id}/")
        and "a.png" not in first.image_url
    )
    for bad_name, data in (
        ("x.gif", PNG),
        ("x.png", b"not an image"),
        ("x.png", PNG + b"0" * (5 * 1024 * 1024)),
        ("x.exe", PNG),
    ):
        assert error_code(upload, bad_name, data) == "INVALID_UPLOAD"
    ordered = services.admin_catalog.reorder_photos(space_id, [second.photo_id, first.photo_id])
    assert [p.photo_id for p in ordered] == [second.photo_id, first.photo_id]  # 第一張為封面
    assert (
        error_code(services.admin_catalog.reorder_photos, space_id, [first.photo_id])
        == "VALIDATION_ERROR"
    )
    services.admin_catalog.delete_photo(first.photo_id)
    assert len(services.admin_catalog.list_photos(space_id)) == 1


def test_fr43_equipment_management(services, space_id, make_equipment):
    created = services.admin_catalog.create_equipment(EquipmentReq(name="新設備", category="AV"))
    assert (
        error_code(
            services.admin_catalog.create_equipment, EquipmentReq(name="新設備", category="AV")
        )
        == "VALIDATION_ERROR"
    )
    assert (
        error_code(services.admin_catalog.create_equipment, EquipmentReq(name="Y", category="BAD"))
        == "VALIDATION_ERROR"
    )
    services.admin_catalog.set_space_equipment(
        space_id, [SpaceEquipmentItem(equipment_id=created.equipment_id, quantity=2, note="75 吋")]
    )
    item = services.catalog.get_space(space_id).equipment[0]
    assert (item.name, item.quantity, item.note) == ("新設備", 2, "75 吋")
    from app.schemas.admin import EquipmentPatchReq

    services.admin_catalog.update_equipment(
        created.equipment_id, EquipmentPatchReq(is_active=False)
    )
    assert services.catalog.filter_options().equipment == []  # 停用後不出現在篩選
    other = make_equipment("另一個")
    services.admin_catalog.update_equipment(other, EquipmentPatchReq(is_active=False))
    with pytest.raises(AppError):
        services.admin_catalog.set_space_equipment(
            space_id, [SpaceEquipmentItem(equipment_id=other)]
        )


def test_fr44_admin_booking_search_and_detail(services, make_user, space_id):
    from app.schemas.admin import BookingFilters

    a, b = make_user("a@test.local"), make_user("b@test.local")
    first = booked(services, a, space_id, 2, 10, 12)
    services.bookings.create(b, req(space_id, 3, 10, 12))
    assert services.admin_bookings.search(BookingFilters()).total == 2
    assert services.admin_bookings.search(BookingFilters(email="a@test")).total == 1
    assert services.admin_bookings.search(BookingFilters(no=first.booking_no)).total == 1
    assert services.admin_bookings.search(BookingFilters(status="PENDING_PAYMENT")).total == 1
    assert (
        services.admin_bookings.search(
            BookingFilters(
                **{"from": local_date(NOW).replace(day=4), "to": local_date(NOW).replace(day=4)}
            )
        ).total
        == 1
    )
    detail = services.admin_bookings.detail(first.booking_id)
    assert [x.action for x in detail.logs] == ["CREATE", "PAY"] and len(detail.notifications) == 1
    assert error_code(services.admin_bookings.detail, 9999) == "NOT_FOUND"
    summary = services.admin_bookings.summary()
    assert summary.failed_notifications == 0 and summary.pending_affected_bookings == 0
