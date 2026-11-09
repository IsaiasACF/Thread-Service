"""Minimal TEST-ONLY patch on separate private copies; upstream stays byte-identical."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from prepare import LOCK, REPO, verify_source

PATCH_ID = 'test-only-insert-one-copy-v1'
MARKER = '.chat-test-patch.json'
REPLACEMENTS = {
    'users/app/main.py': (b'users.insert_one(user)', b'users.insert_one(user.copy())'),
    'channels/app/main.py': (b'channels.insert_one(channel)', b'channels.insert_one(channel.copy())'),
    'messages/app/main.py': (b'messages.insert_one(message)', b'messages.insert_one(message.copy())'),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def metadata(files: dict[str, bytes]) -> dict:
    return {'purpose': 'LOCAL TESTS ONLY; not an upstream or deployed fix', 'mode': 'corrected',
            'source_commit': LOCK['commit'], 'patch_id': PATCH_ID,
            'original_sha256': LOCK['sha256'],
            'copy_sha256': {name: digest(data) for name, data in files.items()},
            'changed_files': sorted(REPLACEMENTS)}


def verify_test_copy(source: Path) -> dict:
    source = source.resolve()
    if source.is_relative_to(REPO):
        raise ValueError('Private test copies must remain outside the repository')
    expected_names = set(LOCK['sha256']) | {MARKER}
    actual_names = {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if actual_names != expected_names:
        raise ValueError('Unexpected files or incomplete private test copy')
    files = {}
    for name, expected_hash in LOCK['sha256'].items():
        file = source / name
        if file.is_symlink():
            raise ValueError('Symlinks are not allowed in private test copies')
        data = file.read_bytes()
        original = data
        if name in REPLACEMENTS:
            before, after = REPLACEMENTS[name]
            if data.count(after) != 1 or before in data:
                raise ValueError(f'Unexpected test patch content: {name}')
            original = data.replace(after, before, 1)
        if digest(original) != expected_hash:
            raise ValueError(f'Test copy contains changes beyond the approved patch: {name}')
        files[name] = data
    expected = metadata(files)
    if (source / MARKER).is_symlink() or json.loads((source / MARKER).read_text()) != expected:
        raise ValueError('Invalid private test patch metadata')
    return expected


def verify_mode(source: Path, mode: str) -> dict:
    if mode == 'original':
        verify_source(source)
        return {'mode': 'original', 'source_commit': LOCK['commit']}
    if mode == 'corrected':
        return verify_test_copy(source)
    raise ValueError('Unknown source mode')


def apply_patch(source: Path, destination: Path) -> dict:
    source, destination = source.resolve(), destination.resolve()
    if destination.is_relative_to(REPO):
        raise ValueError('Private test copies must remain outside the repository')
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Original and corrected sources must be separate non-overlapping trees')
    # Verify all expected input hashes before creating or modifying any destination.
    verify_source(source)
    files = {}
    for name, expected_hash in LOCK['sha256'].items():
        if (source / name).is_symlink():
            raise ValueError('Unexpected symlink in original sources')
        data = (source / name).read_bytes()
        if digest(data) != expected_hash:
            raise ValueError('Original source changed during verification')
        if name in REPLACEMENTS:
            before, after = REPLACEMENTS[name]
            if data.count(before) != 1 or after in data:
                raise ValueError(f'Expected exactly one original insert_one: {name}')
            data = data.replace(before, after, 1)
        files[name] = data
    if destination.exists():
        return verify_test_copy(destination)  # Idempotent: never rewrite or repair a modified tree.
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + destination.name + '-', dir=destination.parent))
    try:
        for name, data in files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o600)
        (staging / MARKER).write_text(json.dumps(metadata(files), indent=2, ensure_ascii=False) + '\n')
        (staging / MARKER).chmod(0o600)
        verify_test_copy(staging)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging)  # Only our newly-created staging directory, never source/destination data.
        raise
    verify_source(source)
    return verify_test_copy(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    result = apply_patch(args.source, args.destination)
    print(json.dumps({'mode': result['mode'], 'patch_id': result['patch_id'],
                      'changed_files': result['changed_files'], 'destination': str(args.destination.resolve())}))


if __name__ == '__main__':
    main()
