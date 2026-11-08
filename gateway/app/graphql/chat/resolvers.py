from ariadne import ObjectType

from .mapping import channel_result, message_result, user_result

query = ObjectType("Query")
mutation = ObjectType("Mutation")


@query.field("user")
async def user(_, info, id):
    return user_result(await info.context["clients"]["users"].get_user(id))


@query.field("channels")
async def channels(_, info):
    return [channel_result(dto) for dto in await info.context["clients"]["channels"].list_channels()]


@query.field("channel")
async def channel(_, info, id):
    return channel_result(await info.context["clients"]["channels"].get_channel(id))


@query.field("messages")
async def messages(_, info, channelId):
    return [message_result(dto) for dto in await info.context["clients"]["messages"].list_messages(channelId)]


@mutation.field("createUser")
async def create_user(_, info, displayName):
    return user_result(await info.context["clients"]["users"].create_user(displayName))


@mutation.field("createChannel")
async def create_channel(_, info, name):
    return channel_result(await info.context["clients"]["channels"].create_channel(name))


@mutation.field("sendMessage")
async def send_message(_, info, channelId, authorId, content):
    dto = await info.context["clients"]["messages"].send_message(channelId, authorId, content)
    return message_result(dto)


bindables = (query, mutation)
