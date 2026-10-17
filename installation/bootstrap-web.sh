#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || {
    printf '%s\n' 'bootstrap-web: cannot locate the installation directory' >&2
    exit 1
}
repository_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P) || {
    printf '%s\n' 'bootstrap-web: cannot locate the repository root' >&2
    exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'bootstrap-web: Python 3.9 or newer is required' >&2
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    printf '%s\n' 'bootstrap-web: Python 3.9 or newer is required' >&2
    exit 1
fi

exec python3 "$repository_root/installation/websetup/launch.py" "$@"
