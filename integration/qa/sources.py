"""Portable verification of private QA copies using the existing source lock."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCK = json.loads((REPO / 'integration/chat/source.lock.json').read_text(encoding='utf-8'))


def create_corrected(original, destination, patch_tools):
    destination.mkdir()
    files = {}
    for name, expected in LOCK['sha256'].items():
        data = (original / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Original provider hash differs: {name}')
        if name in patch_tools.REPLACEMENTS:
            before, after = patch_tools.REPLACEMENTS[name]
            if data.count(before) != 1:
                raise ValueError(f'Unexpected insertion code: {name}')
            data = data.replace(before, after, 1)
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[name] = data
    report = patch_tools.metadata(files)
    (destination / patch_tools.MARKER).write_text(json.dumps(report), encoding='utf-8')
    return verify_corrected(destination, patch_tools)


def verify_corrected(source, patch_tools):
    expected_names = set(LOCK['sha256']) | {patch_tools.MARKER}
    actual = {p.relative_to(source).as_posix() for p in source.rglob('*')
              if p.is_file() or p.is_symlink()}
    if actual != expected_names:
        raise ValueError('Unexpected files in private QA source copy')
    files = {}
    for name, expected in LOCK['sha256'].items():
        path = source / name
        if path.is_symlink():
            raise ValueError('Provider source must be a regular file')
        data = path.read_bytes()
        original = data
        if name in patch_tools.REPLACEMENTS:
            before, after = patch_tools.REPLACEMENTS[name]
            if data.count(after) != 1 or before in data:
                raise ValueError(f'Unexpected test patch: {name}')
            original = data.replace(after, before, 1)
        if hashlib.sha256(original).hexdigest() != expected:
            raise ValueError(f'Provider source changed beyond the test patch: {name}')
        files[name] = data
    marker = source / patch_tools.MARKER
    report = patch_tools.metadata(files)
    if marker.is_symlink() or json.loads(marker.read_text(encoding='utf-8')) != report:
        raise ValueError('Invalid private QA source metadata')
    return report
