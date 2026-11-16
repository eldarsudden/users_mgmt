#!/usr/bin/env bash
# Run the integration suite in a disposable Red Hat UBI container.
set -euo pipefail

el_version="${1:-9}"
ansible_spec="${2:-ansible-core>=2.20,<2.21}"
controller_python="${3:-python3.12}"
case "$el_version" in
  9|10) ;;
  *) echo 'EL version must be 9 or 10' >&2; exit 2 ;;
esac
case "$controller_python" in
  python3|python3.12) ;;
  *) echo 'Controller Python must be python3 or python3.12' >&2; exit 2 ;;
esac
role_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

docker run --rm -i \
  --volume "$role_dir:/work/users_mgmt:ro" \
  "registry.access.redhat.com/ubi${el_version}/ubi:latest" \
  bash -s -- "$ansible_spec" "$controller_python" <<'CONTAINER'
set -euo pipefail
ansible_spec="$1"
controller_python="$2"
dnf install -y python3 python3-pip shadow-utils sudo
if [ "$controller_python" = python3.12 ] && ! command -v python3.12 >/dev/null; then
  dnf install -y python3.12 python3.12-pip
fi
"$controller_python" -m venv /tmp/ansible-test
source /tmp/ansible-test/bin/activate
if [[ "$ansible_spec" == ansible-base* ]]; then
  pip install "$ansible_spec" 'jinja2<3.1'
else
  pip install "$ansible_spec"
fi
export ANSIBLE_PYTHON_INTERPRETER=/usr/bin/python3
cd /work/users_mgmt
ansible-playbook -i tests/inventory.yml tests/syntax.yml --syntax-check
python -m unittest discover -s tests -p 'test_*.py'
python tests/integration/run.py
CONTAINER
