from ariadne import ObjectType
from ..errors import pending

query = ObjectType("Query")
mutation = ObjectType("Mutation")

for field in ['replies']:
    query.set_field(field, pending("threads"))
for field in ['createReply']:
    mutation.set_field(field, pending("threads"))

bindables = (query, mutation)
