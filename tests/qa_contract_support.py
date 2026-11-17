"""Load pinned provider routes with a private persistence stub before import."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import httpx


def load_provider(source: Path, name: str, monkeypatch):
    collection = MagicMock(name=f'{name}_contract_collection')
    mongo = MagicMock(name='contract_mongo')
    database = MagicMock(name=f'chat_{name}')
    setattr(mongo.return_value, f'chat_{name}', database)
    setattr(database, name, collection)
    monkeypatch.setattr('pymongo.MongoClient', mongo)
    monkeypatch.setenv('MONGODB_URL', 'mongodb://contract.invalid:27017')
    spec = importlib.util.spec_from_file_location(
        f'_qa_contract_{name}', source / name / 'app' / 'main.py',
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app, collection, mongo


def provider_transport(provider, requests):
    """Run the actual provider HTTP route for every consumer request."""
    def handle(request):
        requests.append((request.method, request.url.path))
        response = provider.request(request.method, request.url.path)
        return httpx.Response(response.status_code, content=response.content,
                              headers={'content-type': response.headers['content-type']})
    return httpx.MockTransport(handle)


def assert_user_contract(response, expected_id):
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert isinstance(body.get('id'), str)
    assert body['id'] == expected_id


def assert_messages_contract(response):
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    for row in body:
        assert isinstance(row, dict)
        assert isinstance(row.get('id'), str)
        assert isinstance(row.get('channel_id'), str)
