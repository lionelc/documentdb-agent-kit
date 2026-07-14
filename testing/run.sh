#!/usr/bin/env bash
# run.sh — convenience runner for the DocumentDB Agent-Kit regression suite.
# Creates a venv, installs deps, and runs pytest. Extra args pass through to
# pytest, e.g.:  bash testing/run.sh scenarios/ecommerce-healthy-indexes -v
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
VENV="$REPO/testing-venv"

if [[ ! -x "$VENV/bin/python" ]]; then
    echo "Creating venv at $VENV ..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r "$HERE/requirements.txt"
fi

cd "$HERE"
exec "$VENV/bin/python" -m pytest "$@"
