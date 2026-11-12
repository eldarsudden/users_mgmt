"""Run the actual Ansible assertions locally; never execute account-changing tasks."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = os.environ.get("ANSIBLE_PLAYBOOK", "ansible-playbook")


class ValidationTests(unittest.TestCase):
    def run_validation(self, users=None, groups=None, extra=None, valid=True, task="validate.yml"):
        variables = {
            "ansible_facts": {"os_family": "RedHat", "distribution_major_version": "9"},
            "users_mgmt_users": [] if users is None else users,
            "users_mgmt_groups": [] if groups is None else groups,
            "users_mgmt_protected_users": [],
        }
        variables.update(extra or {})
        # JSON is a YAML subset. No interpolated YAML or shell execution.
        play = [{
            "hosts": "localhost", "gather_facts": False,
            "vars": variables,
            "tasks": [{"import_tasks": str(ROOT / "tasks" / task)}],
        }]
        with tempfile.TemporaryDirectory(prefix="users-mgmt-validation-") as directory:
            playbook = Path(directory) / "playbook.yml"
            playbook.write_text(json.dumps(play))
            env = os.environ.copy()
            env.update({
                "ANSIBLE_LOCAL_TEMP": directory + "/local",
                "ANSIBLE_REMOTE_TEMP": directory + "/remote",
                "ANSIBLE_NOCOLOR": "1",
                "ANSIBLE_INVENTORY_UNPARSED_WARNING": "false",
            })
            result = subprocess.run(
                [ANSIBLE, "-i", str(ROOT / "tests/inventory.yml"), "-c", "local", str(playbook)],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
        if valid:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertEqual(result.returncode, 2, result.stdout)
        return result.stdout

    def test_defaults_are_a_noop(self):
        self.run_validation()

    def test_supported_account_attributes(self):
        self.run_validation(
            groups=[{"name": "operations", "gid": 2000}],
            users=[{
                "name": "deploy", "uid": 2001, "group": "operations",
                "groups": ["wheel"], "append": True, "comment": "Deployment",
                "shell": "/bin/bash", "home": "/srv/deploy", "create_home": True,
                "move_home": False, "system": False, "password": "$6$salt$hash",
                "password_lock": False, "update_password": "on_create", "expires": -1,
                "ssh_keys": [],
            }, {"name": "old_user", "state": "absent", "remove": False, "force": False}],
        )

    def test_bad_account_definitions(self):
        cases = [
            {"name": "root"}, {"name": "../escape"}, {"name": "bad\nname"},
            {"name": "deploy", "uid": 0}, {"name": "deploy", "uid": "1001"},
            {"name": "deploy", "state": "removed"},
            {"name": "deploy", "groups": "wheel"},
            {"name": "deploy", "groups": ["wheel,root"]},
            {"name": "deploy", "append": "false"},
            {"name": "deploy", "password": "plaintext"},
            {"name": "deploy", "password": "!\nsecret-password-marker"},
            {"name": "deploy", "home": "/"},
            {"name": "deploy", "shell": "bash"},
            {"name": "deploy", "ssh_keys": ["key\nsecond-key"]},
            {"name": "deploy", "ssh_keys": [123]},
            {"name": "deploy", "sudo": ["ALL\nroot ALL=(ALL) ALL"]},
            {"name": "deploy", "sudo_nopasswd": True},
            {"name": "deploy", "udpate_password": "always"},
            "deploy", {},
        ]
        for case in cases:
            with self.subTest(case=case):
                output = self.run_validation(users=[case], valid=False)
                self.assertNotIn("secret-password-marker", output)

    def test_bad_group_definitions(self):
        for group in [{"name": "root"}, {"name": "../bad"}, {"name": "team", "gid": 0},
                      {"name": "team", "system": "yes"}, {"name": "team", "typo": True}]:
            with self.subTest(group=group):
                self.run_validation(groups=[group], valid=False)

    def test_duplicates_and_protected_accounts(self):
        self.run_validation(users=[{"name": "deploy"}, {"name": "deploy"}], valid=False)
        self.run_validation(groups=[{"name": "team"}, {"name": "team"}], valid=False)
        self.run_validation(users=[{"name": "admin"}],
                            extra={"users_mgmt_protected_users": ["admin"]}, valid=False)

    def test_references_to_deleted_groups(self):
        for attributes in [{"group": "team"}, {"groups": ["team"]}]:
            self.run_validation(users=[dict(name="deploy", **attributes)],
                                groups=[{"name": "team", "state": "absent"}], valid=False)
        self.run_validation(users=[{"name": "deploy", "state": "absent", "group": "team"}],
                            groups=[{"name": "team", "state": "absent"}])

    def test_wrong_platform_and_variable_types(self):
        self.run_validation(extra={"ansible_facts": {
            "os_family": "Debian", "distribution_major_version": "12"}}, valid=False)
        self.run_validation(users="deploy", valid=False)
        self.run_validation(groups={}, valid=False)

    def test_sudo_field_without_requiring_local_sudo(self):
        self.run_validation(extra={"users_mgmt_user": {
            "name": "deploy", "sudo": ["/usr/bin/id"], "sudo_nopasswd": True,
        }}, task="validate_user.yml")


if __name__ == "__main__":
    if not shutil.which(ANSIBLE):
        raise SystemExit("ansible-playbook is required; activate the Ansible virtualenv first")
    unittest.main(verbosity=2)
