"""Regression of source integrity and the boundary around our own Docker resources."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('final_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def source(tmp_path):
    (tmp_path / 'app.py').write_text('immutable upstream\n')
    lock = {'sha256': {'app.py': hashlib.sha256((tmp_path / 'app.py').read_bytes()).hexdigest()}}
    return tmp_path, lock


def test_expected_source_is_verified_without_modification(source):
    directory, lock = source
    before = (directory / 'app.py').read_bytes()
    runner.prep.verify_external(directory, lock)
    assert (directory / 'app.py').read_bytes() == before


@pytest.mark.parametrize('change', ['modified', 'missing', 'extra', 'symlink'])
def test_rejects_unexpected_sources(source, change):
    directory, lock = source
    if change == 'modified':
        (directory / 'app.py').write_text('unapproved')
    elif change == 'missing':
        (directory / 'app.py').unlink()
    elif change == 'extra':
        (directory / 'extra.py').write_text('unapproved')
    else:
        original = directory / 'app.py'; original.rename(directory / 'backing.py'); original.symlink_to(directory / 'backing.py')
    with pytest.raises(ValueError):
        runner.prep.verify_external(directory, lock)


@pytest.mark.parametrize('action', ['stop','start','restart','pause','unpause'])
def test_fault_controls_require_explicit_own_services(action):
    config = {'services': {'chat-messages': {}}}
    with pytest.raises(ValueError): runner.validate_selection(action, [], config)
    with pytest.raises(ValueError): runner.validate_selection(action, ['foreign-project'], config)
    runner.validate_selection(action, ['chat-messages'], config)


@pytest.mark.parametrize('names', [[], ['chat-users','chat-messages'], ['foreign-project']])
def test_container_resolution_cannot_escape_project(names):
    with pytest.raises(ValueError):
        runner.validate_selection('id', names, {'services': {'chat-users':{},'chat-messages':{}}})


def test_no_volume_deletion_or_arbitrary_action_is_exposed():
    text = (HERE / 'run.py').read_text()
    assert "'--volumes'" not in text and "'-v'" not in text
    assert "'prune'" not in text and "'rm'" not in text
    assert "'project'" in text and "'--project-name'" in text
