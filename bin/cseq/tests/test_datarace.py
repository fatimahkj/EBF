import pytest
import subprocess
import yaml
import os
import resource
import psutil

def memory_limit(max_mem):
    def decorator(f):
        def wrapper(*args, **kwargs):
            process = psutil.Process(os.getpid())
            prev_limits = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(
                resource.RLIMIT_AS, (
                     process.memory_info().rss + max_mem, -1
                )
            )
            result = f(*args, **kwargs)
            resource.setrlimit(resource.RLIMIT_AS, prev_limits)
            return result
        return wrapper
    return decorator

CSEQ_PATH = 'cseq.py'

PATH_TO_FILES = 'examples/downloads/ldv-races/'

ignore_list = set([
    # Most of these give syntax error on parsing, even with the --sv-comp flag
    # TODO: Fix the syntax error on cseq parsing (container_of), No need to do this, just work on the .i preprocessed files
    'race-2_1-container_of.c',
    'race-2_5b-container_of.c',
    'race-2_2-container_of.c',
    'race-3_1-container_of-global.c',
    'race-2_2b-container_of.c',
    'race-2_3b-container_of.c',
    'race-2_4-container_of.c',
    'race-2_4b-container_of.c',
    'race-2_5-container_of.c',
    'race-3_2-container_of-global.c',
    'race-3_2b-container_of-global.c',
    'race-2_3-container_of.c',
    '40_barrier_vf.c',
    '46_monabsex2_vs.c',
    '46_monabsex2_vs-b.c',
    '40_barrier_vf-b.c',
    # These ones below just take too long to run, so ignore
    'triangular-longer-2.c', 
    'triangular-longest-2.c'
    'fib_bench_longer-2.c',
    'fib_bench_longest-2.c'
])

special_params = {
    '39_rand_lock_p0_vs-b.c':       {'unwind': 2},
    '45_monabsex1_vs-b.c':          {'unwind': 2},
    'singleton-b.c':                {'rounds': 3},
    'race-4_2-thread_local_vars.c': {'rounds': 2},
    '48_ticket_lock_low_contention_vs-b.c' : {'rounds': 2},
    'fib_bench_longer-2.c' : {'rounds': 6, 'unwind' : 6},
    'fib_bench_longest-2.c' : {'rounds': 11, 'unwind' : 11},
    'fib_bench-2.c': {'rounds': 5, 'unwind': 5},
    'read_write_lock-2.c' : {'rounds': 2},
    'singleton_with-uninit-problems-b.c' : {'rounds': 3},
    'singleton.c' : {'rounds' : 4},
    'triangular-2.c' : {'rounds': 5, 'unwind': 5},
    'triangular-longer-2.c': {'rounds': 10, 'unwind': 10}, 
    'triangular-longest-2.c': {'rounds': 20, 'unwind': 20},
}

@pytest.mark.parametrize('input_filename, verdict', [
    ('race-1_1-join.i',  'SAFE'),
    ('race-1_2-join.i', 'UNSAFE'),
    ('race-1_2b-join.i', 'UNSAFE'),
    ('race-1_3-join.i', 'UNSAFE'),
    ('race-1_3b-join.i', 'UNSAFE'),
    ('race-4_1-thread_local_vars.i', 'SAFE'),
    ('race-4_2-thread_local_vars.i', 'SAFE'),
])
def test_datarace_short(input_filename, verdict):
    try:
        cmd = ['python3', '-m', 'cseq', '--sv-comp', '--data-race-check', '--backend', 'cbmc', '-i', PATH_TO_FILES + input_filename]
        print('Invoking: ', ' '.join(cmd))
        out = subprocess.check_output(cmd)
            
        if verdict == 'UNSAFE':
            assert 'UNSAFE' in out
        elif verdict == 'SAFE':
            assert 'SAFE' in out
    except subprocess.CalledProcessError as e:
        print(e.output)
        assert False


def load_yaml(folder='examples/downloads'):
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith('.yml'):
                path = os.path.join(root, file)
                yield path

def files_to_check():
    for yaml_path in load_yaml():
        example_data = yaml.load(open(yaml_path), Loader=yaml.FullLoader)
        base_path = os.path.sep.join(yaml_path.split(os.path.sep)[:-1])

        expected_global_verdict = 'SAFE'
        has_data_race = False

        file_to_check_basename = example_data['input_files']
        file_to_check = os.path.join(base_path, file_to_check_basename)
        
        if file_to_check_basename in ignore_list:
            continue

        for property in example_data["properties"]:
            if 'expected_verdict' in property:
                property_name = os.path.basename(property['property_file'])
                expected_verdict = property['expected_verdict']
                
                if expected_verdict is False:
                    expected_global_verdict = 'UNSAFE'
                if property_name == 'no-data-race.prp' and expected_verdict == False:
                    has_data_race = True

        if file_to_check_basename not in ignore_list:
            yield (file_to_check, expected_global_verdict, has_data_race)
    
@pytest.mark.slow
@pytest.mark.parametrize('input_filename, verdict, has_data_race', files_to_check())
def test_all(input_filename, verdict, has_data_race):
    try:
        cmd = ['python2', '-m', 'lazy-cseq', '-i', input_filename]
        cmd = ' '.join(cmd)
        cmd = 'ulimit -t 900 -m 7340032 ;' + cmd

        name = os.path.basename(input_filename)
        params = special_params[name] if name in special_params else {}
        for key in params.keys():
            cmd += ['--' + key, str(params[key])]

        out = subprocess.check_output(cmd, shell=True)

        if verdict == 'UNSAFE':
            assert 'UNSAFE' in out
        elif verdict == 'SAFE':
            assert 'SAFE' in out

        if has_data_race:
            # Gotta ask for Verification failed because in some examples
            # the unreachability counterexample is found first than the data
            # race issue and the unreach-call is not specified in the file
            # Ideally this info should be explicit in the yml files so we can differentiate correctly.
            assert 'Data race found' in out or 'VERIFICATION FAILED' in out

    except subprocess.CalledProcessError as e:
        print(e.output)
        assert False

