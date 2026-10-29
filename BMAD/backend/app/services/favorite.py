"""FavoriteService：收藏（FR-15）。清單經由 CatalogService 組出空間摘要。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from ..errors import NotFoundError
from ..extensions import db
from ..models import Space, UserFavorite
from ..schemas.account import UserDTO
from ..schemas.catalog import SpaceSummary
from .catalog import CatalogService


class FavoriteService:
    def __init__(self, catalog: CatalogService) -> None:
        self.catalog = catalog

    def add(self, user: UserDTO, space_id: int) -> None:
        """冪等：重複收藏不報錯。"""
        if db.session.get(Space, space_id) is None:
            raise NotFoundError()
        db.session.execute(
            insert(UserFavorite)
            .values(user_id=user.user_id, space_id=space_id)
            .on_conflict_do_nothing()
        )
        db.session.commit()

    def remove(self, user: UserDTO, space_id: int) -> None:
        db.session.execute(
            delete(UserFavorite).where(
                UserFavorite.user_id == user.user_id, UserFavorite.space_id == space_id
            )
        )
        db.session.commit()

    def list(self, user: UserDTO) -> list[SpaceSummary]:
        """依收藏時間（新到舊）排序；已停用的空間仍列出，由前端顯示「已下架」。"""
        ids = list(
            db.session.execute(
                select(UserFavorite.space_id)
                .where(UserFavorite.user_id == user.user_id)
                .order_by(UserFavorite.created_at.desc())
            ).scalars()
        )
        return self.catalog.summaries(ids)
