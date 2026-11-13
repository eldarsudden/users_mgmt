# users_mgmt

An Ansible role for managing local users on RHEL and compatible EL9/EL10 systems.
Uses only `ansible.builtin`; no additional collections are required.

## Compatibility

| Managed system | Default target Python | Minimum Ansible engine |
| --- | --- | --- |
| EL9 | 3.9 | ansible-base 2.10 |
| EL10 | 3.12 | ansible-core 2.16 |

The role syntax is compatible with Ansible 2.10. However, Ansible 2.10 does not
support EL10's default Python 3.12. The control node's Python version must also
be compatible with the installed Ansible engine. The minimum versions in the
table indicate technical compatibility.

The target host requires Python and `shadow-utils`. To manage sudo, it also needs
the `sudo` package with `/usr/sbin/visudo` and the standard inclusion of
`/etc/sudoers.d` from `/etc/sudoers`. The role does not install packages.
Run with `become: true` or as root. This role manages local accounts; their names
must not overlap with users provided by LDAP/AD/SSSD.

## Usage

Place this role at `roles/users_mgmt` in your Ansible project. The complete
example in this repository uses the following layout:

```text
examples/all-hosts/
├── playbook.yml
├── inventory.yml
├── group_vars/
│   └── all.yml
└── host_vars/
    └── el10.example.com.yml
```

### Playbook

The [playbook](examples/all-hosts/playbook.yml) uses `hosts: all` to apply the
role to every host in the inventory. The `all` group exists
automatically; hosts do not need to belong to another named group. Use this
example with EL9/EL10 hosts supported by the role.

```yaml
---
- name: Manage local accounts on every inventory host
  hosts: all
  become: true
  roles:
    - role: users_mgmt
```

### Where user definitions are stored

**Store the account definitions in `group_vars/all.yml` next to the playbook.**
Ansible loads this file automatically for every inventory host. In this example,
`users_mgmt_common_users` defines shared accounts, and `users_mgmt_users` combines
them with optional `users_mgmt_host_users` from each host's variables. The role
receives the resulting list. Its `defaults/main.yml` only contains empty defaults.

The supplied [group_vars/all.yml](examples/all-hosts/group_vars/all.yml):

```yaml
---
# Loaded automatically for every host targeted by this example's playbook.
users_mgmt_groups:
  - name: operations
    gid: 2000

users_mgmt_common_users:
  - name: deploy
    state: present
    uid: 2001
    group: operations
    comment: Shared account for all inventory hosts
    shell: /bin/bash

# Keep common accounts when a host defines extra accounts in inventory or host_vars.
users_mgmt_users: "{{ users_mgmt_common_users + (users_mgmt_host_users | default([])) }}"
```

| Artifact | Contents |
| --- | --- |
| `inventory.yml` | Hosts, connection settings, and optional per-host account lists |
| `group_vars/all.yml` | Shared user and group definitions, SSH key references, sudo rules, and optional Vault-encrypted variables |
| `public_keys/*.pub` | Optional public SSH keys referenced by `ssh_keys` |
| `host_vars/<inventory_hostname>.yml` | Additional accounts and settings specific to one host |

Keep these artifacts in your Ansible project repository. On managed hosts, the
role applies them to the local account database (`/etc/passwd`, `/etc/shadow`,
`/etc/group`, and `/etc/gshadow`), SSH files, and its sudoers drop-ins. The role
does not maintain a separate user database. Add SSH keys or a Vault-backed
password hash when login access is required.

The example explicitly concatenates common and host-specific user lists because
Ansible does not merge lists automatically. The default empty lists leave users
and groups unchanged. The role manages only explicitly listed entries; removing
an entry from a list does not delete it from the host.

### Run with the YAML inventory

The supplied [inventory.yml](examples/all-hosts/inventory.yml) defines the target hosts:

```yaml
---
all:
  vars:
    ansible_python_interpreter: /usr/bin/python3
  hosts:
    el9.example.com:
      users_mgmt_host_users:
        - name: audit_reader
          state: present
          uid: 2003
          group: operations
          comment: Audit reader on el9.example.com
          shell: /bin/bash
        - name: backup_operator
          state: present
          uid: 2004
          group: operations
          comment: Backup operator on el9.example.com
          shell: /bin/bash
    el10.example.com: {}
```

