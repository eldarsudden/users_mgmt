"""Merge account definitions by name without combining individual field values."""

from copy import deepcopy

try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

from ansible.errors import AnsibleFilterError

try:
    STRING_TYPES = (basestring,)
except NameError:
    STRING_TYPES = (str,)


def merge_users(common_users, *overrides):
    """Apply lists in order; explicit values, including false and [], replace fields."""
    result = []
    positions = {}
    for source_index, source in enumerate((common_users,) + overrides, start=1):
        if not isinstance(source, list):
            raise AnsibleFilterError(
                "users_mgmt_merge_users: source {0} must be a list".format(source_index)
            )
        seen = set()
        for entry_index, entry in enumerate(source, start=1):
            location = "source {0}, entry {1}".format(source_index, entry_index)
            if not isinstance(entry, Mapping):
                raise AnsibleFilterError(
                    "users_mgmt_merge_users: {0} must be a mapping".format(location)
                )
            name = entry.get("name")
            if not isinstance(name, STRING_TYPES) or not name:
                raise AnsibleFilterError(
                    "users_mgmt_merge_users: {0} requires a non-empty name".format(location)
                )
            if name in seen:
                raise AnsibleFilterError(
                    "users_mgmt_merge_users: {0} repeats a name in the same source".format(location)
                )
            seen.add(name)
            values = deepcopy(dict(entry))
            if name in positions:
                result[positions[name]].update(values)
            else:
                positions[name] = len(result)
                result.append(values)
    return result


class FilterModule(object):
    def filters(self):
        return {"users_mgmt_merge_users": merge_users}
