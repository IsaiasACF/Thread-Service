from ariadne import ObjectType
from ..errors import pending

query = ObjectType("Query")
mutation = ObjectType("Mutation")

for field in ['poll']:
    query.set_field(field, pending("polls"))
for field in ['createPoll', 'votePoll', 'closePoll']:
    mutation.set_field(field, pending("polls"))

bindables = (query, mutation)
