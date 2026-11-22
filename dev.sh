#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt
[ -f config.json ] || venv/bin/python focus.py setup
exec venv/bin/python focus.py run
