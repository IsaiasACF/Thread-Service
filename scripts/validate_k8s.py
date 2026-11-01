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
def totals(extra_api=0):
    result = [0, 0, 0, 0, 0]
    for d in workloads:
        count = 3 + extra_api if d['metadata']['name'] == 'thread-api' else d['spec']['replicas']
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
        assert all(p in c for p in ('startupProbe', 'readinessProbe', 'livenessProbe', 'resources'))
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
assert by_key['Deployment','thread-api']['spec']['strategy']['rollingUpdate'] == {'maxSurge': 0, 'maxUnavailable': 1}
for name in ('thread-worker', 'thread-rabbitmq'):
    assert by_key['Deployment', name]['spec']['strategy']['type'] == 'Recreate'
assert len([d for d in docs if d['kind'] == 'PersistentVolumeClaim']) == 1
assert by_key['PersistentVolumeClaim','thread-mongodb-data']['spec']['resources']['requests']['storage'] == '1Gi'
for extra in (0, 1, 3):
    t = totals(extra)
    assert all(a <= b for a,b in zip(t, [10,1000,1024,2000,2048])), t
    print(f'Maximum + {extra} terminating API: pods={t[0]}, requests={t[1]}m/{t[2]}Mi, limits={t[3]}m/{t[4]}Mi')
print(f'Validated {len(docs)} resources and references. Secret and public host are external prerequisites.')