Run from this repository's root:

```bash
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --list-hosts
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --check
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml
```

`--limit` further restricts the targeted hosts even when the play uses `hosts: all`.

### Add an account list directly in inventory.yml

In the inventory above, `users_mgmt_host_users` is nested under
`all.hosts.el9.example.com`. This list adds `audit_reader` and `backup_operator`
only to that host. The expression in `group_vars/all.yml` also keeps the common
`deploy` account. Each list item supports the user fields documented below.

To apply this list only to `el9.example.com`:

```bash
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --limit el9.example.com --check
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --limit el9.example.com
```

### Add accounts to a specific host through host_vars

Define extra accounts in
[host_vars/el10.example.com.yml](examples/all-hosts/host_vars/el10.example.com.yml).
The filename must match the inventory hostname exactly:

```yaml
---
# Additional accounts for this inventory hostname only.
users_mgmt_host_users:
  - name: app_operator
    state: present
    uid: 2002
    group: operations
    comment: Application operator on el10.example.com
    shell: /bin/bash
```

With the supplied inventory, a normal playbook run manages:

| Host | Accounts |
| --- | --- |
| `el9.example.com` | `deploy`, `audit_reader`, `backup_operator` |
| `el10.example.com` | `deploy`, `app_operator` |

The `operations` group is inherited from `group_vars/all.yml`. The expression in
that file combines the common `deploy` account with the host-specific accounts
defined in the inventory or `host_vars`. These helper variables belong to the example; the role
itself reads `users_mgmt_users`. Account names must remain unique in the combined
list.

To apply the configuration only to `el10.example.com`, use the same inventory
and playbook with `--limit`:

```bash
# Review the selected host.
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --limit el10.example.com --list-hosts

# Preview the changes on that host.
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --limit el10.example.com --check

# Apply the common and host-specific accounts on that host.
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --limit el10.example.com
```

`--limit` selects hosts, not individual accounts. The limited run manages both
`deploy` and `app_operator` on `el10.example.com`; other inventory hosts are not
processed. A run without `--limit` still applies `app_operator` only to its host.

For each host, define `users_mgmt_host_users` either in the inventory or in its
`host_vars` file. If both define it, the `host_vars` value takes precedence and
replaces the inventory list; the two host-specific lists are not combined.

### General rule for inventory overrides

Use the same rule for any supported account field: define a variable in the
inventory, reference it in the shared definition, and provide the common value
with `default(...)`.

```text
account field: "{{ override_variable | default(common_value) }}"
```

For account settings, use `<account_name>_<field_name>` as the override variable
name. For example, `user01_shell` controls `user01.shell`, `user01_groups`
controls `user01.groups`, and `user01_sudo` controls `user01.sudo`. This naming
convention makes the examples consistent; it is not an automatic role feature.
Every overridable field needs an explicit reference in the shared definition.

For Ansible 2.10–2.18, enable native Jinja types before using these examples with
numeric fields such as `uid`. Otherwise templated numbers can become strings,
which this role's validation rejects:

```bash
export ANSIBLE_JINJA2_NATIVE=true
```

