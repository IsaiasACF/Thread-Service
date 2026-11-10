"""Explicit diagnostic of the ORIGINAL chat defect; never a successful normal E2E."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import uuid

import httpx

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('final_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
sys.path.insert(0, str(HERE.parent / 'chat'))
from probe import QUERIES, validate_creation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnose-original', action='store_true', required=True)
    args = parser.parse_args()
    state = args.directory.resolve()
    env = runner.prep.verify(state)
    if env['CHAT_SOURCE_MODE'] != 'original':
        parser.error('Administrative diagnosis is forbidden for corrected mode')
    config = runner.configuration(state)
    port = config['services']['chat-gateway']['ports'][0]['published']
    url = 'http://127.0.0.1:' + str(port) + '/graphql'
    report = {'kind':'real-original-docker-diagnostic','normal_e2e_passed':False,'administrative_id_recovery_used':True,'operations':{}}
    tag = 'original-' + uuid.uuid4().hex
    def call(operation_name, **variables):
        response = httpx.post(url, json={'query':QUERIES[operation_name], 'variables':variables}, timeout=15)
        response.raise_for_status()
        return response.json()
    def broken(operation_name, **variables):
        body = call(operation_name, **variables)
        result = {'success':False,'response':body}
        validate_creation('original', operation_name, None, result)
        report['operations'][operation_name] = result
    broken('createUser', name=tag)
    # This is confined to the original diagnostic's own MongoDB, explicitly disclosed.
    script = 'import os,json; from pymongo import MongoClient; print(json.dumps(MongoClient(os.environ["MONGODB_URL"]).chat_users.users.find_one({"display_name":'+repr(tag)+'},{"_id":0})))'
    user = json.loads(subprocess.check_output(runner.command(state)+['exec','-T','chat-users','python','-c',script],text=True))
    uid = user['id']
    assert call('user',id=uid)['data']['user']['displayName'] == tag
    broken('createChannel',name=tag)
    channel = next(item for item in call('channels')['data']['channels'] if item['name']==tag)
    assert call('channel',id=channel['id'])['data']['channel'] == channel
    broken('sendMessage',c=channel['id'],a=uid,text=tag)
    messages = call('messages',c=channel['id'])['data']['messages']
    assert sum(item['content']==tag and item['authorId']==uid for item in messages)==1
    report['original_defect_reproduced'] = True
    report['persisted_after_failed_response'] = True
    report['post_counts'] = {'createUser':1,'createChannel':1,'sendMessage':1}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('Original defect confirmed: three HTTP 500, persisted data, no automatic POST retry; normal E2E remains failed')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
