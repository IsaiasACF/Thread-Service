"""Run original or explicitly patched TEST-ONLY services on loopback when a local Docker daemon is unavailable.

State must be outside this repository. No deletion, global installs or mock transports.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import urlopen

import pika
from pymongo import MongoClient

from apply_test_patch import verify_mode

REPO = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = 'd15f2e20ced1007099b90bf59b720e97be3d2d4a'
PORTS = dict(users=18001, channels=18002, messages=18003, threads=18004,
             gateway=15000, frontend=15173, mongodb=27027, rabbitmq=15679,
             epmd=14379, distribution=25679)


def executable(path: Path) -> Path:
    # Resolving bin/python symlinks would bypass pyvenv.cfg and the virtualenv.
    return path.absolute()


def check_ports(ports: dict[str, int]):
    for name, port in ports.items():
        with socket.socket() as check:
            # Permit immediate restarts after TIME_WAIT, but never steal a listener.
            check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                check.bind(('127.0.0.1', port))
            except OSError:
                raise RuntimeError(f'{name} port {port} is occupied; existing processes were not touched') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('source', 'mongod', 'rabbit-runtime', 'base-python', 'thread-python', 'gateway-python', 'node', 'state'):
        parser.add_argument('--' + option, required=True, type=Path)
    parser.add_argument('--resume', action='store_true', help='Reuse only a state directory created by this launcher')
    parser.add_argument('--mode', choices=('original', 'corrected'), default='original')
    args = parser.parse_args()
    source_metadata = verify_mode(args.source.resolve(), args.mode)
    state = args.state.resolve()
    if state.is_relative_to(REPO):
        parser.error('State, credentials and database files must be outside the repository')
    if args.resume:
        marker = json.loads((state / 'owner.json').read_text())
        expected = {'owner': 'thread-service-chat-integration-v1', 'source_commit': SOURCE_COMMIT, 'source_mode': args.mode}
        legacy = {'owner': 'thread-service-chat-integration-v1', 'source_commit': SOURCE_COMMIT}
        if marker != expected and not (args.mode == 'original' and marker == legacy):
            parser.error('Unrecognized state directory; refusing to reuse it')
    else:
        state.mkdir(parents=True, exist_ok=False, mode=0o700)
        (state / 'owner.json').write_text(json.dumps({'owner': 'thread-service-chat-integration-v1', 'source_commit': SOURCE_COMMIT, 'source_mode': args.mode}))
    try:
        check_ports(PORTS)
    except RuntimeError as error:
        parser.error(str(error))
    for directory in ('data/mongo', 'data/rabbit', 'logs', 'bin', 'rabbit-home', 'xdg/erlang'):
        (state / directory).mkdir(parents=True, exist_ok=True)
    credential_file = state / 'runtime-credentials.json'
    if credential_file.exists():
        credentials = json.loads(credential_file.read_text())
    else:
        credentials = {'username': 'it_' + secrets.token_hex(6), 'password': secrets.token_urlsafe(32)}
        descriptor = os.open(credential_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            json.dump(credentials, output)
    rabbit_runtime = args.rabbit_runtime.resolve()
    erlang = rabbit_runtime / 'usr/lib/erlang'
    erts = next(erlang.glob('erts-*'))
    erl = state / 'bin/erl'
    erl.write_text('#!/usr/bin/python3\nimport os,sys\nenv=dict(os.environ)\n'
                   f'env.update(ROOTDIR={str(erlang)!r}, BINDIR={str(erts / "bin")!r}, EMU="beam", PROGNAME="erl")\n'
                   f'os.execve({str(erts / "bin/erlexec")!r}, ["erl", *sys.argv[1:]], env)\n')
    erl.chmod(0o700)
    config = state / 'rabbitmq.conf'
    config.write_text(f'listeners.tcp.1 = 127.0.0.1:{PORTS["rabbitmq"]}\n'
                      'distribution.listener.interface = 127.0.0.1\n'
                      f'distribution.listener.port_range.min = {PORTS["distribution"]}\n'
                      f'distribution.listener.port_range.max = {PORTS["distribution"]}\n')
    mongo_url = f'mongodb://127.0.0.1:{PORTS["mongodb"]}'
    amqp_url = ('amqp://' + quote(credentials['username'], safe='') + ':' + quote(credentials['password'], safe='')
                + f'@127.0.0.1:{PORTS["rabbitmq"]}/%2F')
    common = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    source = args.source.resolve()
    definitions = {}

    def define(name, command, cwd=REPO, **environment):
        definitions[name] = (list(map(str, command)), cwd, dict(common, **environment))

    define('mongodb', [args.mongod.resolve(), '--dbpath', state / 'data/mongo', '--bind_ip', '127.0.0.1', '--port', PORTS['mongodb'], '--quiet'], state)
    define('epmd', [erts / 'bin/epmd', '-port', PORTS['epmd'], '-address', '127.0.0.1'], state)
    define('rabbitmq', [rabbit_runtime / 'usr/lib/rabbitmq/bin/rabbitmq-server'], state,
           XDG_CONFIG_HOME=str(state / 'xdg'), ERL_CRASH_DUMP=str(state / 'logs/erl-crash.dump'),
           PATH=str(state / 'bin') + os.pathsep + os.environ['PATH'],
           ERL_EPMD_PORT=str(PORTS['epmd']), ERL_EPMD_ADDRESS='127.0.0.1',
           RABBITMQ_NODENAME='chat_integration@localhost', RABBITMQ_NODE_IP_ADDRESS='127.0.0.1',
           RABBITMQ_NODE_PORT=str(PORTS['rabbitmq']), RABBITMQ_DIST_PORT=str(PORTS['distribution']),
           RABBITMQ_CONFIG_FILE=str(config), RABBITMQ_CONF_ENV_FILE=str(state / 'absent-env.conf'),
           RABBITMQ_MNESIA_BASE=str(state / 'data/rabbit'), RABBITMQ_LOG_BASE=str(state / 'logs'),
           RABBITMQ_PLUGINS_EXPAND_DIR=str(state / 'rabbit-plugins'),
           RABBITMQ_PID_FILE=str(state / 'rabbit.pid'), RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS='+S 2:2',
           RABBITMQ_DEFAULT_USER=credentials['username'], RABBITMQ_DEFAULT_PASS=credentials['password'])
    for service in ('users', 'channels', 'messages'):
        extra = dict(MONGODB_URL=mongo_url)
        if service == 'messages':
            extra.update(USERS_URL=f'http://127.0.0.1:{PORTS["users"]}',
                         CHANNELS_URL=f'http://127.0.0.1:{PORTS["channels"]}', RABBITMQ_URL=amqp_url)
        define(service, [executable(args.base_python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', PORTS[service]], source / service, **extra)
    thread_env = dict(THREAD_MONGODB_URL=mongo_url, THREAD_MONGODB_DATABASE='chat_integration_threads',
                      THREAD_USERS_URL=f'http://127.0.0.1:{PORTS["users"]}',
                      THREAD_MESSAGES_URL=f'http://127.0.0.1:{PORTS["messages"]}', THREAD_RABBITMQ_URL=amqp_url,
                      THREAD_RABBITMQ_EXCHANGE='chat', THREAD_RABBITMQ_QUEUE='chat.integration.replies')
    define('threads', [executable(args.thread_python), '-m', 'uvicorn', 'app.asgi:app', '--host', '127.0.0.1', '--port', PORTS['threads']], **thread_env)
    define('worker', [executable(args.thread_python), '-m', 'app.workers.outbox'], **thread_env)
    define('gateway', [executable(args.gateway_python), '-m', 'uvicorn', 'gateway.app.main:app', '--host', '127.0.0.1', '--port', PORTS['gateway']],
           **{f'{s.upper()}_BASE_URL': f'http://127.0.0.1:{PORTS[s]}' for s in ('users', 'channels', 'messages', 'threads')},
           HTTP_TIMEOUT_SECONDS='2', CORS_ORIGINS=json.dumps([f'http://127.0.0.1:{PORTS["frontend"]}']))
    define('frontend', [args.node.resolve(), REPO / 'frontend/node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', PORTS['frontend'], '--strictPort'],
           REPO / 'frontend', GATEWAY_PROXY_TARGET=f'http://127.0.0.1:{PORTS["gateway"]}')
    processes, logs = {}, []
    stopped = False

    def save_manifest():
        manifest = {'kind': 'real-processes-no-mocks', 'source_commit': SOURCE_COMMIT, 'source_mode': args.mode,
                    'test_source': source_metadata, 'ports': PORTS,
                    'mongo_url': mongo_url, 'state': str(state),
                    'pids': {name: process.pid for name, process in processes.items() if process.poll() is None}}
        (state / 'manifest.json').write_text(json.dumps(manifest, indent=2))

    def start(name):
        command, cwd, env = definitions[name]
        log = (state / 'logs' / f'{name}.log').open('a')
        logs.append(log)
        processes[name] = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        save_manifest()

    def stop(name):
        process = processes.get(name)
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        save_manifest()

    def ready(name):
        if name == 'mongodb':
            with MongoClient(mongo_url, serverSelectionTimeoutMS=500) as mongo:
                mongo.admin.command('ping')
        elif name == 'rabbitmq':
            params = pika.URLParameters(amqp_url)
            params.socket_timeout = 1
            connection = pika.BlockingConnection(params)
            connection.close()
        elif name == 'epmd':
            with socket.create_connection(('127.0.0.1', PORTS['epmd']), timeout=1):
                pass
        elif name == 'worker':
            return
        else:
            path = '/' if name == 'frontend' else '/health'
            with urlopen(f'http://127.0.0.1:{PORTS[name]}{path}', timeout=1) as response:
                assert response.status == 200

    def wait_ready(name):
        deadline = time.monotonic() + 60
        while not stopped:
            if processes[name].poll() is not None:
                raise RuntimeError(f'{name} exited; inspect its private runtime log')
            try:
                ready(name)
                return
            except Exception:
                if time.monotonic() > deadline:
                    raise RuntimeError(f'{name} startup timeout; inspect its private runtime log') from None
                time.sleep(0.3)

    def request_stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        for name in definitions:
            start(name)
            wait_ready(name)
            if stopped:
                return
            print(f'READY {name}', flush=True)
        print('STACK_READY ' + str(state / 'manifest.json'), flush=True)
        while not stopped:
            control = state / 'control.json'
            if control.exists():
                request = json.loads(control.read_text())
                control.unlink()
                name, action = request['service'], request['action']
                if name not in definitions or action not in ('start', 'stop', 'restart'):
                    raise ValueError('Unsupported control request')
                if action in ('stop', 'restart'):
                    stop(name)
                if action in ('start', 'restart'):
                    start(name)
                    wait_ready(name)
                (state / 'control-result.json').write_text(json.dumps({'id': request['id'], 'service': name, 'action': action}))
            time.sleep(0.2)
    finally:
        for name in reversed(list(processes)):
            stop(name)
        for log in logs:
            log.close()
        print('STACK_STOPPED: data retained at ' + str(state), flush=True)


if __name__ == '__main__':
    main()
