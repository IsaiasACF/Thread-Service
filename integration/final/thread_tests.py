"""Run the existing Thread Service test target against this project's own infrastructure."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('final_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    private = runner.prep.verify(directory)
    config = runner.configuration(directory)
    image = private['CHAT_PROJECT_NAME'] + '-thread-tests'
    subprocess.run(['docker','build','--target','test','-t',image,str(HERE.parents[1])],check=True)
    env = dict(os.environ, THREAD_TEST_MONGODB_URL='mongodb://chat-threads-db:27017',
        THREAD_TEST_RABBITMQ_URL='amqp://'+private['CHAT_RABBIT_USER']+':'+private['CHAT_RABBIT_PASSWORD']+'@chat-rabbitmq:5672/%2F')
    raise SystemExit(subprocess.run(['docker','run','--rm','--network',config['networks']['chat-data']['name'],
        '--env','THREAD_TEST_MONGODB_URL','--env','THREAD_TEST_RABBITMQ_URL',image], env=env).returncode)


if __name__ == '__main__':
    main()
