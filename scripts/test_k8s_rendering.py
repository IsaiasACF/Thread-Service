"""Offline deployment packaging checks; no cluster or credentials required."""
from copy import deepcopy
from pathlib import Path
import runpy

import pytest
import yaml

from scripts import prepare_k8s

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'ghcr.io/isaiasacf/thread-service@sha256:' + 'a' * 64
HOST = 'render-test.invalid'  # Reserved test hostname, never a deployment assignment.


def source_documents():
    resources = yaml.safe_load((ROOT / 'k8s/kustomization.yaml').read_text())['resources']
    base = [doc for name in resources
            for doc in yaml.safe_load_all((ROOT / 'k8s' / name).read_text())]
    ingress = yaml.safe_load((ROOT / 'k8s/templates/ingress.yaml.example').read_text())
    return base, ingress


def rendered_documents():
    return prepare_k8s.render_documents(*source_documents(), IMAGE, HOST)


def test_stages_partition_resources_and_preserve_dependencies(tmp_path):
    docs = rendered_documents()
    prepare_k8s.write_manifests(docs, tmp_path)
    files = sorted((tmp_path / 'stages').glob('*.yaml'))
    assert [p.name for p in files] == [
        '01-config.yaml', '02-mongodb.yaml', '03-rabbitmq.yaml', '04-api.yaml',
        '05-worker.yaml', '06-ingress.yaml', '07-hpa.yaml',
    ]
    stages = [list(yaml.safe_load_all(path.read_text())) for path in files]
    flattened = [d for stage in stages for d in stage]
    keys = [(d['kind'], d['metadata']['name']) for d in flattened]
    assert len(keys) == len(set(keys)) == 11
    assert flattened == list(yaml.safe_load_all((tmp_path / 'workloads.yaml').read_text()))
    assert set(keys) == {(d['kind'], d['metadata']['name']) for d in docs}
    assert all(d['metadata']['namespace'] == 'grupo-threads' for d in flattened)
    assert [d['kind'] for d in stages[3]] == ['Service', 'Deployment']
    assert [d['kind'] for d in stages[6]] == ['HorizontalPodAutoscaler']
    for stage_index, container_name in [(3, 'api'), (4, 'worker')]:
        deployment = next(d for d in stages[stage_index] if d['kind'] == 'Deployment')
        container = deployment['spec']['template']['spec']['containers'][0]
        assert container['name'] == container_name and container['image'] == IMAGE
        assert {e['valueFrom']['secretKeyRef']['name'] for e in container['env']} == {'thread-secrets'}
    assert stages[5][0]['spec']['rules'][0]['host'] == HOST
    hpa = stages[6][0]['spec']
    assert hpa['scaleTargetRef']['name'] == stages[3][1]['metadata']['name']
    # No real Secret belongs to either form of the workload output.
    assert not any(d['kind'] == 'Secret' for d in flattened)
    prepare_k8s.write_manifests(docs, tmp_path)
    assert len(list((tmp_path / 'stages').glob('*.yaml'))) == 7


def test_image_substitution_preserves_resources_and_inputs():
    base, ingress = source_documents()
    before = deepcopy(base)
    docs = prepare_k8s.render_documents(base, ingress, IMAGE, HOST)
    assert base == before
    assert ingress['spec']['rules'][0]['host'] == 'PENDING_PUBLIC_HOST'
    for original, rendered in zip(base, docs):
        expected = deepcopy(original)
        if expected['kind'] == 'Deployment' and expected['metadata']['name'] in ('thread-api', 'thread-worker'):
            expected['spec']['template']['spec']['containers'][0]['image'] = IMAGE
        assert rendered == expected  # Includes all resource budgets, probes and references.


@pytest.mark.parametrize('problem', ['duplicate', 'missing', 'unexpected', 'namespace'])
def test_invalid_resource_sets_fail_before_writing(tmp_path, problem):
    docs = rendered_documents()
    if problem == 'duplicate':
        docs.append(deepcopy(docs[0]))
    elif problem == 'missing':
        docs.pop()
    elif problem == 'unexpected':
        docs.append({'kind': 'ConfigMap', 'metadata': {'name': 'unexpected'}})
    else:
        docs[0]['metadata']['namespace'] = 'other-namespace'
    with pytest.raises(ValueError):
        prepare_k8s.write_manifests(docs, tmp_path)
    assert not list(tmp_path.iterdir())


def test_cli_creates_stages_without_prompting_for_credentials(tmp_path, monkeypatch):
    base, ingress = source_documents()
    (tmp_path / 'k8s/templates').mkdir(parents=True)
    (tmp_path / 'k8s/templates/ingress.yaml.example').write_text(yaml.safe_dump(ingress))
    monkeypatch.setattr(prepare_k8s, 'ROOT', tmp_path)
    monkeypatch.setattr(prepare_k8s.subprocess, 'check_output',
                        lambda *args, **kwargs: yaml.safe_dump_all(base))
    monkeypatch.setattr(prepare_k8s.getpass, 'getpass',
                        lambda *args: pytest.fail('No credentials should be requested'))
    monkeypatch.setattr('sys.argv', ['prepare_k8s.py', '--image', IMAGE, '--host', HOST])
    prepare_k8s.main()
    output = tmp_path / 'k8s/rendered'
    assert len(list((output / 'stages').glob('*.yaml'))) == 7
    docs = list(yaml.safe_load_all((output / 'workloads.yaml').read_text()))
    assert len(docs) == 11 and all(d['kind'] != 'Secret' for d in docs)


