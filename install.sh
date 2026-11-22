#!/bin/bash
set -euo pipefail

DIR="$HOME/Library/Application Support/busybar-focus-mode"

python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10+ is required." >&2; exit 1; }

mkdir -p "$DIR"
curl -fsSL https://codeload.github.com/ErBlack/busybar-focus-mode/tar.gz/main | tar -xz --strip-components=1 -C "$DIR"
python3 -m venv --clear "$DIR/venv"
"$DIR/venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"
"$DIR/venv/bin/python" "$DIR/focus.py" setup < /dev/tty
"$DIR/venv/bin/python" "$DIR/focus.py" start < /dev/tty
