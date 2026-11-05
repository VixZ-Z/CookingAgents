#!/usr/bin/env bash
# Linux / macOS: set up the environment and run everything.
#   bash run.sh
set -e
cd "$(dirname "$0")"

[ -x .venv/bin/python ] || python3 -m venv .venv
py=.venv/bin/python
"$py" -m pip install -q -r requirements.txt

for script in main compare visualize animate; do
    echo
    echo "=== $script.py ==="
    "$py" "$script.py"
done