def test_rabbitmq_tcp_checks_survive_stage_rendering(tmp_path):
    prepare_k8s.write_manifests(rendered_documents(), tmp_path)
    docs = list(yaml.safe_load_all((tmp_path / 'stages/03-rabbitmq.yaml').read_text()))
    broker = next(d for d in docs if d['kind'] == 'Deployment')
    container = broker['spec']['template']['spec']['containers'][0]
    assert 'livenessProbe' not in container
    for name in ('startupProbe', 'readinessProbe'):
        probe = container[name]
        assert probe['tcpSocket']['port'] == 5672
        assert 'exec' not in probe
    startup = container['startupProbe']
    assert startup['failureThreshold'] * startup['periodSeconds'] >= 600


@pytest.mark.parametrize('problem', [None, 'exec_startup', 'wrong_port', 'rabbit_liveness', 'api_liveness'])
def test_validator_scopes_probe_policy_to_rabbitmq(monkeypatch, problem):
    base, _ = source_documents()
    rabbit = next(d for d in base if d['kind'] == 'Deployment' and d['metadata']['name'] == 'thread-rabbitmq')
    container = rabbit['spec']['template']['spec']['containers'][0]
    if problem == 'exec_startup':
        container['startupProbe'].pop('tcpSocket')
        container['startupProbe']['exec'] = {'command': ['rabbitmq-diagnostics', '-q', 'ping']}
    elif problem == 'wrong_port':
        container['readinessProbe']['tcpSocket']['port'] = 15672
    elif problem == 'rabbit_liveness':
        container['livenessProbe'] = deepcopy(container['readinessProbe'])
    elif problem == 'api_liveness':
        api = next(d for d in base if d['kind'] == 'Deployment' and d['metadata']['name'] == 'thread-api')
        api['spec']['template']['spec']['containers'][0].pop('livenessProbe')
    monkeypatch.setattr('subprocess.check_output', lambda *args, **kwargs: yaml.safe_dump_all(base))
    if problem is None:
        runpy.run_path(str(ROOT / 'scripts/validate_k8s.py'), run_name='__main__')
    else:
        with pytest.raises(AssertionError):
            runpy.run_path(str(ROOT / 'scripts/validate_k8s.py'), run_name='__main__')


def test_mongodb_probe_policy_survives_stage_rendering(tmp_path):
    prepare_k8s.write_manifests(rendered_documents(), tmp_path)
    docs = list(yaml.safe_load_all((tmp_path / 'stages/02-mongodb.yaml').read_text()))
    statefulset = next(d for d in docs if d['kind'] == 'StatefulSet')
    container = statefulset['spec']['template']['spec']['containers'][0]
    for name in ('startupProbe', 'livenessProbe'):
        assert container[name]['tcpSocket'] == {'port': 27017}
        assert 'exec' not in container[name]
    assert 'mongosh' in container['readinessProbe']['exec']['command']
    assert container['readinessProbe']['timeoutSeconds'] == 15


@pytest.mark.parametrize('problem', [None, 'exec_liveness', 'tcp_readiness',
                                      'short_readiness', 'aggressive_liveness', 'wrong_startup_port'])
def test_validator_enforces_mongodb_probe_policy(monkeypatch, problem):
    base, _ = source_documents()
    mongo = next(d for d in base if d['kind'] == 'StatefulSet')
    container = mongo['spec']['template']['spec']['containers'][0]
    if problem == 'exec_liveness':
        container['livenessProbe'].pop('tcpSocket')
        container['livenessProbe']['exec'] = deepcopy(container['readinessProbe']['exec'])
    elif problem == 'tcp_readiness':
        container['readinessProbe'].pop('exec')
        container['readinessProbe']['tcpSocket'] = {'port': 27017}
    elif problem == 'short_readiness':
        container['readinessProbe']['timeoutSeconds'] = 5
    elif problem == 'aggressive_liveness':
        container['livenessProbe']['failureThreshold'] = 1
    elif problem == 'wrong_startup_port':
        container['startupProbe']['tcpSocket']['port'] = 5672
    monkeypatch.setattr('subprocess.check_output', lambda *args, **kwargs: yaml.safe_dump_all(base))
    if problem is None:
        runpy.run_path(str(ROOT / 'scripts/validate_k8s.py'), run_name='__main__')
    else:
        with pytest.raises(AssertionError):
            runpy.run_path(str(ROOT / 'scripts/validate_k8s.py'), run_name='__main__')
