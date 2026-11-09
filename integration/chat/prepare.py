"""Fetch immutable external sources and generate a private, local-only Compose env."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import tarfile
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCK = json.loads((HERE / 'source.lock.json').read_text())


def verify_source(source: Path):
    for name, expected in LOCK['sha256'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'External source differs from pinned contract: {name}')


def write_environment(destination: Path, environment: dict[str, str]):
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        for name, value in environment.items():
            # Compose dotenv does not interpret JSON's Unicode escape sequences.
            output.write(f'{name}={json.dumps(value, ensure_ascii=False)}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--directory', type=Path)
    mode.add_argument('--verify-source', type=Path)
    parser.add_argument('--mode', choices=('original', 'corrected'), default='original')
    args = parser.parse_args()
    if args.verify_source:
        verify_source(args.verify_source.resolve())
        print('External source hashes match the pinned commit')
        return
    directory = args.directory.resolve()
    if directory.is_relative_to(REPO):
        parser.error('Use a new directory outside the repository for source and credentials')
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive = directory / 'source.tar.gz'
    url = f'https://codeload.github.com/rmasad/microservicios/tar.gz/{LOCK["commit"]}'
    with urlopen(url, timeout=60) as response, archive.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    with tarfile.open(archive) as bundle:
        bundle.extractall(directory / 'source', filter='data')
    root = next((directory / 'source').iterdir())
    source = root / LOCK['subdirectory']
    verify_source(source)
    selected_source = source
    if args.mode == 'corrected':
        from apply_test_patch import apply_patch
        selected_source = directory / 'corrected-source'
        apply_patch(source, selected_source)
    environment = {
        'CHAT_SOURCE_MODE': args.mode,
        'CHAT_BASE_SOURCE': str(selected_source), 'CHAT_PROJECT_NAME': 'tarea6-chat-' + secrets.token_hex(4),
        'CHAT_RABBIT_USER': 'chat_it', 'CHAT_RABBIT_PASSWORD': secrets.token_urlsafe(32),
    }
    write_environment(directory / 'compose.env', environment)
    print(f'Source verified at commit {LOCK["commit"]}')
    print('Compose env (private, do not commit): ' + str(directory / 'compose.env'))
    print('Original source (unchanged): ' + str(source))
    print('Selected test source: ' + str(selected_source))
    print('Mode: ' + args.mode)


if __name__ == '__main__':
    main()
