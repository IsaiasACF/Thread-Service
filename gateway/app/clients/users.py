from .base import RestClient
from .chat_contracts import UserCreate, UserDTO, encode_id, input_dto, response_dto


class UsersClient(RestClient):
    service = "users"

    async def get_user(self, user_id: str) -> UserDTO:
        data = await self.request_json("GET", f"/api/v1/users/{encode_id(user_id, self.service)}")
        return response_dto(self, UserDTO, data, id=user_id)

    async def create_user(self, display_name: str) -> UserDTO:
        body = input_dto(UserCreate, self.service, display_name=display_name)
        data = await self.request_json("POST", "/api/v1/users", json=body.model_dump())
        return response_dto(self, UserDTO, data)
