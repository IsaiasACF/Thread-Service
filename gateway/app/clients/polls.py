from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import RestClient
from .chat_contracts import RestDTO, Identifier, MessageDTO, encode_id, input_dto, response_dto


class PollCreate(RestDTO):
    channel_id: Identifier
    author_id: Identifier
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=10)
    duration_minutes: int = Field(default=5, ge=1, le=1440)

    @field_validator('channel_id', 'author_id', 'question', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('options')
    @classmethod
    def alternatives(cls, values):
        values = [value.strip() for value in values]
        if any(not value for value in values) or len({v.casefold() for v in values}) != len(values):
            raise ValueError('Alternatives must be nonempty and distinct')
        return values


class OptionDTO(RestDTO):
    option_id: str
    position: int = Field(ge=0)
    text: str
    vote_count: int = Field(ge=0)

    @field_validator('option_id')
    @classmethod
    def uuid(cls, value):
        UUID(value)
        return value


class PollDTO(RestDTO):
    poll_id: str
    channel_id: Identifier
    author_id: Identifier
    question: str
    options: list[OptionDTO] = Field(min_length=2, max_length=10)
    status: Literal['pending_announcement', 'open', 'closed', 'creation_failed']
    duration_minutes: int = Field(ge=1, le=1440)
    closes_at: str
    created_at: str
    closed_at: str | None
    total_votes: int = Field(ge=0)
    creation_error: str | None = None

    @field_validator('poll_id')
    @classmethod
    def uuid(cls, value):
        UUID(value)
        return value

    @field_validator('closes_at', 'created_at', 'closed_at')
    @classmethod
    def timestamp(cls, value):
        return MessageDTO.utc_timestamp(value) if value is not None else None

    @model_validator(mode='after')
    def counts(self):
        ids = {option.option_id for option in self.options}
        positions = {option.position for option in self.options}
        if len(ids) != len(self.options) or positions != set(range(len(self.options))):
            raise ValueError('Inconsistent options')
        if sum(option.vote_count for option in self.options) != self.total_votes:
            raise ValueError('Inconsistent results')
        return self


class VoteInput(RestDTO):
    voter_id: Identifier
    option_id: str

    @field_validator('option_id')
    @classmethod
    def uuid(cls, value):
        return str(UUID(value))


class VoteDTO(VoteInput):
    poll_id: str
    cast_at: str

    @field_validator('poll_id')
    @classmethod
    def uuid(cls, value):
        UUID(value)
        return value

    @field_validator('cast_at')
    @classmethod
    def timestamp(cls, value):
        return MessageDTO.utc_timestamp(value)


class CloseInput(RestDTO):
    author_id: Identifier


class KeyInput(RestDTO):
    key: str = Field(min_length=1)

    @field_validator('key')
    @classmethod
    def safe_header(cls, value):
        if not value.strip() or not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Invalid idempotency header')
        return value


class PollIdentifier(RestDTO):
    id: str

    @field_validator('id')
    @classmethod
    def uuid(cls, value):
        return str(UUID(value))


class PollsClient(RestClient):
    """Polls owns voting, deadlines, permissions and idempotency."""
    service = "polls"

    def poll_path(self, poll_id):
        return f'/api/v1/polls/{encode_id(poll_id, self.service)}'

    async def get(self, poll_id):
        poll_id = input_dto(PollIdentifier, self.service, id=poll_id).id
        return response_dto(self, PollDTO,
            await self.request_json('GET', self.poll_path(poll_id)), poll_id=poll_id)

    async def create(self, data, key):
        body = input_dto(PollCreate, self.service, **data)
        key = input_dto(KeyInput, self.service, key=key).key
        result = await self.request_json('POST', '/api/v1/polls',
            json=body.model_dump(), headers={'Idempotency-Key': key})
        return response_dto(self, PollDTO, result,
                            channel_id=body.channel_id, author_id=body.author_id)

    async def vote(self, poll_id, voter_id, option_id):
        poll_id = input_dto(PollIdentifier, self.service, id=poll_id).id
        body = input_dto(VoteInput, self.service, voter_id=voter_id, option_id=option_id)
        result = await self.request_json('POST', self.poll_path(poll_id) + '/votes',
                                        json=body.model_dump())
        return response_dto(self, VoteDTO, result, poll_id=poll_id,
                            voter_id=voter_id, option_id=body.option_id)

    async def close(self, poll_id, author_id):
        poll_id = input_dto(PollIdentifier, self.service, id=poll_id).id
        body = input_dto(CloseInput, self.service, author_id=author_id)
        return response_dto(self, PollDTO, await self.request_json(
            'POST', self.poll_path(poll_id) + '/close', json=body.model_dump()),
            poll_id=poll_id, author_id=author_id)
