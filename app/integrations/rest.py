"""REST adapters: external services retain ownership of their data."""
from urllib.parse import quote

import httpx

from app.ports import GatewayBadResponse, GatewayUnavailable

NOT_FOUND = object()

def get_json(client: httpx.Client, path: str):
    try:
        response = client.get(path)
    except httpx.DecodingError as exc:
        raise GatewayBadResponse('Invalid dependency encoding') from exc
    except httpx.TransportError as exc:
        raise GatewayUnavailable('Dependent service unavailable') from exc
    if response.status_code == 404:
        return NOT_FOUND
    if response.status_code != 200:
        raise GatewayBadResponse('Dependent service failed')
    try:
        return response.json()
    except ValueError as exc:
        raise GatewayBadResponse('Invalid dependency JSON') from exc


class RestUserGateway:
    def __init__(self, client: httpx.Client):
        self.client = client

    def exists(self, user_id: str) -> bool:
        data = get_json(self.client, f'api/v1/users/{quote(user_id, safe="")}')
        if data is NOT_FOUND:
            return False
        if not isinstance(data, dict) or data.get('id') != user_id:
            raise GatewayBadResponse('Invalid user response')
        return True


class RestMessageGateway:
    def __init__(self, client: httpx.Client):
        self.client = client

    def exists_in_channel(self, channel_id: str, message_id: str) -> bool:
        data = get_json(self.client, f'api/v1/channels/{quote(channel_id, safe="")}/messages')
        if data is NOT_FOUND:
            return False
        if not isinstance(data, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('id'), str)
            or not isinstance(row.get('channel_id'), str) for row in data
        ):
            raise GatewayBadResponse('Invalid messages response')
        return any(row['id'] == message_id and row['channel_id'] == channel_id for row in data)
