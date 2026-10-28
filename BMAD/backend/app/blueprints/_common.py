"""Blueprint 共用工具：請求解析（Pydantic）、取得 Service、轉換回應。"""

from __future__ import annotations

from typing import Any, TypeVar

from flask import current_app, jsonify, request
from flask_login import current_user
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ..errors import ValidationError
from ..schemas.account import UserDTO
from ..services import Services

M = TypeVar("M", bound=BaseModel)


def svc() -> Services:
    return current_app.extensions["services"]


def me() -> UserDTO:
    return current_user.dto


def _fail(exc: PydanticValidationError):
    fields = {".".join(str(p) for p in e["loc"]) or "body": e["msg"] for e in exc.errors()}
    raise ValidationError("VALIDATION_ERROR", details={"fields": fields}) from exc


def parse_body(model: type[M]) -> M:
    payload = request.get_json(silent=True)
    if payload is not None and not isinstance(payload, dict):
        raise ValidationError("VALIDATION_ERROR")
    try:
        return model.model_validate(payload or {})
    except PydanticValidationError as exc:
        _fail(exc)


def parse_query(model: type[M], list_fields: tuple[str, ...] = ()) -> M:
    data: dict[str, Any] = {}
    for key in request.args:
        if key in list_fields:
            values = [v for raw in request.args.getlist(key) for v in raw.split(",") if v]
            data[key] = values
        elif request.args[key] != "":
            data[key] = request.args[key]
    try:
        return model.model_validate(data)
    except PydanticValidationError as exc:
        _fail(exc)


def dump(obj: Any):
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [dump(o) for o in obj]
    return obj


def ok(obj: Any = None, status: int = 200, **extra):
    body = dump(obj) if obj is not None else {}
    if extra:
        body = {**body, **extra} if isinstance(body, dict) else {"data": body, **extra}
    return jsonify(body), status


def idempotency_key(required: bool = True) -> str | None:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key and required:
        raise ValidationError("VALIDATION_ERROR", "缺少 Idempotency-Key 標頭")
    if len(key) > 64:
        raise ValidationError("VALIDATION_ERROR", "Idempotency-Key 過長")
    return key or None
