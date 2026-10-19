from unittest.mock import patch

import mongomock
from fastapi.testclient import TestClient

from app.asgi import app


def test_operational_lifespan_wires_service_indexes_and_closes():
    mongo = mongomock.MongoClient()
    with patch('app.asgi.mongo_client', return_value=mongo), patch(
        'app.asgi.RestMessageGateway'
    ) as messages, patch('app.asgi.RestUserGateway') as users:
        messages.return_value.exists_in_channel.return_value = True
        users.return_value.exists.return_value = True
        with TestClient(app) as client:
            route = '/api/v1/channels/channel/messages/root/replies'
            response = client.post(route, json={'author_id': 'user', 'content': 'Hello'})
            assert response.status_code == 201
            assert client.get(route).json() == [response.json()]
            assert mongo.threads.replies.count_documents({}) == 1
            assert mongo.threads.replies.find_one()['_outbox']['published_at'] is None
            assert any(index.get('unique') for index in mongo.threads.replies.index_information().values())
        assert app.state.thread_service is None
