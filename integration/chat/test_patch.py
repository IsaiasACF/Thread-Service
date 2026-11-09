"""File-level patch regression, not simulated service integration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from apply_test_patch import apply_patch, verify_test_copy, verify_mode, LOCK, MARKER, REPLACEMENTS, REPO
from prepare import verify_source
from probe import validate_creation


@pytest.fixture
def original(tmp_path):
    location = os.environ.get('CHAT_TEST_ORIGINAL_SOURCE')
    if not location:
        pytest.skip('Prepare the immutable sources and set CHAT_TEST_ORIGINAL_SOURCE')
    source = Path(location)
    verify_source(source)
    target = tmp_path / 'original'
    for name in LOCK['sha256']:
        file = target / name
        file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, file)
    return target


def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def test_exact_three_edits_original_unchanged_and_idempotent(original, tmp_path):
    before = snapshot(original)
    target = tmp_path / 'corrected'
    result = apply_patch(original, target)
    after = snapshot(target)
    assert snapshot(original) == before
    assert set(after) == set(before) | {MARKER}
    changed = {name for name in before if before[name] != after[name]}
    assert changed == set(REPLACEMENTS)
    for name in changed:
        old, new = REPLACEMENTS[name]
        assert after[name] == before[name].replace(old, new, 1)
    assert result == verify_test_copy(target)
    times = {p: p.stat().st_mtime_ns for p in target.rglob('*') if p.is_file()}
    assert apply_patch(original, target) == result
    assert times == {p: p.stat().st_mtime_ns for p in times}
    assert snapshot(original) == before
    assert verify_mode(original, 'original')['mode'] == 'original'
    assert verify_mode(target, 'corrected')['mode'] == 'corrected'
    with pytest.raises(ValueError):
        verify_mode(target, 'original')
    with pytest.raises(ValueError):
        verify_mode(original, 'corrected')


@pytest.mark.parametrize('name', list(REPLACEMENTS))
def test_rejects_unexpected_original_before_creating_copy(original, tmp_path, name):
    file = original / name
    file.write_bytes(file.read_bytes() + b'\n# unexpected source change\n')
    before = snapshot(original)
    destination = tmp_path / 'must-not-exist'
    with pytest.raises(ValueError):
        apply_patch(original, destination)
    assert not destination.exists()
    assert snapshot(original) == before


@pytest.mark.parametrize('kind', ['file', 'empty-directory'])
def test_never_overwrites_unrecognized_destination(original, tmp_path, kind):
    destination = tmp_path / 'foreign'
    if kind == 'file':
        destination.write_text('unrelated file')
    else:
        destination.mkdir()
    with pytest.raises(ValueError):
        apply_patch(original, destination)
    assert destination.read_text() == 'unrelated file' if kind == 'file' else list(destination.iterdir()) == []


@pytest.mark.parametrize('kind', ['same', 'child', 'parent', 'repository'])
def test_rejects_overlap_and_repository_destinations(original, tmp_path, kind):
    destinations = {'same': original, 'child': original / 'copy', 'parent': tmp_path,
                    'repository': REPO / 'integration/chat/forbidden-test-copy'}
    before = snapshot(original)
    with pytest.raises(ValueError):
        apply_patch(original, destinations[kind])
    assert snapshot(original) == before


@pytest.mark.parametrize('kind', ['code', 'metadata', 'extra-file', 'symlink'])
def test_rejects_tampered_copy_without_repairing_it(original, tmp_path, kind):
    target = tmp_path / 'corrected'
    apply_patch(original, target)
    if kind == 'code':
        file = target / 'messages/app/main.py'
        file.write_bytes(file.read_bytes() + b'\n# unapproved\n')
    elif kind == 'metadata':
        file = target / MARKER
        data = json.loads(file.read_text()); data['patch_id'] = 'unapproved'
        file.write_text(json.dumps(data))
    elif kind == 'extra-file':
        (target / 'unrelated.txt').write_text('unexpected')
    else:
        file = target / 'users/app/main.py'; file.unlink(); file.symlink_to(original / 'users/app/main.py')
    before = snapshot(target)
    with pytest.raises(ValueError):
        apply_patch(original, target)
    assert snapshot(target) == before


def test_rejects_symlink_inputs(original, tmp_path):
    file = original / 'users/app/main.py'
    backing = tmp_path / 'same-bytes.py'; backing.write_bytes(file.read_bytes())
    file.unlink(); file.symlink_to(backing)
    with pytest.raises(ValueError, match='symlink'):
        apply_patch(original, tmp_path / 'copy')


@pytest.mark.parametrize('operation,service', [('createUser','users'),('createChannel','channels'),('sendMessage','messages')])
def test_creation_policy_requires_real_success_and_preserves_original_failure(operation, service):
    value = {'id': 'api-confirmed-id'}
    good = {'success': True, 'response': {'data': {operation: value}}}
    bad = {'success': False, 'response': {'data': None, 'errors': [{'extensions': {'code':'BAD_UPSTREAM_RESPONSE','service':service,'httpStatus':500}}]}}
    validate_creation('corrected', operation, value, good)
    validate_creation('original', operation, None, bad)
    with pytest.raises(AssertionError): validate_creation('corrected', operation, None, bad)
    with pytest.raises(AssertionError): validate_creation('original', operation, value, good)
    with pytest.raises(AssertionError): validate_creation('corrected', operation, {'id':''}, good)
    with pytest.raises(AssertionError): validate_creation('corrected', operation, {'id':'invented'}, good)
    with pytest.raises(AssertionError): validate_creation('corrected', operation, value, {'success':True,'response':bad['response']})


def test_corrected_probe_forbids_administrative_recovery(tmp_path):
    output = tmp_path / 'must-not-be-written.json'
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('probe.py')),
        '--manifest', str(tmp_path / 'nonexistent.json'), '--output', str(output),
        '--allow-local-writes', '--mode', 'corrected', '--diagnose-upstream'], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'forbidden in corrected mode' in result.stderr
    assert not output.exists()
