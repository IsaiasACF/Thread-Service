from pathlib import Path
from ..registry import GraphQLModule
from .resolvers import bindables

module = GraphQLModule(
    type_defs=Path(__file__).with_name("schema.graphql").read_text(encoding="utf-8"),
    bindables=bindables,
)
