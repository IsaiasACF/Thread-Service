from ariadne import QueryType

query = QueryType()

@query.field("health")
def health(*_):
    return "ok"

bindables = (query,)
