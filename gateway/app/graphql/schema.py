from ariadne import make_executable_schema

from .registry import discover_modules


def build_schema():
    modules = discover_modules()
    return make_executable_schema(
        [module.type_defs for module in modules],
        *[bindable for module in modules for bindable in module.bindables],
    )
