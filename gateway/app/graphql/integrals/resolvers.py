from ariadne import ObjectType

query = ObjectType("Query")
mutation = ObjectType("Mutation")

def integral_result(dto):
    data = dto.model_dump()
    data['durationMs'] = data.pop('duration_ms')
    data['createdAt'] = data.pop('created_at')
    source = data['source']
    for snake, camel in [('channel_id', 'channelId'), ('author_id', 'authorId'), ('message_id', 'messageId')]:
        source[camel] = source.pop(snake)
    return data


@query.field('integrals')
async def integrals(_, info, limit=20, offset=0, status=None):
    page = await info.context['clients']['integrals'].history(limit, offset, status)
    return {**page.model_dump(), 'items': [integral_result(item) for item in page.items]}


@query.field('integral')
async def integral(_, info, id):
    return integral_result(await info.context['clients']['integrals'].get(id))


@mutation.field('calculateIntegral')
async def calculate_integral(_, info, latex):
    return integral_result(await info.context['clients']['integrals'].calculate(latex))

bindables = (query, mutation)
