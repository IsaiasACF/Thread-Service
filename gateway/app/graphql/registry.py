from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GraphQLModule:
    type_defs: str
    bindables: tuple[Any, ...]


def discover_modules() -> list[GraphQLModule]:
    """Each domain owns its module.py; no central list to edit on integration."""
    directory = Path(__file__).parent
    return [import_module(f"{__package__}.{path.parent.name}.module").module
            for path in sorted(directory.glob("*/module.py"))]
