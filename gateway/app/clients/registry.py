from importlib import import_module
from pathlib import Path

from .base import RestClient
from ..config import Settings


def build_clients(http, settings: Settings) -> dict[str, RestClient]:
    clients = {}
    for path in sorted(Path(__file__).parent.glob("*.py")):
        if path.stem in {"__init__", "base", "registry"}:
            continue
        module = import_module(f"{__package__}.{path.stem}")
        for candidate in vars(module).values():
            if (isinstance(candidate, type) and issubclass(candidate, RestClient)
                    and candidate is not RestClient and candidate.__module__ == module.__name__):
                url = getattr(settings, f"{candidate.service}_base_url", None)
                clients[candidate.service] = candidate(http, str(url) if url else None)
    return clients
