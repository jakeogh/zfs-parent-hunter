#!/usr/bin/env python3

import pprint
import sys
import os
import subprocess
import pickle
import time
from pathlib import Path
from math import inf
import click

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def run_command(command, verbose=False, shell=True, expected_exit_code=0, stdin=None, ignore_exit=False):
    output = ''
    if verbose:
        eprint("command:", '`' + command + '`')
        eprint("shell:", shell)
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=shell, stdin=stdin)
        if verbose:
            eprint("output:", output.decode('utf8'))
    except subprocess.CalledProcessError as error:
        if verbose:
            eprint("exit code:", error.returncode, error.output)
        if error.returncode == expected_exit_code:
            return output
        elif ignore_exit:
            return output
        eprint("command:", command)
        eprint("exit code:", error.returncode, error.output)
        raise error

    return output


def print_match(obj_id, parent_id, pad, verbose):
   if verbose:
       print("id:", obj_id, "parent:", parent_id, end=pad+'\n')
   else:
       print(obj_id)


@click.command()
@click.argument("fs", type=str, nargs=1)
@click.argument("parents", type=int, nargs=-1)
@click.option("--start", type=int, default=1)
@click.option("--end", default=inf)
@click.option("--verbose", is_flag=True)
@click.option("--debug", is_flag=True)
@click.option("--load-pickle", type=str)
def find_parents(fs, parents, start, end, verbose, debug, load_pickle):
    initial_key_count = 0
    pad = 25 * ' '

    if not load_pickle:
        timestamp = str(time.time())
        data_dir = Path(os.path.expanduser("~/.zfs_parent_hunter"))
        data_dir.mkdir(exist_ok=True)
        data_file = Path("_".join(['parent_map', fs, timestamp, str(os.getpid()), '.pickle']))
        data_pickle = data_dir / data_file
        data_pickle.parent.mkdir(exist_ok=True)
        parent_map = {}
    else:
        data_pickle = Path(load_pickle)
        with open(data_pickle, 'rb') as fh:
            parent_map = pickle.load(fh)
            initial_key_count = len(parent_map.keys())

    assert len(fs.split()) == 1
    if verbose:
        eprint("looking for parent(s):", parents)
    obj_id = start
    while obj_id <= end:
        if verbose:
            eprint("checking id:", obj_id, end=pad+'\r', flush=True)
        if obj_id in parent_map.keys():
            parent_id = parent_map[obj_id]
            if parent_id in parents:
                print_match(obj_id, parent_id, pad, verbose)

            obj_id += 1
            continue

        if (len(parent_map.keys()) % 20) == 0 and parent_map.keys() and len(parent_map.keys()) != initial_key_count:
            if debug: eprint("saving:", data_pickle)
            with open(data_pickle, 'wb') as fh:
                pickle.dump(parent_map, fh)

        command = " ".join(["zdb", "-L", "-dddd", fs, str(obj_id)])
        output = run_command(command, shell=True, verbose=debug, ignore_exit=True)

        if len(output) == 0:
            parent_map[obj_id] = None
        else:
            if b'parent' not in output:
                parent_map[obj_id] = None
                obj_id += 1
                continue

        for line in output.splitlines():
            line = line.decode('utf8')
            if '\tparent\t' in line:
                parent_id = int(line.split()[-1])
                assert obj_id not in parent_map.keys()
                parent_map[obj_id] = parent_id
                if parent_id in parents:
                    print_match(obj_id, parent_id, pad, verbose)
        if debug:
            eprint(obj_id, "len(output):", len(output))

        obj_id += 1


if __name__ == "__main__":
    find_parents()

