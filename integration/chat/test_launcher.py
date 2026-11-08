"""Regression checks for real launcher failures, using only own local resources."""
from pathlib import Path
import socket
import subprocess
import venv

import pytest

from process_stack import check_ports, executable


def test_virtualenv_interpreter_keeps_its_own_prefix(tmp_path):
    environment = tmp_path / 'isolated-python'
    venv.EnvBuilder(symlinks=True).create(environment)
    interpreter = executable(environment / 'bin/python')
    prefix = subprocess.check_output([str(interpreter), '-c', 'import sys; print(sys.prefix)'], text=True).strip()
    assert Path(prefix) == environment


def test_preflight_refuses_an_existing_listener_without_disrupting_it():
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0))
        server.listen()
        port = server.getsockname()[1]
        with pytest.raises(RuntimeError, match='existing processes were not touched'):
            check_ports({'owned-test-port': port})
        with socket.create_connection(('127.0.0.1', port)):
            connection, _ = server.accept()
            connection.close()


def test_preflight_allows_restart_after_a_closed_connection():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 0))
    server.listen()
    port = server.getsockname()[1]
    with socket.create_connection(('127.0.0.1', port)) as client:
        connection, _ = server.accept()
        connection.close()
        assert client.recv(1) == b''
    server.close()
    check_ports({'owned-test-port': port})


def test_compose_environment_preserves_unicode_paths_and_private_permissions(tmp_path):
    from dotenv import dotenv_values
    from prepare import write_environment
    target = tmp_path / 'compose.env'
    source = str(tmp_path / 'carpeta con espacios' / '03_Comunicación' / 'demo')
    write_environment(target, {'CHAT_BASE_SOURCE': source, 'CHAT_RABBIT_PASSWORD': 'test-fixture-only'})
    assert dotenv_values(target)['CHAT_BASE_SOURCE'] == source
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_environment(target, {'CHAT_BASE_SOURCE': 'do-not-overwrite'})
