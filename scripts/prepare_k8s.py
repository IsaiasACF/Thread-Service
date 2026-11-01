"""Render ordered deployment stages locally; no network or cluster writes."""
import argparse
from copy import deepcopy
import getpass
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    '01-config.yaml': [('ConfigMap', 'thread-config')],
    '02-mongodb.yaml': [('Service', 'thread-mongodb'),
                        ('PersistentVolumeClaim', 'thread-mongodb-data'),
                        ('StatefulSet', 'thread-mongodb')],
    '03-rabbitmq.yaml': [('Service', 'thread-rabbitmq'), ('Deployment', 'thread-rabbitmq')],
    '04-api.yaml': [('Service', 'thread-api'), ('Deployment', 'thread-api')],
    '05-worker.yaml': [('Deployment', 'thread-worker')],
    '06-ingress.yaml': [('Ingress', 'thread-api')],
    '07-hpa.yaml': [('HorizontalPodAutoscaler', 'thread-api')],
}


def render_documents(base, ingress, image, host):
    """Resolve API/worker image and ingress host without mutating the source."""
    docs = deepcopy(base) + [deepcopy(ingress)]
    for doc in docs:
        if doc['kind'] == 'Deployment' and doc['metadata']['name'] in ('thread-api', 'thread-worker'):
            for container in doc['spec']['template']['spec']['containers']:
                if container['name'] in ('api', 'worker'):
                    container['image'] = image
    docs[-1]['spec']['rules'][0]['host'] = host
    return docs


def write_manifests(docs, output):
    """Each resource belongs to one stage; consolidated output is an alternative."""
    by_key = {(d['kind'], d['metadata']['name']): d for d in docs}
    expected = {key for keys in STAGES.values() for key in keys}
    if len(by_key) != len(docs) or set(by_key) != expected:
        raise ValueError('Duplicate, missing or unexpected resources in deployment stages')
    if any(d['metadata']['namespace'] != 'grupo-threads' for d in docs):
        raise ValueError('All deployment stages must target grupo-threads')
    stages = output / 'stages'
    stages.mkdir(mode=0o700, parents=True, exist_ok=True)
    ordered = []
    for filename, keys in STAGES.items():
        stage = [by_key[key] for key in keys]
        ordered.extend(stage)
        (stages / filename).write_text(yaml.safe_dump_all(stage, sort_keys=False))
    (output / 'workloads.yaml').write_text(yaml.safe_dump_all(ordered, sort_keys=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='ghcr.io/isaiasacf/thread-service@sha256:...')
    parser.add_argument('--host', required=True, help='Confirmed DNS hostname pointing at Traefik')
    parser.add_argument('--secret-file', type=Path,
                        help='Prompt privately and create a new Secret outside the repository/OneDrive')
    args = parser.parse_args()
    if not re.fullmatch(r'ghcr\.io/isaiasacf/thread-service@sha256:[0-9a-f]{64}', args.image):
        parser.error('Use the immutable GHCR digest from the successful publication job')
    if (len(args.host) > 253 or '.' not in args.host or 'pending' in args.host.lower()
            or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
                       for part in args.host.split('.'))):
        parser.error('A confirmed DNS hostname is required')
    target = None
    if args.secret_file:
        target = args.secret_file.expanduser().resolve()
        if ROOT in target.parents or 'onedrive' in str(target).lower():
            parser.error('Store the Secret outside the repository and OneDrive')
        if not target.parent.is_dir():
            parser.error('Create a private parent directory for the Secret first')
        if target.exists():
            parser.error('Existing Secret file preserved; use it without --secret-file')
    base = list(yaml.safe_load_all(subprocess.check_output(
        ['kubectl', 'kustomize', str(ROOT / 'k8s')], text=True)))
    ingress = yaml.safe_load((ROOT / 'k8s/templates/ingress.yaml.example').read_text())
    docs = render_documents(base, ingress, args.image, args.host)
    write_manifests(docs, ROOT / 'k8s/rendered')
    if target:
        values = {}
        for key in ('MONGO_INITDB_ROOT_USERNAME', 'MONGO_INITDB_ROOT_PASSWORD',
                    'RABBITMQ_DEFAULT_USER', 'RABBITMQ_DEFAULT_PASS'):
            value = getpass.getpass(f'{key}: ')
            if not value:
                parser.error('Credentials must not be empty')
            if key == 'RABBITMQ_DEFAULT_USER' and value == 'guest':
                parser.error('Use a RabbitMQ application user other than guest')
            values[key] = value
        values['THREAD_MONGODB_URL'] = (
            'mongodb://{}:{}@thread-mongodb:27017/threads?authSource=admin'.format(
                *[quote(values[k], safe='') for k in
                  ('MONGO_INITDB_ROOT_USERNAME', 'MONGO_INITDB_ROOT_PASSWORD')]))
        values['THREAD_RABBITMQ_URL'] = 'amqp://{}:{}@thread-rabbitmq:5672/%2F'.format(
            *[quote(values[k], safe='') for k in ('RABBITMQ_DEFAULT_USER', 'RABBITMQ_DEFAULT_PASS')])
        with open(target, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
            yaml.safe_dump({'apiVersion': 'v1', 'kind': 'Secret',
                            'metadata': {'name': 'thread-secrets', 'namespace': 'grupo-threads'},
                            'type': 'Opaque', 'stringData': values}, stream, sort_keys=False)
    print('Generated 7 stages in k8s/rendered/stages/ and alternative workloads.yaml. '
          'No cluster operation performed.')


if __name__ == '__main__':
    main()
