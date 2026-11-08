"""Validate Compose syntax and actual build directories without exposing expanded env."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    command = ['docker', 'compose', '--env-file', str(args.env_file), '-f',
               str(Path(__file__).with_name('compose.yaml')), 'config', '--format', 'json']
    # Expanded output contains the temporary AMQP password: never print or save it.
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise SystemExit('Compose configuration failed; inspect its private env locally')
    config = json.loads(result.stdout)
    contexts = [service['build']['context'] for service in config['services'].values() if 'build' in service]
    if not all(Path(context).is_dir() for context in contexts):
        raise SystemExit('A Compose build directory does not exist; check source path encoding')
    network = config['networks']['microsvcs']
    assert network['name'] == 'microsvcs' and network['external'] is True
    for service in config['services'].values():
        assert 'container_name' not in service
        assert all(port.get('host_ip') == '127.0.0.1' for port in service.get('ports', []))
    print(f'Compose syntax, {len(contexts)} real build contexts, microsvcs and loopback published ports verified.')


if __name__ == '__main__':
    main()
