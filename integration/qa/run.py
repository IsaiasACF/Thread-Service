"""Prepare pinned providers and execute Tarea 7 contracts/integration."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from sources import LOCK, create_corrected, verify_corrected

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / 'integration/chat'))
source_tools = importlib.import_module('prepare')
patch_tools = importlib.import_module('apply_test_patch')
OWNER = 'thread-service-tarea7-qa-v1'


def execute(command, **kwargs):
    return subprocess.run(command, cwd=REPO, check=True, **kwargs)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def prepare(directory):
    environment = os.environ.copy()
    environment['PYTHONUTF8'] = '1'
    execute([sys.executable, str(REPO / 'integration/chat/prepare.py'),
             '--directory', str(directory), '--mode', 'original'], env=environment)
    root = next((directory / 'source').iterdir())
    original = root / LOCK['subdirectory']
    create_corrected(original, directory / 'corrected-source', patch_tools)
    project = 'tarea7-qa-' + secrets.token_hex(6)
    output = directory / 'evidence'
    output.mkdir()
    (directory / 'qa.env').unlink(missing_ok=True)
    source_tools.write_environment(directory / 'qa.env', {
        'QA_SOURCE': str(directory / 'corrected-source'),
        'QA_OUTPUT': str(output), 'QA_RABBIT_PASSWORD': secrets.token_hex(24),
    })
    write_json(directory / 'qa.json', {
        'owner': OWNER, 'repository': str(REPO), 'project': project,
        'original': str(original), 'corrected': str(directory / 'corrected-source'),
    })
    write_json(output / 'sources.json', verify_corrected(directory / 'corrected-source', patch_tools))
    print(f'QA prepared: {project}. Contract providers use original sources.')


def load_state(directory):
    state = json.loads((directory / 'qa.json').read_text(encoding='utf-8'))
    if state.get('owner') != OWNER or state.get('repository') != str(REPO):
        raise ValueError('Directory does not belong to this repository QA launcher')
    if not state.get('project', '').startswith('tarea7-qa-'):
        raise ValueError('Invalid QA project name')
    return state


def contract(directory, state):
    source_tools.verify_source(Path(state['original']))
    environment = os.environ.copy()
    environment['THREAD_QA_SOURCE'] = state['original']
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    execute([sys.executable, '-m', 'pytest', '-q', '-W', 'error',
             'tests/test_qa_contract.py',
             '--junitxml=' + str(directory / 'evidence/contrato.xml')], env=environment)


def compose(directory, state, *arguments, capture=False):
    return execute([
        'docker', 'compose', '--env-file', str(directory / 'qa.env'),
        '-p', state['project'], '-f', str(HERE / 'compose.yaml'), *arguments,
    ], capture_output=capture, text=True)


def integration(directory, state, keep):
    source_tools.verify_source(Path(state['original']))
    verify_corrected(directory / 'corrected-source', patch_tools)
    report = {'passed': False, 'project': state['project'],
              'sourceMode': 'corrected', 'providerCommit': source_tools.LOCK['commit']}
    report['projectCommit'] = execute(['git', 'rev-parse', 'HEAD'],
                                      capture_output=True, text=True).stdout.strip()
    report['worktreeDirty'] = bool(execute(['git', 'status', '--porcelain'],
                                         capture_output=True, text=True).stdout.strip())
    tested_files = [
        'integration/qa/run.py', 'integration/qa/compose.yaml',
        'integration/qa/Dockerfile', 'integration/qa/test_flow.py', 'integration/qa/sources.py',
        'integration/chat/prepare.py', 'integration/chat/apply_test_patch.py',
        'tests/test_qa_contract.py', 'tests/qa_contract_support.py',
    ]
    report['testedFilesSHA256'] = {
        name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in tested_files
    }
    output = directory / 'evidence'
    inspected = subprocess.run(['docker', 'network', 'inspect', 'microsvcs'],
                                capture_output=True)
    if inspected.returncode:
        execute(['docker', 'network', 'create', 'microsvcs'])
    try:
        compose(directory, state, 'config', '--quiet')
        compose(directory, state, 'build', 'qa-tests')
        compose(directory, state, 'up', '--build', '-d', '--wait', '--wait-timeout', '180')
        compose(directory, state, 'run', '--rm', '--no-deps', 'qa-tests',
                'python', '-m', 'pytest', '-q', '-W', 'error', '-p', 'no:cacheprovider',
                'integration/qa/test_flow.py::test_create_read_and_reject_invalid_replies',
                '--junitxml=/evidence/integracion.xml')
        container = compose(directory, state, 'ps', '-q', 'qa-threads', capture=True).stdout.strip()
        def started_at():
            return execute(['docker', 'inspect', '--format', '{{.State.StartedAt}}', container],
                           capture_output=True, text=True).stdout.strip()
        report['startedBefore'] = started_at()
        compose(directory, state, 'restart', 'qa-threads')
        report['startedAfter'] = started_at()
        assert report['startedBefore'] != report['startedAfter'], 'Threads did not restart'
        compose(directory, state, 'run', '--rm', '--no-deps', 'qa-tests',
                'python', '-m', 'pytest', '-q', '-W', 'error', '-p', 'no:cacheprovider',
                'integration/qa/test_flow.py::test_read_same_reply_after_restart',
                '--junitxml=/evidence/persistencia.xml')
        (output / 'compose-status.json').write_text(
            compose(directory, state, 'ps', '--format', 'json', capture=True).stdout)
        (output / 'images.json').write_text(
            compose(directory, state, 'images', '--format', 'json', capture=True).stdout)
        (output / 'dependencies.txt').write_text(
            compose(directory, state, 'run', '--rm', '--no-deps', 'qa-tests',
                    'python', '-m', 'pip', 'freeze', capture=True).stdout)
        report['passed'] = True
    finally:
        write_json(output / 'integration-summary.json', report)
        if not keep:
            compose(directory, state, 'down', '--volumes', '--remove-orphans')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'contract', 'integration', 'cleanup'])
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--keep', action='store_true', help='Keep only this QA project for inspection')
    args = parser.parse_args()
    directory = args.directory.resolve()
    if args.action == 'prepare':
        prepare(directory)
        return
    state = load_state(directory)
    if args.action == 'contract':
        contract(directory, state)
    elif args.action == 'integration':
        integration(directory, state, args.keep)
    else:
        compose(directory, state, 'down', '--volumes', '--remove-orphans')


if __name__ == '__main__':
    main()
