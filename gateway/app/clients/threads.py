from .base import RestClient
from .chat_contracts import ReplyCreate, ReplyDTO, encode_id, input_dto, response_dto, response_list


class ThreadsClient(RestClient):
    service = "threads"

    def _path(self, channel_id: str, message_id: str) -> str:
        channel = encode_id(channel_id, self.service)
        message = encode_id(message_id, self.service)
        return f"/api/v1/channels/{channel}/messages/{message}/replies"

    async def list_replies(self, channel_id: str, message_id: str) -> list[ReplyDTO]:
        data = await self.request_json("GET", self._path(channel_id, message_id))
        return response_list(self, ReplyDTO, data, channel_id=channel_id, message_id=message_id)

    async def create_reply(self, channel_id: str, message_id: str,
                           author_id: str, content: str) -> ReplyDTO:
        body = input_dto(ReplyCreate, self.service, author_id=author_id, content=content)
        data = await self.request_json("POST", self._path(channel_id, message_id), json=body.model_dump())
        return response_dto(self, ReplyDTO, data, channel_id=channel_id,
                            message_id=message_id, author_id=body.author_id)
