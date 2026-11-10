"""Operate only the Compose project owned by a private final-integration directory."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('final_prepare', HERE / 'prepare.py')
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


def command(directory):
    return ['docker', 'compose', '--project-name', json.loads((directory / 'owner.json').read_text())['project'], '--env-file', str(directory / 'compose.env'),
            '-f', str(HERE.parent / 'chat/compose.yaml'), '-f', str(HERE / 'compose.yaml')]


def configuration(directory):
    result = subprocess.run(command(directory) + ['config', '--format', 'json'], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Compose config failed; expanded private values are intentionally hidden')
    config = json.loads(result.stdout)
    env = prep.verify(directory)
    svc = config['services']
    for name in ('users','channels','messages'):
        assert Path(svc['chat-'+name]['build']['context']).resolve() == (Path(env['CHAT_BASE_SOURCE']) / name).resolve(), 'Unexpected build source override'
    for name, service in [('integrals','integrals'),('polls','polls-api')]:
        assert Path(svc[service]['build']['context']).resolve() == Path(env[name.upper()+'_SOURCE_DIR']).resolve(), 'Unexpected external source override'
    assert 'gateway' not in svc and 'frontend' not in svc, 'Duplicate platform services'
    assert config['networks']['microsvcs']['name'] == 'microsvcs' and config['networks']['microsvcs']['external']
    assert svc['chat-gateway']['environment']['MESSAGES_BASE_URL'] == svc['polls-api']['environment']['MESSAGES_BASE_URL'] == svc['integrals']['environment']['MESSAGES_URL']
    assert svc['chat-gateway']['environment']['USERS_BASE_URL'] == svc['chat-threads']['environment']['THREAD_USERS_URL'] == svc['integrals']['environment']['USERS_URL']
    assert svc['chat-gateway']['environment']['MESSAGES_BASE_URL'] == svc['chat-threads']['environment']['THREAD_MESSAGES_URL']
    assert svc['chat-gateway']['environment']['INTEGRALS_BASE_URL'] == 'http://chat-it-integrals:8000'
    assert svc['chat-gateway']['environment']['POLLS_BASE_URL'] == 'http://chat-it-polls:8004'
    assert all('container_name' not in item and all(p.get('host_ip') == '127.0.0.1' for p in item.get('ports', [])) for item in svc.values())
    assert all(Path(item['build']['context']).is_dir() for item in svc.values() if 'build' in item)
    return config


def validate_selection(action, selected, config):
    if any(name not in config['services'] for name in selected):
        raise ValueError('Only services in this owned Compose project are allowed')
    if action in ('stop','start','restart','pause','unpause') and not selected:
        raise ValueError('Select explicit own services for fault/restart operations')
    if action == 'id' and len(selected) != 1:
        raise ValueError('Select exactly one owned service')
    if action in ('down','snapshot','config') and selected:
        raise ValueError('This action does not take service arguments')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('action', choices=('config','up','down','ps','stop','start','restart','pause','unpause','id','snapshot'))
    parser.add_argument('services', nargs='*')
    args = parser.parse_args()
    directory = args.directory.resolve()
    prep.verify(directory)
    config = configuration(directory)
    try:
        validate_selection(args.action, args.services, config)
    except ValueError as error:
        parser.error(str(error))
    cmd = command(directory)
    if args.action == 'config':
        print('Verified sources, single platform, shared upstreams, DNS/ports, private secrets and microsvcs; services=' + str(len(config['services'])))
        return
    if args.action == 'up':
        exists = subprocess.run(['docker','network','inspect','microsvcs'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if exists.returncode:
            subprocess.run(['docker','network','create','microsvcs'], check=True, stdout=subprocess.DEVNULL)
        cmd += ['up','--build','-d','--wait','--wait-timeout','240'] + args.services
    elif args.action == 'id':
        cmd += ['ps','-q'] + args.services
    elif args.action == 'snapshot':
        ids = subprocess.check_output(cmd + ['ps','-aq'], text=True).split()
        records = json.loads(subprocess.check_output(['docker','inspect',*ids], text=True)) if ids else []
        # Select safe fields only; never write container environment or credentials.
        print(json.dumps([{'id':r['Id'],'service':r['Config']['Labels']['com.docker.compose.service'],'image':r['Image'],
            'startedAt':r['State']['StartedAt'],'status':r['State']['Status'],'health':r['State'].get('Health',{}).get('Status'),
            'volumes':[{'name':v.get('Name'),'destination':v['Destination']} for v in r['Mounts'] if v['Type']=='volume']} for r in records], indent=2))
        return
    else:
        cmd += [args.action] + args.services
    raise SystemExit(subprocess.run(cmd).returncode)


if __name__ == '__main__':
    main()
