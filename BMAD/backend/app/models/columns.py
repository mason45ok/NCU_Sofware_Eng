"""共用欄位型別：主鍵與外鍵使用 BIGINT（SCHEMA.md 共用約定）。"""

from typing import Annotated

from sqlalchemy import BigInteger
from sqlalchemy.orm import mapped_column

BigId = Annotated[int, mapped_column(BigInteger)]
