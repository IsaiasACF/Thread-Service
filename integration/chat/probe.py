"""Exercise the nine resolvers against the dedicated process stack, never mocks.

Returns 1 when the strict creation journey is blocked, even when diagnostics complete.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import time
import uuid
from urllib.parse import urlparse

import httpx
import pika
from pymongo import MongoClient


QUERIES = {
    'createUser': 'mutation($name:String!){createUser(displayName:$name){id displayName}}',
    'user': 'query($id:ID!){user(id:$id){id displayName}}',
    'createChannel': 'mutation($name:String!){createChannel(name:$name){id name}}',
    'channels': '{channels{id name}}',
    'channel': 'query($id:ID!){channel(id:$id){id name}}',
    'sendMessage': 'mutation($c:ID!,$a:ID!,$text:String!){sendMessage(channelId:$c,authorId:$a,content:$text){id channelId authorId content createdAt}}',
    'messages': 'query($c:ID!){messages(channelId:$c){id channelId authorId content createdAt}}',
    'createReply': 'mutation($c:ID!,$m:ID!,$a:ID!,$text:String!){createReply(channelId:$c,messageId:$m,authorId:$a,content:$text){id channelId messageId authorId content createdAt}}',
    'replies': 'query($c:ID!,$m:ID!){replies(channelId:$c,messageId:$m){id channelId messageId authorId content createdAt}}',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-local-writes', action='store_true', required=True)
    parser.add_argument('--diagnose-upstream', action='store_true', help='Read own MongoDB to diagnose a failed Users creation; never forge a success')
    parser.add_argument('--faults-and-restart', action='store_true', help='Stop/restart only processes owned by this local launcher')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    state = Path(manifest['state'])
    if json.loads((state / 'owner.json').read_text())['owner'] != 'thread-service-chat-integration-v1':
        parser.error('The manifest must belong to process_stack.py')
    if urlparse(manifest['mongo_url']).hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Only the dedicated loopback test stack is allowed')
    ports = manifest['ports']
    base = f'http://127.0.0.1:{ports["gateway"]}'
    tag = uuid.uuid4().hex[:12]
    report = dict(kind='real-services-no-mocks', source_commit=manifest['source_commit'],
                  strict_e2e_passed=False, tag=tag, operations={}, checks={}, fixtures={}, external_blockers=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def call(operation_name, **variables):
        response = httpx.post(base + '/graphql', json={'query': QUERIES[operation_name], 'variables': variables}, timeout=15)
        response.raise_for_status()
        return response.json()

    def operation(operation_name, **variables):
        body = call(operation_name, **variables)
        value = (body.get('data') or {}).get(operation_name)
        report['operations'][operation_name] = {'success': 'errors' not in body, 'response': body}
        save()
        return value

    def expect_code(label, name, expected, **variables):
        body = call(name, **variables)
        assert body['errors'][0]['extensions']['code'] == expected, body
        report['checks'][label] = {'passed': True, 'extensions': body['errors'][0]['extensions']}

    def control(service, action):
        request_id = uuid.uuid4().hex
        temporary = state / 'control.tmp'
        temporary.write_text(json.dumps({'id': request_id, 'service': service, 'action': action}))
        temporary.replace(state / 'control.json')
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            result = state / 'control-result.json'
            if result.exists() and json.loads(result.read_text()).get('id') == request_id:
                return
            time.sleep(0.1)
        raise TimeoutError('Local process controller did not respond')

    def health(service):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if service == 'mongodb':
                    with MongoClient(manifest['mongo_url'], serverSelectionTimeoutMS=500) as test_mongo:
                        test_mongo.admin.command('ping')
                else:
                    httpx.get(f'http://127.0.0.1:{ports[service]}/health', timeout=1).raise_for_status()
                return
            except Exception:
                time.sleep(0.2)
        raise TimeoutError('Service did not become healthy: ' + service)

    mongo = MongoClient(manifest['mongo_url'], serverSelectionTimeoutMS=3000)
    try:
        for service in ('users', 'channels', 'messages', 'threads', 'gateway'):
            health(service)
        report['checks']['real_service_health'] = {'passed': True, 'services': ['users', 'channels', 'messages', 'threads', 'gateway']}
        report['mongo_version'] = mongo.server_info()['version']
        username = 'IT-usuario-' + tag
        user = operation('createUser', name=username)
        if not user:
            report['external_blockers'].append('Users POST persisted data but did not return a valid creation response')
            if not args.diagnose_upstream:
                return 1
            user = mongo.chat_users.users.find_one({'display_name': username}, {'_id': 0})
            assert user, 'No user was persisted; diagnostic cannot continue'
            report['checks']['user_write_after_error'] = {'passed': True, 'recovery': 'Read-only inspection of this run\'s own MongoDB', 'id': user['id']}
        uid = user['id']
        assert operation('user', id=uid) == {'id': uid, 'displayName': username}
        channel_name = 'it-canal-' + tag
        channel = operation('createChannel', name=channel_name)
        channels = operation('channels')
        if not channel:
            report['external_blockers'].append('Channels POST persisted data but did not return a valid creation response')
            channel = next(item for item in channels if item['name'] == channel_name)
        cid = channel['id']
        assert operation('channel', id=cid) == channel
        text = 'Mensaje real de integración ' + tag
        message = operation('sendMessage', c=cid, a=uid, text=text)
        messages = operation('messages', c=cid)
        if not message:
            report['external_blockers'].append('Messages POST persisted data but failed while publishing/serializing an ObjectId')
            message = next(item for item in messages if item['content'] == text)
        mid = message['id']
        assert message['channelId'] == cid and message['authorId'] == uid
        assert datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).utcoffset().total_seconds() == 0
        assert operation('replies', c=cid, m=mid) == []
        reply_text = 'Respuesta real de integración ' + tag
        reply = operation('createReply', c=cid, m=mid, a=uid, text=reply_text)
        assert reply and reply['channelId'] == cid and reply['messageId'] == mid and reply['authorId'] == uid
        assert datetime.fromisoformat(reply['createdAt'].replace('Z', '+00:00')).utcoffset().total_seconds() == 0
        assert reply in call('replies', c=cid, m=mid)['data']['replies']
        report['fixtures'] = dict(user_id=uid, channel_id=cid, message_id=mid, reply_id=reply['id'],
                                  username=username, channel_name=channel_name, message=text, reply=reply_text)
        report['checks']['references_and_utc'] = {'passed': True}
        report['checks']['reply_round_trip'] = {'passed': True, 'reply_id': reply['id']}
        expect_code('missing_user', 'user', 'NOT_FOUND', id='missing-' + tag)
        expect_code('missing_channel', 'channel', 'NOT_FOUND', id='missing-' + tag)
        expect_code('missing_root', 'replies', 'NOT_FOUND', c=cid, m='missing-' + tag)
        expect_code('invalid_author_message', 'sendMessage', 'VALIDATION_ERROR', c=cid, a='missing-' + tag, text='invalid author')
        expect_code('invalid_author_reply', 'createReply', 'VALIDATION_ERROR', c=cid, m=mid, a='missing-' + tag, text='invalid author')
        expect_code('empty_content', 'sendMessage', 'VALIDATION_ERROR', c=cid, a=uid, text='')
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            document = mongo.chat_integration_threads.replies.find_one({'id': reply['id']})
            published = document.get('_outbox', {}).get('published_at')
            if published:
                break
            time.sleep(0.2)
        assert published, 'The real worker did not confirm publication'
        credentials = json.loads((state / 'runtime-credentials.json').read_text())
        params = pika.ConnectionParameters('127.0.0.1', ports['rabbitmq'], credentials=pika.PlainCredentials(credentials['username'], credentials['password']))
        connection = pika.BlockingConnection(params)
        try:
            channel_amqp = connection.channel()
            found = False
            while True:
                method, properties, payload = channel_amqp.basic_get('chat.integration.replies', auto_ack=False)
                if method is None:
                    break
                event = json.loads(payload)
                channel_amqp.basic_ack(method.delivery_tag)
                if event['data']['id'] == reply['id']:
                    assert event['type'] == 'chat.thread.reply.created'
                    found = True
            assert found, 'Expected reply event not found in own RabbitMQ queue'
        finally:
            connection.close()
        report['checks']['real_amqp_delivery'] = {'passed': True, 'reply_id': reply['id'], 'published_at': published.isoformat() + 'Z'}
        if args.faults_and_restart:
            control('users', 'stop')
            try:
                expect_code('real_connection_error', 'user', 'UPSTREAM_UNAVAILABLE', id=uid)
                health('gateway')
            finally:
                control('users', 'start')
                health('users')
            user_pid = json.loads(args.manifest.read_text())['pids']['users']
            os.kill(user_pid, signal.SIGSTOP)
            try:
                expect_code('real_timeout', 'user', 'UPSTREAM_TIMEOUT', id=uid)
            finally:
                os.kill(user_pid, signal.SIGCONT)
            control('messages', 'stop')
            try:
                expect_code('real_dependency_503', 'replies', 'UPSTREAM_UNAVAILABLE', c=cid, m=mid)
            finally:
                control('messages', 'start')
                health('messages')
            control('mongodb', 'restart')
            health('mongodb')
            for service in ('users', 'channels', 'messages', 'threads', 'gateway'):
                control(service, 'restart')
                health(service)
            assert call('user', id=uid)['data']['user']['id'] == uid
            assert call('channel', id=cid)['data']['channel']['id'] == cid
            assert message in call('messages', c=cid)['data']['messages']
            assert reply in call('replies', c=cid, m=mid)['data']['replies']
            report['checks']['disk_persistence_after_restart'] = {'passed': True, 'restarted': ['mongodb', 'users', 'channels', 'messages', 'threads', 'gateway']}
        report['strict_e2e_passed'] = all(item['success'] for item in report['operations'].values())
        return 0 if report['strict_e2e_passed'] else 1
    finally:
        mongo.close()
        save()
        print(json.dumps({'strict_e2e_passed': report['strict_e2e_passed'],
                          'successful_operations': [name for name, result in report['operations'].items() if result['success']],
                          'blocked_operations': [name for name, result in report['operations'].items() if not result['success']],
                          'real_checks_verified': list(report['checks']), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
