from ariadne import ObjectType
from ..errors import pending

query = ObjectType("Query")
mutation = ObjectType("Mutation")

for field in ['user', 'channels', 'channel', 'messages']:
    query.set_field(field, pending("chat"))
for field in ['createUser', 'createChannel', 'sendMessage']:
    mutation.set_field(field, pending("chat"))

bindables = (query, mutation)
