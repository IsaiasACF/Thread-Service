"""Esquemas de los errores existentes, incluidos los de validación de FastAPI."""
from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


class ValidationIssue(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    input: Any = None
    ctx: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationIssue]
