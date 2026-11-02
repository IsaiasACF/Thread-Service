"""Offline cross-resource and quota validation; never connects to Kubernetes."""
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
docs = list(yaml.safe_load_all(subprocess.check_output(
    ['kubectl', 'kustomize', str(ROOT / 'k8s')], text=True)))
by_key = {(d['kind'], d['metadata']['name']): d for d in docs}
assert len(by_key) == len(docs), 'Duplicate resources'
assert all(d['metadata']['namespace'] == 'grupo-threads' for d in docs)
workloads = [d for d in docs if d['kind'] in ('Deployment', 'StatefulSet')]
services = [d for d in docs if d['kind'] == 'Service']
config = by_key['ConfigMap', 'thread-config']['data']
assert config['THREAD_USERS_URL'] == 'http://users.servicios-base.svc.cluster.local:8000'
assert config['THREAD_MESSAGES_URL'] == 'http://messages.servicios-base.svc.cluster.local:8000'
def cpu(value):
    return int(value[:-1]) if value.endswith('m') else int(value) * 1000
def memory(value):
    return int(value[:-2]) * (1024 if value.endswith('Gi') else 1)
def totals(api_replicas):
    result = [0, 0, 0, 0, 0]
    for d in workloads:
        count = api_replicas if d['metadata']['name'] == 'thread-api' else d['spec']['replicas']
        result[0] += count
        for c in d['spec']['template']['spec']['containers']:
            r = c['resources']
            for index, (scope, resource, parse) in enumerate([
                ('requests','cpu',cpu), ('requests','memory',memory),
                ('limits','cpu',cpu), ('limits','memory',memory)], 1):
                result[index] += count * parse(r[scope][resource])
    return result
for d in workloads:
    s = d['spec']
    labels = s['template']['metadata']['labels']
    assert s['selector']['matchLabels'].items() <= labels.items()
    for c in s['template']['spec']['containers']:
        assert all(p in c for p in ('startupProbe', 'readinessProbe', 'resources'))
        if d['metadata']['name'] == 'thread-rabbitmq' and c['name'] == 'rabbitmq':
            # RabbitMQ's Kubernetes guidance uses TCP readiness and no liveness CLI.
            assert 'livenessProbe' not in c, 'RabbitMQ must not use liveness restarts'
            for name in ('startupProbe', 'readinessProbe'):
                probe = c[name]
                assert probe.get('tcpSocket') == {'port': 5672}, (name, 'Expected AMQP TCP check')
                assert not any(action in probe for action in ('exec', 'httpGet', 'grpc'))
                assert probe['timeoutSeconds'] >= 5
                assert probe['periodSeconds'] >= 10
            assert c['startupProbe']['failureThreshold'] * c['startupProbe']['periodSeconds'] >= 600
            assert c['readinessProbe']['failureThreshold'] >= 3
        else:
            assert 'livenessProbe' in c, 'Other workloads still require liveness'
        if d['metadata']['name'] == 'thread-mongodb' and c['name'] == 'mongodb':
            for name in ('startupProbe', 'livenessProbe'):
                probe = c[name]
                assert probe.get('tcpSocket') == {'port': 27017}, (name, 'Expected MongoDB TCP check')
                assert not any(action in probe for action in ('exec', 'httpGet', 'grpc'))
                assert probe['timeoutSeconds'] >= 5
            startup = c['startupProbe']
            assert startup['failureThreshold'] * startup['periodSeconds'] >= 600
            live = c['livenessProbe']
            assert live['periodSeconds'] >= 30 and live['failureThreshold'] >= 6
            ready = c['readinessProbe']
            assert ready.get('exec', {}).get('command') == [
                'mongosh', '--quiet', '--eval', 'quit(db.adminCommand({ping:1}).ok ? 0 : 1)']
            assert not any(action in ready for action in ('tcpSocket', 'httpGet', 'grpc'))
            assert (ready['timeoutSeconds'], ready['periodSeconds'], ready['failureThreshold']) == (15, 20, 3)
        assert cpu(c['resources']['limits']['cpu']) <= 1000
        assert memory(c['resources']['limits']['memory']) <= 1024
        for source in c.get('envFrom', []):
            assert ('ConfigMap', source['configMapRef']['name']) in by_key
        for env in c.get('env', []):
            if 'valueFrom' in env:
                assert env['valueFrom']['secretKeyRef']['name'] == 'thread-secrets'
    for vol in s['template']['spec'].get('volumes', []):
        if 'persistentVolumeClaim' in vol:
            assert ('PersistentVolumeClaim', vol['persistentVolumeClaim']['claimName']) in by_key
for service in services:
    assert service['spec'].get('type', 'ClusterIP') == 'ClusterIP'
    assert any(service['spec']['selector'].items() <= d['spec']['template']['metadata']['labels'].items() for d in workloads)
hpa = by_key['HorizontalPodAutoscaler', 'thread-api']['spec']
assert hpa['minReplicas'] == 2 and hpa['maxReplicas'] == 3
assert hpa['metrics'][0]['resource']['target']['averageUtilization'] == 70
assert ('Deployment', hpa['scaleTargetRef']['name']) in by_key
assert by_key['Deployment', 'thread-api']['spec']['replicas'] == hpa['minReplicas']
for name in ('thread-api', 'thread-worker', 'thread-rabbitmq'):
    assert by_key['Deployment', name]['spec']['strategy'] == {'type': 'Recreate'}
assert len([d for d in docs if d['kind'] == 'PersistentVolumeClaim']) == 1
assert by_key['PersistentVolumeClaim','thread-mongodb-data']['spec']['resources']['requests']['storage'] == '1Gi'
# Recreate waits for the old revision to terminate before creating its replacement.
# Sequential controlled upgrades only: not a bound for manual deletion or concurrent rollouts.
quota = [10, 1000, 1024, 2000, 2048]
initial = by_key['Deployment', 'thread-api']['spec']['replicas']
for label, api_replicas in (
    ('Initial', initial),
    ('HPA maximum', hpa['maxReplicas']),
    ('Recreate: old API revision terminating, no new API', hpa['maxReplicas']),
    ('Recreate: API stopped before new revision', 0),
    ('Recreate: new API revision, no old API', hpa['maxReplicas']),
):
    t = totals(api_replicas)
    assert all(a <= b for a, b in zip(t, quota)), (label, t)
    # Preserve at least 20% headroom in compute and pod quotas for controlled upgrades.
    assert all(a * 5 <= b * 4 for a, b in zip(t, quota)), (label, 'Insufficient headroom', t)
    remaining = [b - a for a, b in zip(t, quota)]
    used = [round(a / b * 100, 2) for a, b in zip(t, quota)]
    print(f'{label}: pods={t[0]}, requests={t[1]}m/{t[2]}Mi, limits={t[3]}m/{t[4]}Mi')
    print(f'  Used % (pods, request CPU/Mi, limit CPU/Mi): {used}; remaining: {remaining}')
print(f'Validated {len(docs)} resources and references. Secret and public host are external prerequisites.')