Ansible-core 2.19 and later always use native types; this setting is unnecessary
there. See the [Ansible 2.19 templating changes](https://docs.ansible.com/projects/ansible/latest/porting_guides/porting_guide_core_2.19.html).

#### 1. Define common values in group_vars/all.yml

This file contains variables directly, without an `all:` wrapper. Keep common
values inside `default(...)` so inventory variables can supply overrides:

```yaml
---
users_mgmt_common_users:
  - name: user01
    state: "{{ user01_state | default('present') }}"
    uid: "{{ user01_uid | default(2001) }}"
    groups: "{{ user01_groups | default(['operations']) }}"
    append: "{{ user01_append | default(true) }}"
    shell: "{{ user01_shell | default('/bin/bash') }}"
    ssh_keys: "{{ user01_ssh_keys | default(['ssh-ed25519 <COMMON_BASE64> user01@common']) }}"
    sudo: "{{ user01_sudo | default(['/usr/bin/id']) }}"
    sudo_nopasswd: "{{ user01_sudo_nopasswd | default(false) }}"

users_mgmt_users: "{{ users_mgmt_common_users + (users_mgmt_host_users | default([])) }}"

users_mgmt_groups: "{{ env_users_mgmt_groups | default([{'name': 'operations', 'gid': 2000}]) }}"
users_mgmt_protected_users: "{{ env_users_mgmt_protected_users | default(['ansible']) }}"
```

The same expression works for the other fields listed in the Variables section:
`group`, `comment`, `home`, `create_home`, `password_lock`, `expires`, and so on.
Use the documented type and an appropriate common value for each field. Leave
fields out when they should not be managed. Password overrides must contain
supported password hashes stored with Ansible Vault.

Role-level settings follow the same rule. In this example,
`env_users_mgmt_groups` supplies `users_mgmt_groups`, and
`env_users_mgmt_protected_users` supplies `users_mgmt_protected_users`.
These override variables are referenced explicitly; the role itself reads the
final `users_mgmt_*` settings.

#### 2. Override only the values that differ in inventory.yml

For a production inventory, put environment-wide values under **`all.vars`**:

```yaml
---
all:
  vars:
    ansible_python_interpreter: /usr/bin/python3

    user01_uid: 3001
    user01_groups: [operations, wheel]
    user01_append: false
    user01_ssh_keys:
      - "ssh-ed25519 <PRODUCTION_BASE64> user01@prod"
    user01_sudo:
      - /usr/bin/systemctl restart nginx.service
    user01_sudo_nopasswd: false

    env_users_mgmt_protected_users:
      - ansible
      - emergency_admin

  hosts:
    prod01.example.com: {}
    prod02.example.com: {}
```

Replace the public key placeholders with complete public key lines before
applying this example. The restart command requires the service to exist.
The inventory filename does not select settings automatically: its variables
provide the values. In this example:

| Setting | Common value | Production result |
| --- | --- | --- |
| `uid` | `2001` | `3001` |
| `groups` | `[operations]` | `[operations, wheel]` |
| `append` | `true` | `false` |
| `shell` | `/bin/bash` | `/bin/bash`: no override supplied |
| `ssh_keys` | Common public key | Production public key |
| `sudo` | `/usr/bin/id` | Restart `nginx.service` |
| `sudo_nopasswd` | `false` | `false` |
| `users_mgmt_groups` | `operations` with GID `2000` | Unchanged: no override supplied |
| `users_mgmt_protected_users` | `[ansible]` | `[ansible, emergency_admin]` |

Lists replace their common values. For example, `user01_groups: [wheel]` would
select `[wheel]`, not `[operations, wheel]`. The `append` field independently
controls whether existing supplementary memberships on the server are retained.
Other sudoers policies and group-based permissions still apply.

#### 3. Use the same variable at the required scope

| Location | Scope |
| --- | --- |
| Inventory `all.vars` | Every host in that inventory |
| Inventory `all.children.<group>.vars` | Hosts in that group |
| Inventory `all.hosts.<hostname>` | That inventory hostname only |
| `host_vars/<hostname>.yml` next to the playbook | That inventory hostname only |

Within these scopes, host values override group values, and child group values
override parent group values. The playbook's `host_vars` file takes precedence
over the same host variable defined directly in inventory. Keep fallback values
in the field expressions: defining the override variable again in the
playbook's `group_vars/all.yml` can override its value from inventory `all.vars`.

All values keep their YAML types:

| Type | Inventory example |
| --- | --- |
| String | `user01_shell: /bin/bash` |
| Integer | `user01_uid: 3001` |
| Boolean | `user01_append: false` |
| List of strings | `user01_groups: [operations, wheel]` |
| List of mappings | `env_users_mgmt_groups: [{name: operations, gid: 2000}]` |

Use unquoted `true` / `false` for booleans and YAML lists for list fields.
Quote Jinja expressions that start a YAML value. With native Jinja enabled as
described above, Ansible preserves the type of the referenced list, number, or
boolean.

#### 4. Distinguish missing values from explicit values

`default(common_value)` uses the common value only when the override variable
is undefined. To use the common value, omit the override variable entirely.

| Override value | Result |
| --- | --- |
| Variable omitted | Use the common value from `default(...)` |
| `false` | Keep `false` |
| `[]` | Keep an empty list |
| Empty string | Keep the empty string; the target field must support it |
| `null` | Keep `null`; it does not request the common value and can fail validation |

For example, `user01_ssh_keys: []` removes all keys from the managed
`authorized_keys`, while omitting `user01_ssh_keys` uses the common keys.
`user01_sudo: []` removes the role-owned sudo policy. Avoid `default(..., true)`
for this pattern because it would replace explicit `false`, empty lists, and
other false-like values with the common value.

With these example definitions saved in the supplied project layout, inspect
hosts and preview the changes before applying them:

```bash
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --list-hosts
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --check
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml
```

## Variables

`users_mgmt_groups` is a list of dictionaries:

| Field | Default | Description |
| --- | --- | --- |
| `name` | required | Group name |
| `state` | `present` | `present` / `absent` |
| `gid` | unchanged | Positive integer GID |
| `system` | `false` | Create a system group |

`users_mgmt_users` is a list of dictionaries:

| Field | Default | Description |
| --- | --- | --- |
| `name` | required | Username |
| `state` | `present` | `present` / `absent` |
| `uid` | unchanged | Positive integer UID |
| `group` | unchanged | Primary group; must exist or be created by the role |
| `groups` | unchanged | List of supplementary groups; must exist |
| `append` | `true` | Preserve existing supplementary group memberships |
| `comment`, `shell`, `home` | unchanged | GECOS, absolute shell path, and absolute home directory path |
| `create_home` | `true` | Create the home directory |
| `move_home` | `false` | Move the existing home directory when changing its path |
| `system` | `false` | Create a system account |
| `password` | unchanged | Precomputed password hash, `!` to lock the password, or `*` |
| `update_password` | `on_create` | `on_create` / `always` |
| `password_lock` | unchanged | Lock / unlock the password |
| `expires` | unchanged | Account expiration as a Unix timestamp; `-1` removes expiration |
| `ssh_keys` | unchanged | Complete list of lines for `authorized_keys` |
| `sudo` | unchanged | List of sudo commands; `ALL` permits all commands |
| `sudo_nopasswd` | `false` | Run the specified sudo commands without a password |
| `remove` | `false` | With `state: absent`, remove the home directory and mail spool using `userdel` |
| `force` | `false` | Force account deletion using `userdel --force` |

`users_mgmt_protected_users` is an additional list of usernames that must not be
modified or deleted. `root` is always protected, and explicit UID/GID values of 0
are rejected. Add the account used by Ansible to this list if needed.
Unknown fields, duplicate names, and invalid types are rejected before changes
are made to the host. Names may contain up to 32 characters: lowercase ASCII
letters, digits, `_`, `.`, and `-`. The first character must be a letter or `_`;
a trailing `$` is allowed.

### Groups

Groups with `state: present` are created before users are processed. Groups with
`state: absent` are deleted afterward. To enforce exact supplementary group
membership, set `append: false`. To remove all supplementary memberships, use
`groups: []` with `append: false`. Before deleting a primary group, assign a
different primary group to every account that uses it. The `system` option
affects creation; it does not convert existing entries.

### Passwords

Store password hashes in Ansible Vault and pass them through `password`.
Plaintext passwords are rejected. Tasks containing hashes use `no_log`; account
definition errors are also hidden to avoid exposing secrets. Use the types and
fields listed in the table. The hashing algorithm must be supported by the target
system and its cryptographic policy. For rotation, set `update_password: always`
and supply a persistent hash from Vault. Setting `password_lock: true` locks the
password; SSH keys continue to work.

### SSH

When `ssh_keys` is omitted, the role leaves SSH files unchanged. When it is
provided, the role completely replaces `~/.ssh/authorized_keys`, removing keys
that are not in the list. Setting `ssh_keys: []` leaves the file without keys.
Use one line per key; standard `authorized_keys` options are supported.
Provide public key lines rather than URLs or private keys. The configuration
author is responsible for validating the public key format.

The home directory and primary GID are read through `getent` after the account
is processed, supporting custom home directories and primary groups. Permissions
are `0700` for `.ssh` and `0600` for `authorized_keys`. Explicit key management
creates `.ssh` and any missing parent directories even with `create_home: false`.
The role uses the standard `AuthorizedKeysFile .ssh/authorized_keys` location and
the system's default SELinux contexts. For a custom home directory, configure
`semanage fcontext` and `restorecon` separately.

### Sudo

When `sudo` is omitted, the existing policy is preserved. Setting `sudo: []`
removes only the file owned by this role. With `state: absent`, that file is
removed automatically, even if the home directory is retained. Other sudoers
files and privileges granted through groups are left unchanged. Each installed
file is validated with `/usr/sbin/visudo -cf %s` and has mode `0440`.
The path is `/etc/sudoers.d/90-users_mgmt-<sha256 of username>`. Hashing avoids
filename collisions for usernames containing dots and ensures that the sudoers
filename contains no dots, which would cause sudo to ignore it.

### Deletion and check mode

Setting `state: absent` deletes only the specified account; its home directory
is retained by default. Setting `remove: true` explicitly enables its removal.
Account for retained home directories, keys, and other files when reusing a
username or UID.

The role supports `--check`. For accounts that have not yet been created, SSH
files are skipped with an explanation. On a fresh host, check mode may stop at a
dependency that is only planned for creation, such as a missing primary group.
On a configured host, `--check` reports expected changes without applying them.

## Configuration examples

The following snippets show the role input `users_mgmt_users` directly. In the
supplied example, put these account entries under `users_mgmt_common_users` in
`group_vars/all.yml` for every host, or under `users_mgmt_host_users` in a
`host_vars/<inventory_hostname>.yml` file or under the host in `inventory.yml` for
one host. Keep the expression that
builds `users_mgmt_users` so the two lists are combined. Define shared groups
under `users_mgmt_groups` in `group_vars/all.yml`. Repeating a YAML variable does
not merge lists.

### Create a regular user

Create an account with a home directory and Bash. Existing attributes omitted
from the definition, such as UID and password, are left unchanged.

```yaml
users_mgmt_users:
  - name: alice
    comment: Alice Smith
    shell: /bin/bash
```

For a new account, configure a password hash or SSH keys to provide login access.

### Create a service account

Create a system group and account with no interactive shell or home directory.
The `home` value records the intended application directory without creating it.

```yaml
users_mgmt_groups:
  - name: metrics_agent
    system: true

users_mgmt_users:
  - name: metrics_agent
    group: metrics_agent
    system: true
    home: /var/lib/metrics_agent
    create_home: false
    shell: /sbin/nologin
    password: '!'
```

Create application directories and set their ownership in the application's role.

### Add, replace, or clear supplementary groups

Alice keeps existing memberships and gains `operations`. Bob's supplementary
memberships become exactly `operations` and `releases`. Carol loses all
supplementary memberships; her primary group is preserved.

```yaml
users_mgmt_groups:
  - name: operations
  - name: releases

users_mgmt_users:
  - name: alice
    groups: [operations]
    append: true
  - name: bob
    groups: [operations, releases]
    append: false
  - name: carol
    groups: []
    append: false
```

### Manage multiple SSH keys and key options

Read public key files from the Ansible control node. The second key is restricted
to the example office subnet and cannot use agent forwarding. Replace the subnet
and key paths with your own values.

```yaml
users_mgmt_users:
  - name: alice
    ssh_keys:
      - "{{ lookup('file', 'public_keys/alice-laptop.pub') }}"
      - >-
        from="192.0.2.0/24",no-agent-forwarding {{ lookup('file', 'public_keys/alice-office.pub') | trim }}
```

Only these two lines remain in `authorized_keys`. To rotate a key, replace its
entry with the new public key. To remove all managed SSH access, use
`ssh_keys: []`. Omit `ssh_keys` to preserve the existing file.

### Rotate a password stored in Ansible Vault

Encrypt a precomputed password hash without putting it in the command line:

```bash
ansible-vault encrypt_string --stdin-name vault_alice_password_hash
```

Enter the hash on standard input and finish with EOF. Add the generated encrypted
variable to `examples/all-hosts/group_vars/all.yml` and reference it from the
common account definition in the same file. Keep the `users_mgmt_users`
composition expression shown above:

```yaml
users_mgmt_common_users:
  - name: alice
    password: "{{ vault_alice_password_hash }}"
    update_password: always
```

```bash
ansible-playbook -i examples/all-hosts/inventory.yml examples/all-hosts/playbook.yml --ask-vault-pass
```

Changing the stored hash updates the account on the next run. Use
`update_password: on_create` instead to set a password only when creating the
account. Keep the same hash between runs to preserve idempotence.

### Grant selected sudo commands or full administration

Allow `deploy` to manage one service without a password. Allow `administrator`
to run any command with password authentication. The service must already exist.

```yaml
users_mgmt_users:
  - name: deploy
    sudo:
      - /usr/bin/systemctl restart nginx.service
      - /usr/bin/systemctl status nginx.service
    sudo_nopasswd: true
  - name: administrator
    sudo: [ALL]
    sudo_nopasswd: false
```

The administrator needs a usable password, configured separately or through
`password`. For `deploy` to have only the listed sudo permissions, also account
for existing group memberships and other sudoers rules.

### Revoke keys and role-owned sudo access while retaining the account

Clear SSH keys, remove this role's sudo policy, and lock password authentication.
The account, home directory, and group memberships remain in place.

```yaml
users_mgmt_users:
  - name: former_employee
    ssh_keys: []
    sudo: []
    password_lock: true
```

This does not terminate running sessions or remove sudo privileges granted by
other policies or groups. To clear supplementary memberships as well, add
`groups: []` and `append: false`.

### Set account expiration

Set expiration to January 1, 2030, at 00:00 UTC using a Unix timestamp:

```yaml
users_mgmt_users:
  - name: contractor
    expires: 1893456000
```

To remove an existing expiration date, change the value to `expires: -1`.
Omitting the field leaves the current expiration unchanged.

### Delete accounts with or without their home directories

Delete `old_operator` while retaining its home directory. Delete `old_deploy`
along with its home directory and mail spool, then remove its former group.

```yaml
users_mgmt_groups:
  - name: legacy_deploy
    state: absent

users_mgmt_users:
  - name: old_operator
    state: absent
    remove: false
  - name: old_deploy
    state: absent
    remove: true
```

Ensure no remaining account uses `legacy_deploy` as its primary group. Both
accounts' role-owned sudo policies are removed. Files they own outside the home
directory and mail spool require separate cleanup.

### Protect the Ansible connection account

Prevent the role from changing or deleting the automation and emergency accounts:

```yaml
users_mgmt_protected_users:
  - ansible
  - emergency_admin
```

Do not include these names in `users_mgmt_users`; validation rejects any matching
entry. The `root` account remains protected regardless of this list.

## Testing

Test syntax, validation, and templates with the minimum engine version locally,
without modifying accounts:

```bash
python3.9 -m venv .venv210
. .venv210/bin/activate
pip install 'ansible-base==2.10.17' 'jinja2<3.1'
ansible-playbook -i tests/inventory.yml tests/syntax.yml --syntax-check
python tests/test_validation.py
python tests/test_templates.py
```

For integration tests on a disposable EL host:

```bash
python tests/integration/run.py
```

Run this test **as root inside a disposable EL9/EL10 environment** with Python,
`shadow-utils`, and `sudo` installed. It creates and deletes a test account and
groups, and checks idempotence, check mode, key and sudo revocation, membership
replacement, and home directory retention after deletion. Do not run it on a
production server.

Run the complete suite in disposable UBI containers with Docker running:

```bash
bash tests/run-container.sh 9 'ansible-base==2.10.17' python3
bash tests/run-container.sh 9 'ansible-core>=2.20,<2.21'
bash tests/run-container.sh 10 'ansible-core>=2.16,<2.17'
bash tests/run-container.sh 10 'ansible-core>=2.20,<2.21'
```
