"""Verify QA copies and detect accidental changes to pinned provider sources."""
import importlib
import os
from pathlib import Path

import pytest

from integration.qa.sources import create_corrected, verify_corrected


@pytest.fixture
def corrected(tmp_path, monkeypatch):
    original = Path(os.environ['THREAD_QA_SOURCE'])
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'chat'))
    patch_tools = importlib.import_module('apply_test_patch')
    target = tmp_path / 'corrected'
    report = create_corrected(original, target, patch_tools)
    return target, patch_tools, report


def test_copy_preserves_verified_patch_metadata(corrected):
    target, tools, report = corrected
    assert verify_corrected(target, tools) == report
    assert len(report['changed_files']) == 3


@pytest.mark.parametrize('fault', ['extra-file', 'changed-code', 'changed-metadata'])
def test_copy_rejects_changes(corrected, fault):
    target, tools, _ = corrected
    path = {
        'extra-file': target / 'unexpected.txt',
        'changed-code': target / 'users/app/main.py',
        'changed-metadata': target / tools.MARKER,
    }[fault]
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError):
        verify_corrected(target, tools)
