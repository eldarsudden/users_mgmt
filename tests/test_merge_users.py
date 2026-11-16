"""Check account merge behavior, including explicit revocation and inheritance."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

from ansible.errors import AnsibleFilterError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("users_mgmt_merge", ROOT / "filter_plugins/merge_users.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
merge_users = MODULE.merge_users


class MergeUsersTests(unittest.TestCase):
    def test_inherit_fields_and_override_environment_keys(self):
        common = [{"name": "kerimov", "uid": 2001, "groups": ["wheel"],
                   "ssh_keys": ["common-key"], "sudo": ["ALL"], "sudo_nopasswd": True}]
        result = merge_users(common, [{"name": "kerimov", "ssh_keys": ["prod-key"]}])
        self.assertEqual(result, [dict(common[0], ssh_keys=["prod-key"])])

    def test_host_overrides_environment_without_losing_common_fields(self):
        result = merge_users(
            [{"name": "kerimov", "uid": 2001, "shell": "/bin/bash", "ssh_keys": ["common"]}],
            [{"name": "kerimov", "ssh_keys": ["prod"], "sudo_nopasswd": True}],
            [{"name": "kerimov", "ssh_keys": ["host"], "sudo_nopasswd": False}],
        )
        self.assertEqual(result, [{"name": "kerimov", "uid": 2001, "shell": "/bin/bash",
                                   "ssh_keys": ["host"], "sudo_nopasswd": False}])

    def test_explicit_empty_values_are_not_replaced_by_defaults(self):
        result = merge_users(
            [{"name": "kerimov", "groups": ["wheel"], "ssh_keys": ["key"],
              "sudo": ["ALL"], "sudo_nopasswd": True, "comment": "Old comment"}],
            [{"name": "kerimov", "groups": [], "ssh_keys": [], "sudo": [],
              "sudo_nopasswd": False, "comment": ""}],
        )
        self.assertEqual(result, [{"name": "kerimov", "groups": [], "ssh_keys": [],
                                   "sudo": [], "sudo_nopasswd": False, "comment": ""}])

    def test_new_accounts_and_order_and_inputs_are_preserved(self):
        sources = ([{"name": "a", "groups": ["wheel"]}, {"name": "b"}],
                   [{"name": "b", "uid": 2002}, {"name": "c"}],
                   [{"name": "a", "comment": "Override"}, {"name": "d"}])
        original = deepcopy(sources)
        result = merge_users(*sources)
        self.assertEqual([user["name"] for user in result], ["a", "b", "c", "d"])
        result[0]["groups"].append("other")
        self.assertEqual(sources, original)

    def test_duplicate_names_are_rejected_within_each_source(self):
        for index in range(3):
            sources = [[], [], []]
            sources[index] = [{"name": "a"}, {"name": "a"}]
            with self.subTest(index=index), self.assertRaises(AnsibleFilterError):
                merge_users(*sources)

    def test_malformed_sources_do_not_expose_account_values(self):
        for source in (None, {}, "secret-marker", ["secret-marker"], [{}],
                       [{"name": ""}], [{"name": 123}], [{"password": "secret-marker"}]):
            with self.subTest(source=source):
                with self.assertRaises(AnsibleFilterError) as failure:
                    merge_users([], source)
                self.assertNotIn("secret-marker", str(failure.exception))

    def test_null_fields_reach_normal_role_validation(self):
        self.assertEqual(merge_users([{"name": "a", "uid": 2001}], [{"name": "a", "uid": None}]),
                         [{"name": "a", "uid": None}])

    def test_explicit_deletion_is_preserved(self):
        self.assertEqual(merge_users([{"name": "a", "uid": 2001}],
                                     [{"name": "a", "state": "absent", "remove": False}]),
                         [{"name": "a", "uid": 2001, "state": "absent", "remove": False}])

    def test_empty_sources_are_a_noop(self):
        self.assertEqual(merge_users([], [], []), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
