from .base import RestClient
from .chat_contracts import ChannelCreate, ChannelDTO, encode_id, input_dto, response_dto, response_list


class ChannelsClient(RestClient):
    service = "channels"

    async def list_channels(self) -> list[ChannelDTO]:
        return response_list(self, ChannelDTO, await self.request_json("GET", "/api/v1/channels"))

    async def get_channel(self, channel_id: str) -> ChannelDTO:
        data = await self.request_json("GET", f"/api/v1/channels/{encode_id(channel_id, self.service)}")
        return response_dto(self, ChannelDTO, data, id=channel_id)

    async def create_channel(self, name: str) -> ChannelDTO:
        body = input_dto(ChannelCreate, self.service, name=name)
        data = await self.request_json("POST", "/api/v1/channels", json=body.model_dump())
        return response_dto(self, ChannelDTO, data)
