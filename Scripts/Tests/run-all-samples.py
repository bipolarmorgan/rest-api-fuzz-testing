# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pathlib
import sys
import os
import json
import urllib.parse
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
cli_dir = os.path.join(cur_dir, '..', '..', 'cli')
sys.path.append(cli_dir)
from raft_sdk.raft_service import RaftCLI, RaftJobConfig, RaftApiException

def find_files():
    configs = {}
    fs = ['dredd', 'zap', 'compile', 'test', 'fuzz', 'schemathesis']
    for root, _, files in os.walk(cli_dir):
        for f in fs:
            j = f + '.json'
            if j in files:
                if not configs.get(root):
                    configs[root] = {}
                configs[root][f] = os.path.join(root, j)

            y = f + '.yaml'
            if y in files:
                if not configs.get(root):
                    configs[root] = {}
                configs[root][f] = os.path.join(root, y)

    return configs

def wait(configs, count, task_name, job_id_key):
    completed_count = 0
    completed_counted = {}
    while completed_count < count:
        for c in configs:
            if configs[c].get(task_name):
                try:
                    status = cli.job_status(configs[c][job_id_key])
                except RaftApiException as ex:
                    if ex.status_code != 404:
                        raise ex
                completed, _ = cli.is_completed(status)
                if completed and not completed_counted.get(configs[c][job_id_key]):
                    completed_counted[configs[c][job_id_key]] = True
                    completed_count += 1
                    print('Jobs completed: ' + configs[c][job_id_key] + " job index : " + str(completed_count) + ' out of ' + str(count))
                cli.print_status(status)
        for _ in range(1,9) :
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(1)
        print('.')


def compile_and_dredd_and_schemathesis(cli, configs):
    compile_count = 0
    dredd_count = 0
    schemathesis_count = 0
    for c in configs:
        if configs[c].get('compile'):
            compile_job_config = RaftJobConfig(file_path=configs[c]['compile'], substitutions=subs)
            compile_job = cli.new_job(compile_job_config)
            configs[c]['compile_job_id'] = compile_job['jobId'] 
            compile_count = compile_count + 1

        if configs[c].get('dredd'):
            dredd_job_config = RaftJobConfig(file_path=configs[c]['dredd'], substitutions=subs)
            dredd_job = cli.new_job(dredd_job_config)
            configs[c]['dredd_job_id'] = dredd_job['jobId'] 
            dredd_count = dredd_count + 1

        if configs[c].get('schemathesis'):
            schemathesis_job_config = RaftJobConfig(file_path=configs[c]['schemathesis'], substitutions=subs)
            schemathesis_job = cli.new_job(schemathesis_job_config)
            configs[c]['schemathesis_job_id'] = schemathesis_job['jobId'] 
            schemathesis_count = schemathesis_count + 1

    print('Compiling all ' + str(compile_count) + ' and running Dredd on ' + str(dredd_count) + ' and running Schemathesis on ' +  str(schemathesis_count) + ' samples ...')
    wait(configs, compile_count, 'compile', 'compile_job_id')
    wait(configs, dredd_count, 'dredd', 'dredd_job_id')
    wait(configs, schemathesis_count, 'schemathesis', 'schemathesis_job_id')


def test(cli, configs):
    test_count = 0
    for c in configs:
        if configs[c].get('test'):
            subs['{compile.jobId}'] = configs[c]['compile_job_id']
            test_job_config = RaftJobConfig(file_path=configs[c]['test'], substitutions=subs)
            test_job = cli.new_job(test_job_config)
            configs[c]['test_job_id'] = test_job['jobId'] 
            test_count = test_count + 1
    print('Testing all ' + str(test_count) + ' samples ...')
    wait(configs, test_count, 'test', 'test_job_id')


def fuzz_and_zap(cli, configs):
    fuzz_count = 0
    zap_count = 0
    for c in configs:
        if configs[c].get('fuzz'):
            subs['{compile.jobId}'] = configs[c]['compile_job_id']
            fuzz_job_config = RaftJobConfig(file_path=configs[c]['fuzz'], substitutions=subs)
            fuzz_job = cli.new_job(fuzz_job_config)
            configs[c]['fuzz_job_id'] = fuzz_job['jobId'] 
            fuzz_count = fuzz_count + 1

        if configs[c].get('zap'):
            zap_job_config = RaftJobConfig(file_path=configs[c]['zap'], substitutions=subs)
            zap_job = cli.new_job(zap_job_config)
            configs[c]['zap_job_id'] = zap_job['jobId'] 
            zap_count = zap_count + 1

    print('Fuzzing all ' + str(fuzz_count) + ' and ZAP: ' + str(zap_count) + ' samples ...')
    wait(configs, fuzz_count, 'fuzz', 'fuzz_job_id')
    wait(configs, zap_count, 'zap', 'zap_job_id')

if __name__ == "__main__":
    cli = RaftCLI()
    subs = {
       '{defaults.deploymentName}' : cli.definitions.deployment,
       '{ci-run}': 'all-samples'
    }
    configs = find_files()
    compile_and_dredd_and_schemathesis(cli, configs)
    test(cli, configs)
    fuzz_and_zap(cli, configs)
