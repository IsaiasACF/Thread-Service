"""Render deployment files locally; no network, no cluster writes."""
import argparse
import getpass
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image', required=True, help='ghcr.io/isaiasacf/thread-service@sha256:...')
parser.add_argument('--host', required=True, help='Confirmed DNS hostname pointing at Traefik')
parser.add_argument('--secret-file', type=Path, help='Prompt privately and create a new Secret file outside the repository/OneDrive')
args = parser.parse_args()
if not re.fullmatch(r'ghcr\.io/isaiasacf/thread-service@sha256:[0-9a-f]{64}', args.image):
    parser.error('Use the immutable GHCR digest from the successful publication job')
if len(args.host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p) for p in args.host.split('.')) or '.' not in args.host or 'pending' in args.host.lower():
    parser.error('A confirmed DNS hostname is required')
root = Path(__file__).resolve().parents[1]
out = root / 'k8s/rendered'
out.mkdir(mode=0o700, exist_ok=True)
docs = list(yaml.safe_load_all(subprocess.check_output(['kubectl','kustomize',str(root/'k8s')],text=True)))
for d in docs:
    if d['kind'] == 'Deployment':
        for c in d['spec']['template']['spec']['containers']:
            if c['image'].startswith('ghcr.io/isaiasacf/thread-service:'):
                c['image'] = args.image
ing = yaml.safe_load((root/'k8s/templates/ingress.yaml.example').read_text())
ing['spec']['rules'][0]['host'] = args.host
docs.append(ing)
(out/'workloads.yaml').write_text(yaml.safe_dump_all(docs, sort_keys=False))
if args.secret_file:
    target = args.secret_file.expanduser().resolve()
    if root in target.parents or 'onedrive' in str(target).lower():
        parser.error('Store the Secret outside the repository and OneDrive')
    if not target.parent.is_dir():
        parser.error('Create a private parent directory for the Secret first')
    if target.exists():
        parser.error('Existing Secret file preserved; remove it explicitly to generate another')
    values = {}
    for key in ('MONGO_INITDB_ROOT_USERNAME','MONGO_INITDB_ROOT_PASSWORD','RABBITMQ_DEFAULT_USER','RABBITMQ_DEFAULT_PASS'):
        value = getpass.getpass(f'{key}: ')
        if not value: parser.error('Credentials must not be empty')
        values[key] = value
    values['THREAD_MONGODB_URL'] = 'mongodb://{}:{}@thread-mongodb:27017/threads?authSource=admin'.format(*[quote(values[k],safe='') for k in ('MONGO_INITDB_ROOT_USERNAME','MONGO_INITDB_ROOT_PASSWORD')])
    values['THREAD_RABBITMQ_URL'] = 'amqp://{}:{}@thread-rabbitmq:5672/%2F'.format(*[quote(values[k],safe='') for k in ('RABBITMQ_DEFAULT_USER','RABBITMQ_DEFAULT_PASS')])
    with open(target, 'x', opener=lambda p,f: os.open(p,f,0o600)) as f:
        yaml.safe_dump({'apiVersion':'v1','kind':'Secret','metadata':{'name':'thread-secrets','namespace':'grupo-threads'},'type':'Opaque','stringData':values},f,sort_keys=False)
print('Generated ignored files in k8s/rendered/. No cluster operation performed.')
