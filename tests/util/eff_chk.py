#! /bin/env python3

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess as sub
import yaml
import os
import re
from time import sleep


### CONFIG
# test_dir = Path("tests/spread/integration/metapixel")
# test_dir = Path("tests/spread/integration/hello")
# test_dir = Path("tests/spread/integration/xz-utils")
test_dir = Path("tests/spread/integration/git")
# test_dir = Path('tests/spread/integration/flask')
# test_dir = Path("tests/spread/integration/libgif7")
# test_dir = Path('tests/spread/integration/libpng16-16t64')
shell = Path("/bin/bash")
overrides_path = Path(__file__).parent / "overrides"
lib_path = Path(__file__).parent / "../spread/lib"
release_path = Path(__file__).parent / "../../"
ignore_dirs = True


### SUPPORT
def load_tree(event_list):
    tree = set()

    for path, event in event_list:
        # print(path, path.name == "log")
        if path.name == "log":
            continue

        # # todo make better exclude mechanism
        # if path == Path("usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"):
        #     continue

        if "DELETE" in event:
            tree.remove(path)
            continue

        if "OPEN" in event:
            tree.add(path)
            continue

        if "CREATE" in event:
            tree.add(path)
            continue

        if "MODIFY" in event:
            tree.add(path)
            continue

        if "ACCESS" in event:
            tree.add(path)
            continue

    return tree


def parse_inotify(event_log, rootfs_path):
    marker_path = (rootfs_path / "../log").resolve()
    inotify_record = event_log.splitlines()

    marker_idx = None
    events = list()

    for line in inotify_record:
        if match := re.match("(\S+)\s(\S+)\s(\S+)", line):
            parent, event_type, filename = match.groups()

            full_path = Path(parent) / filename

            if ignore_dirs and full_path.is_dir():
                continue

            if rootfs_path in full_path.parents:
                rel_path = full_path.relative_to(rootfs_path)
                events.append((rel_path, event_type))

            if full_path == marker_path:
                marker_idx = len(events)

    # marker_idx -= 1
    setup_events = events[:marker_idx]
    task_events = events[marker_idx:]

    return setup_events, task_events


def parse_du(du_output):
    # prase_line = lambda *arr: (arr[0], arr[1])
    # du_table = [prase_line(line.split()) for line in du_output.splitlines()]

    du_mapping = dict()

    for line in du_output.splitlines():
        cols = line.split()

        if len(cols) != 2:
            print("Warning: skipping line", repr(line))
            continue

        name = cols[1].lstrip("./")

        du_mapping[Path(name)] = int(cols[0])

    return du_mapping


### EXECUTE
with open(test_dir / "task.yaml") as fh:
    test_task = yaml.safe_load(fh)


with TemporaryDirectory() as tempdir_str:
    tempdir_path = Path(tempdir_str)

    rootfs_path = tempdir_path / "rootfs"
    rootfs_path.mkdir()

    environ = os.environ.copy()
    environ["TEMP_PATH"] = str(rootfs_path)
    environ["PROJECT_PATH"] = str(release_path)
    environ["PATH"] = f"{overrides_path}:" + f"{lib_path}:" + environ["PATH"]

    sub.check_output(["cp", "-r", f"{test_dir}/.", tempdir_str])

    inotify_proc = sub.Popen(
        ["inotifywait", "-rm", tempdir_path], stdout=sub.PIPE, text=True
    )

    matrix = {}
    defaults = {}
    for key, value in test_task["environment"].items():
        print(key, value)

        split_key = key.split("/")

        if len(split_key) == 2:
            var, name = split_key

            if name not in matrix:
                matrix[name] = {}

            matrix[name][var] = value

        else:
            defaults[key] = value

    # print(matrix)

    for matrix_name, matrix_vars in matrix.items():
        print("Running", matrix_name)
        sub.run(
            ["unshare", "-r", shell, "-c", "set -x\n" + test_task["execute"]],
            env={**environ, **defaults, **matrix_vars},
            cwd=tempdir_str,
        )

    inotify_proc.terminate()

    # comment me, used for testing with out analysis
    # sub.Popen(["ls", "-lashR"], cwd=rootfs_path)

    sleep(1)
    exit()

    inotify_log = inotify_proc.stdout.read()
    setup_events, task_events = parse_inotify(inotify_log, rootfs_path)

    setup_tree = load_tree(setup_events)
    task_tree = load_tree(task_events)

    du_proc = sub.Popen(["du", "-b", "-a"], cwd=rootfs_path, stdout=sub.PIPE, text=True)
    du_log = du_proc.stdout.read()
    du_result = parse_du(du_log)

    # for path, event in setup_events:
    #     print("setup", event, path)

    # for path, event in task_events:
    #     print("task", event, path)

    ## ANALYSIS
    min_rootfs = task_tree.intersection(setup_tree)
    file_efficiency = 100 * len(min_rootfs) / len(setup_tree)

    setup_rootfs_size = sum([du_result[file] for file in setup_tree])
    min_rootfs_size = sum([du_result[file] for file in min_rootfs])
    space_efficiency = 100 * min_rootfs_size / setup_rootfs_size

    print(f"\nSetup RootFS: {setup_rootfs_size} bytes")
    for path in setup_tree:
        print("\t", path)

    print(f"\nMin RootFS: {min_rootfs_size} bytes")
    for path in min_rootfs:
        print("\t", path)
    print("file efficiency", file_efficiency)
    print("space efficiency", space_efficiency)
