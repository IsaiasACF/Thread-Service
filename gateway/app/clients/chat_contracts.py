"""REST DTOs for A's domains only; no dependency on Thread Service's Python app."""
from datetime import datetime, timezone
from typing import Annotated, TypeVar
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from ..graphql.errors import ErrorCode, GatewayError

Identifier = Annotated[str, Field(min_length=1)]
Name = Annotated[str, Field(min_length=1, max_length=80)]
Content = Annotated[str, Field(min_length=1, max_length=4000)]
T = TypeVar("T", bound=BaseModel)


class RestDTO(BaseModel):
    # Upstreams may add fields. Required fields never coerce numbers/null into strings.
    model_config = ConfigDict(strict=True, extra="ignore")


class UserCreate(RestDTO):
    display_name: Name


class UserDTO(UserCreate):
    id: Identifier


class ChannelCreate(RestDTO):
    name: Name


class ChannelDTO(ChannelCreate):
    id: Identifier


class MessageCreate(RestDTO):
    author_id: str
    content: Content


class ReplyCreate(MessageCreate):
    author_id: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("author_id", "content", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class MessageDTO(RestDTO):
    id: Identifier
    channel_id: Identifier
    author_id: Identifier
    content: Content
    created_at: str

    @field_validator("created_at")
    @classmethod
    def utc_timestamp(cls, value):
        if "T" not in value:
            raise ValueError("Expected an ISO 8601 timestamp")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Expected a timezone-aware timestamp")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ReplyDTO(MessageDTO):
    message_id: Identifier
    author_id: Annotated[str, Field(min_length=1, max_length=128)]


def encode_id(value: str, service: str) -> str:
    if not isinstance(value, str) or not value:
        raise GatewayError("Identificador inválido.", ErrorCode.VALIDATION_ERROR,
                           service=service)
    segment = quote(value, safe="")
    # quote leaves dots unescaped; do not allow URL normalization to change the path.
    return segment.replace(".", "%2E") if segment in {".", ".."} else segment


def input_dto(model: type[T], service: str, **data) -> T:
    try:
        return model.model_validate(data)
    except ValidationError:
        raise GatewayError("Entrada inválida.", ErrorCode.VALIDATION_ERROR,
                           service=service) from None


def response_dto(client, model: type[T], data, **expected) -> T:
    try:
        dto = model.model_validate(data)
    except ValidationError:
        raise client.bad_response() from None
    if any(getattr(dto, key) != value for key, value in expected.items()):
        raise client.bad_response()
    return dto


def response_list(client, model: type[T], data, **expected) -> list[T]:
    try:
        dtos = TypeAdapter(list[model]).validate_python(data, strict=True)
    except ValidationError:
        raise client.bad_response() from None
    if any(getattr(dto, key) != value for dto in dtos for key, value in expected.items()):
        raise client.bad_response()
    return dtos
