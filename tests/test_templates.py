"""Render access files through Ansible into temporary paths, without modifying accounts."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = os.environ.get("ANSIBLE_PLAYBOOK", "ansible-playbook")


class TemplateTests(unittest.TestCase):
    def render(self, account):
        with tempfile.TemporaryDirectory(prefix="users-mgmt-template-") as directory:
            output = Path(directory)
            tasks = []
            for filename in ["authorized_keys", "sudoers"]:
                options = {
                    "src": str(ROOT / "templates" / (filename + ".j2")),
                    "dest": str(output / filename),
                    "mode": "0600",
                }
                if filename == "sudoers" and shutil.which("visudo"):
                    options["validate"] = shutil.which("visudo") + " -cf %s"
                tasks.append({"ansible.builtin.template": options})
            play = [{
                "hosts": "localhost", "gather_facts": False,
                "vars": {"users_mgmt_user": account, "ansible_python_interpreter": sys.executable},
                "tasks": tasks,
            }]
            playbook = output / "playbook.yml"
            playbook.write_text(json.dumps(play))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=directory + "/local",
                       ANSIBLE_REMOTE_TEMP=directory + "/remote", ANSIBLE_NOCOLOR="1")
            result = subprocess.run(
                [ANSIBLE, "-i", str(ROOT / "tests/inventory.yml"), "-c", "local", str(playbook)],
                text=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            return {filename: (output / filename).read_text()
                    for filename in ["authorized_keys", "sudoers"]}

    def test_public_keys_and_passwordless_sudo(self):
        key = (ROOT / "tests/fixtures/test_ed25519.pub").read_text().strip()
        different_key = key.replace('WpPC', 'wPpc')
        result = self.render({"name": "svc.user", "ssh_keys": [key, key, different_key],
                              "sudo": ["/usr/bin/id"], "sudo_nopasswd": True})
        self.assertEqual(result["authorized_keys"], key + "\n" + different_key + "\n")
        self.assertIn("svc.user ALL=(ALL:ALL) NOPASSWD: /usr/bin/id\n", result["sudoers"])

    def test_empty_keys_and_password_required_sudo(self):
        result = self.render({"name": "deploy", "ssh_keys": [], "sudo": ["ALL"]})
        # Ansible 2.10 preserves the template's trailing newline for an empty loop.
        self.assertEqual(result["authorized_keys"].strip(), "")
        self.assertIn("deploy ALL=(ALL:ALL) PASSWD: ALL\n", result["sudoers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
