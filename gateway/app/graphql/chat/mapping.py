from ...clients.chat_contracts import ChannelDTO, MessageDTO, UserDTO


def user_result(dto: UserDTO) -> dict:
    return {"id": dto.id, "displayName": dto.display_name}


def channel_result(dto: ChannelDTO) -> dict:
    return {"id": dto.id, "name": dto.name}


def message_result(dto: MessageDTO) -> dict:
    return {"id": dto.id, "channelId": dto.channel_id, "authorId": dto.author_id,
            "content": dto.content, "createdAt": dto.created_at}
