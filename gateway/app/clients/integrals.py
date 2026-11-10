from typing import Literal

from pydantic import Field, field_validator, model_validator

from .base import RestClient
from .chat_contracts import RestDTO, Identifier, MessageDTO, encode_id, input_dto, response_dto


class IntegralResultDTO(RestDTO):
    latex: str
    numeric: float | None = Field(default=None, allow_inf_nan=False)
    indefinite: bool


class IntegralErrorDTO(RestDTO):
    code: str
    message: str


class IntegralSourceDTO(RestDTO):
    kind: Literal['rest', 'chat']
    channel_id: str | None = None
    author_id: str | None = None
    message_id: str | None = None


class IntegralDTO(RestDTO):
    id: Identifier
    latex: str
    status: Literal['calculated', 'failed']
    result: IntegralResultDTO | None = None
    error: IntegralErrorDTO | None = None
    source: IntegralSourceDTO
    duration_ms: int = Field(ge=0)
    created_at: str

    @field_validator('created_at')
    @classmethod
    def timestamp(cls, value):
        return MessageDTO.utc_timestamp(value)

    @model_validator(mode='after')
    def outcome(self):
        if self.status == 'calculated' and (self.result is None or self.error is not None):
            raise ValueError('Missing calculation result')
        if self.status == 'failed' and (self.error is None or self.result is not None):
            raise ValueError('Missing calculation error')
        return self


class IntegralCreate(RestDTO):
    latex: str = Field(min_length=1, max_length=1000)


class HistoryInput(RestDTO):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    status: Literal['calculated', 'failed'] | None = None


class IntegralPageDTO(RestDTO):
    items: list[IntegralDTO]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class IntegralsClient(RestClient):
    """Public integral API; a failed calculation is still a domain result."""
    service = "integrals"

    async def calculate(self, latex: str) -> IntegralDTO:
        body = input_dto(IntegralCreate, self.service, latex=latex.strip())
        # Calculation plus persistence/event publication exceeds the shared 5s timeout.
        data = await self.request_json('POST', '/api/v1/integrals',
                                       json=body.model_dump(), timeout=30.0)
        return response_dto(self, IntegralDTO, data)

    async def get(self, integral_id: str) -> IntegralDTO:
        path = encode_id(integral_id, self.service)
        return response_dto(self, IntegralDTO,
                            await self.request_json('GET', f'/api/v1/integrals/{path}'),
                            id=integral_id)

    async def history(self, limit=20, offset=0, status=None) -> IntegralPageDTO:
        params = input_dto(HistoryInput, self.service, limit=limit, offset=offset, status=status)
        page = response_dto(self, IntegralPageDTO, await self.request_json(
            'GET', '/api/v1/integrals', params=params.model_dump(exclude_none=True)),
            limit=limit, offset=offset)
        if len(page.items) > limit or len(page.items) > page.total:
            raise self.bad_response()
        if status and any(item.status != status for item in page.items):
            raise self.bad_response()
        return page
