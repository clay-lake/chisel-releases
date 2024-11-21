#! /bin/env python3

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess as sub
import yaml
import os
import re
from time import sleep


### CONFIG
test_dir = Path("tests/spread/integration/metapixel")
shell = Path("/bin/bash")
lib_path = Path(__file__).parent / "../spread/lib"
release_path = Path(__file__).parent / "../../"
ignore_dirs = True


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
    environ["PATH"] = f"{lib_path}:" + environ["PATH"]

    sub.check_output(["cp", "-r", f"{test_dir}/.", tempdir_str])

    matrix = {}
    defaults = {}

    if "environment" in test_task:
        for key, value in test_task["environment"].items():
            split_key = key.split("/")

            if len(split_key) == 2:
                var, name = split_key

                if name not in matrix:
                    matrix[name] = {}

                matrix[name][var] = value

            else:
                defaults[key] = value
    else:
        matrix = {"Default": {}}

    for matrix_name, matrix_vars in matrix.items():
        task_env = {**environ, **defaults, **matrix_vars}
        print(f"Running {matrix_name} environment.")
        sub.run(
            ["unshare", "-r", shell, "-c", "set -x\n" + test_task["execute"]],
            env=task_env,
            cwd=tempdir_str,
        )
