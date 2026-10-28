"""共用 DTO 基礎：時間序列化為 Asia/Taipei 的 ISO 8601（含時區）、分頁。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    PlainSerializer,
    StringConstraints,
)

from ..utils.time import to_taipei

# 輸出：一律轉台北時間的 ISO 8601（2026-11-20T14:00:00+08:00）
TPDatetime = Annotated[
    datetime, PlainSerializer(lambda d: to_taipei(d).isoformat(), return_type=str)
]
# 輸入：必須含時區
InDatetime = AwareDatetime

Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]

T = TypeVar("T")


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class Request(BaseModel):
    """請求模型：拒絕多餘欄位以免誤用。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page(DTO, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
