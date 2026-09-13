#!/usr/bin/env bash
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"
python3 -m pip install --user --editable .
echo "Installed. Restart the shell, then run: rogue"
