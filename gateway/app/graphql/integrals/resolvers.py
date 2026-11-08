from ariadne import ObjectType
from ..errors import pending

query = ObjectType("Query")
mutation = ObjectType("Mutation")

for field in ['integrals', 'integral']:
    query.set_field(field, pending("integrals"))
for field in ['calculateIntegral']:
    mutation.set_field(field, pending("integrals"))

bindables = (query, mutation)
