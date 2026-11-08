from .base import RestClient
from .chat_contracts import MessageCreate, MessageDTO, encode_id, input_dto, response_dto, response_list


class MessagesClient(RestClient):
    service = "messages"

    def _path(self, channel_id: str) -> str:
        return f"/api/v1/channels/{encode_id(channel_id, self.service)}/messages"

    async def list_messages(self, channel_id: str) -> list[MessageDTO]:
        data = await self.request_json("GET", self._path(channel_id))
        return response_list(self, MessageDTO, data, channel_id=channel_id)

    async def send_message(self, channel_id: str, author_id: str, content: str) -> MessageDTO:
        body = input_dto(MessageCreate, self.service, author_id=author_id, content=content)
        data = await self.request_json("POST", self._path(channel_id), json=body.model_dump())
        return response_dto(self, MessageDTO, data, channel_id=channel_id, author_id=body.author_id)
