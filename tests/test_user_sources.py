"""Resolve layered inputs through Ansible without executing account-changing tasks."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = os.environ.get("ANSIBLE_PLAYBOOK", "ansible-playbook")


class UserSourcesTests(unittest.TestCase):
    def run_play(self, directory, variables=None, expected=None, example=False):
        directory = Path(directory)
        play = [{
            "hosts": "all" if example else "localhost",
            "gather_facts": False,
            "vars": variables or {},
            "tasks": [
                {"name": "Load role defaults and filters without modifying accounts",
                 "ansible.builtin.import_role": {"name": str(ROOT)}, "when": False},
                {"name": "Verify resolved account inputs",
                 "ansible.builtin.assert": {"that": [
                     "users_mgmt_users == expected_by_host[inventory_hostname]" if example
                     else "users_mgmt_users == expected_users",
                     "users_mgmt_users | type_debug == 'list'",
                 ]}},
            ],
        }]
        if not example:
            play[0]["vars"]["expected_users"] = expected
        playbook = directory / "check.yml"
        playbook.write_text(json.dumps(play))
        inventory = directory / "inventory.yml" if example else ROOT / "tests/inventory.yml"
        env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(directory / "local"),
                   ANSIBLE_REMOTE_TEMP=str(directory / "remote"), ANSIBLE_NOCOLOR="1")
        result = subprocess.run([ANSIBLE, "-i", str(inventory), str(playbook)],
                                text=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_layered_defaults_preserve_types_and_explicit_revocation(self):
        variables = {
            "users_mgmt_common_users": [{"name": "a", "uid": 2001, "groups": ["wheel"],
                                          "ssh_keys": ["common"], "sudo_nopasswd": True}],
            "users_mgmt_env_users": [{"name": "a", "ssh_keys": ["prod"], "sudo": ["ALL"]}],
            "users_mgmt_host_users": [{"name": "a", "ssh_keys": [], "sudo_nopasswd": False},
                                       {"name": "b", "uid": 2002}],
        }
        expected = [{"name": "a", "uid": 2001, "groups": ["wheel"], "ssh_keys": [],
                     "sudo": ["ALL"], "sudo_nopasswd": False}, {"name": "b", "uid": 2002}]
        with tempfile.TemporaryDirectory(prefix="users-mgmt-sources-") as directory:
            self.run_play(directory, variables, expected)

    def test_direct_users_input_remains_authoritative(self):
        variables = {"users_mgmt_users": [{"name": "direct", "uid": 2001}],
                     "users_mgmt_common_users": [{"name": "common"}],
                     "users_mgmt_env_users": [{"name": "env"}]}
        with tempfile.TemporaryDirectory(prefix="users-mgmt-direct-") as directory:
            self.run_play(directory, variables, [{"name": "direct", "uid": 2001}])

    def test_example_inventory_merges_environment_and_each_host(self):
        with tempfile.TemporaryDirectory(prefix="users-mgmt-example-") as directory:
            project = Path(directory) / "project"
            shutil.copytree(ROOT / "examples/all-hosts", project)
            common = yaml.safe_load((project / "group_vars/all.yml").read_text())["users_mgmt_common_users"][0]
            inventory = yaml.safe_load((project / "inventory.yml").read_text())
            extras = inventory["all"]["hosts"]["el9.example.com"]["users_mgmt_host_users"]
            host_values = yaml.safe_load((project / "host_vars/el10.example.com.yml").read_text())["users_mgmt_host_users"]
            expected = {
                "el9.example.com": [dict(common, comment="Deployment account for this inventory")] + extras,
                "el10.example.com": [dict(common, comment="Deployment account on el10.example.com")] + host_values[1:],
            }
            self.run_play(project, {"expected_by_host": expected}, example=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
