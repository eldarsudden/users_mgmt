"""Destructive fixture tests: run as root ONLY inside a disposable EL9/EL10 host."""

import os
from pathlib import Path
import re
import subprocess


HERE = Path(__file__).resolve().parent


def run(playbook, *options, unchanged=False):
    command = ["ansible-playbook", "-i", str(HERE.parent / "inventory.yml"),
               str(HERE / playbook), *options]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    if unchanged:
        changes = re.findall(r"\bchanged=(\d+)", result.stdout)
        if not changes or any(int(count) != 0 for count in changes):
            raise SystemExit("Expected an idempotent run with changed=0")


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Run only as root in a disposable EL9/EL10 test environment")
    os.environ["ANSIBLE_NOCOLOR"] = "1"
    os.environ["ANSIBLE_STDOUT_CALLBACK"] = "default"
    os.environ["ANSIBLE_CONFIG"] = str(HERE.parents[1] / "ansible.cfg")
    run("converge.yml")
    run("verify.yml")
    run("add_membership.yml")
    run("converge.yml", unchanged=True)
    run("converge.yml", "--check", unchanged=True)
    run("verify.yml", "-e", "expect_extra=true")
    run("revoke.yml")
    run("delete.yml")
