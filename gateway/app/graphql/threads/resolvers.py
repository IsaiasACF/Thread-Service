from ariadne import ObjectType

from .mapping import reply_result

query = ObjectType("Query")
mutation = ObjectType("Mutation")


@query.field("replies")
async def replies(_, info, channelId, messageId):
    dtos = await info.context["clients"]["threads"].list_replies(channelId, messageId)
    return [reply_result(dto) for dto in dtos]


@mutation.field("createReply")
async def create_reply(_, info, channelId, messageId, authorId, content):
    dto = await info.context["clients"]["threads"].create_reply(channelId, messageId, authorId, content)
    return reply_result(dto)


bindables = (query, mutation)
