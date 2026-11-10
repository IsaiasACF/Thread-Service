from ariadne import ObjectType

query = ObjectType("Query")
mutation = ObjectType("Mutation")

def camel_result(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump()
    if isinstance(value, list):
        return [camel_result(item) for item in value]
    if isinstance(value, dict):
        def camel(key):
            first, *rest = key.split('_')
            return first + ''.join(part.title() for part in rest)
        return {camel(key): camel_result(item) for key, item in value.items()}
    return value


@query.field('poll')
async def poll(_, info, id):
    return camel_result(await info.context['clients']['polls'].get(id))


@mutation.field('createPoll')
async def create_poll(_, info, input, idempotencyKey):
    body = { 'channel_id': input['channelId'], 'author_id': input['authorId'],
             'question': input['question'], 'options': input['options'],
             'duration_minutes': input.get('durationMinutes', 5) }
    return camel_result(await info.context['clients']['polls'].create(body, idempotencyKey))


@mutation.field('votePoll')
async def vote_poll(_, info, pollId, voterId, optionId):
    return camel_result(await info.context['clients']['polls'].vote(pollId, voterId, optionId))


@mutation.field('closePoll')
async def close_poll(_, info, pollId, authorId):
    return camel_result(await info.context['clients']['polls'].close(pollId, authorId))

bindables = (query, mutation)
