"""Prepare pinned real services outside the repository, with explicit test-only chat mode."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'chat'))
from apply_test_patch import verify_mode
from prepare import write_environment

LOCK = json.loads((HERE / 'sources.lock.json').read_text())
OWNER = 'thread-service-final-integration-v1'


def verify_external(source, spec):
    source = Path(source)
    actual = {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != set(spec['sha256']):
        raise ValueError('External source contains unexpected or missing files')
    for name, digest in spec['sha256'].items():
        file = source / name
        if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError('External source differs from the pinned revision: ' + name)


def verify(directory):
    directory = Path(directory).resolve()
    owner = json.loads((directory / 'owner.json').read_text())
    if owner['owner'] != OWNER or directory.is_relative_to(REPO):
        raise ValueError('Unrecognized or unsafe integration directory')
    env = {key: json.loads(value) for key, value in (line.split('=', 1) for line in (directory / 'compose.env').read_text().splitlines())}
    verify_mode(Path(env['CHAT_BASE_SOURCE']), owner['mode'])
    for name, spec in LOCK.items():
        verify_external(env[name.upper() + '_SOURCE_DIR'], spec)
    if env['CHAT_SOURCE_MODE'] != owner['mode'] or env['CHAT_PROJECT_NAME'] != owner['project'] or not env['CHAT_PROJECT_NAME'].startswith('tarea6-chat-'):
        raise ValueError('Source mode/project mismatch')
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--mode', choices=('original', 'corrected'), default='corrected')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    directory = args.directory.resolve()
    if args.verify:
        env = verify(directory)
        print('Verified immutable sources; mode=' + env['CHAT_SOURCE_MODE'])
        return
    if directory.is_relative_to(REPO):
        parser.error('Use a NEW private directory outside the repository')
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    subprocess.run([sys.executable, str(HERE.parent / 'chat/prepare.py'), '--directory', str(directory / 'chat'), '--mode', args.mode], check=True)
    env = {key: json.loads(value) for key, value in (line.split('=', 1) for line in (directory / 'chat/compose.env').read_text().splitlines())}
    for name, spec in LOCK.items():
        repo = spec['repository'].removeprefix('https://github.com/')
        archive = directory / (name + '.tar.gz')
        with urlopen('https://codeload.github.com/' + repo + '/tar.gz/' + spec['commit'], timeout=60) as response:
            archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['archive_sha256']:
            raise ValueError('Unexpected archive checksum: ' + name)
        target = directory / name
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter='data')
        root = next(target.iterdir())
        source = (root / spec['buildSubdirectory']).resolve()
        verify_external(source, spec)
        env[name.upper() + '_SOURCE_DIR'] = str(source)
    if args.mode == 'original':
        env.update(CHAT_USERS_PORT='28001', CHAT_CHANNELS_PORT='28002', CHAT_MESSAGES_PORT='28003', CHAT_THREADS_PORT='28004', CHAT_GATEWAY_PORT='25000', CHAT_FRONTEND_PORT='25173')
    for variable in ('FINAL_POSTGRES_PASSWORD', 'FINAL_POLLS_RABBIT_PASSWORD', 'FINAL_INTEGRALS_RABBIT_PASSWORD'):
        env[variable] = secrets.token_urlsafe(32)
    write_environment(directory / 'compose.env', env)
    (directory / 'owner.json').write_text(json.dumps({'owner': OWNER, 'mode': args.mode, 'project': env['CHAT_PROJECT_NAME']}) + '\n')
    verify(directory)
    print('Prepared private integration directory: ' + str(directory))
    print('Mode: ' + args.mode + '; keep compose.env private; originals unchanged')


if __name__ == '__main__':
    main()
