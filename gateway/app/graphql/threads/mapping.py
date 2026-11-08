from ...clients.chat_contracts import ReplyDTO


def reply_result(dto: ReplyDTO) -> dict:
    return {"id": dto.id, "channelId": dto.channel_id, "messageId": dto.message_id,
            "authorId": dto.author_id, "content": dto.content, "createdAt": dto.created_at}
