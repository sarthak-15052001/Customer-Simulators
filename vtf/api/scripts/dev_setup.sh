#!/usr/bin/env bash
# Bootstrap a local Python virtualenv at vtf/api/.venv (gitignored).
#
# Idempotent: re-run after editing requirements.txt to pick up new deps.
# Use $PYTHON to pin a specific interpreter (defaults to python3.12, falls
# back to python3).
#
# Usage:
#   ./scripts/dev_setup.sh
#   PYTHON=python3.13 ./scripts/dev_setup.sh
set -euo pipefail

API_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$API_DIR/.venv"

PYTHON_BIN="${PYTHON:-python3.12}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python3
fi

if [ ! -d "$VENV" ]; then
  echo "[dev_setup] creating venv at $VENV using $PYTHON_BIN..."
  "$PYTHON_BIN" -m venv "$VENV"
else
  echo "[dev_setup] reusing existing venv at $VENV"
fi

echo "[dev_setup] upgrading pip..."
"$VENV/bin/pip" install --upgrade --quiet pip

echo "[dev_setup] installing requirements..."
"$VENV/bin/pip" install --quiet -r "$API_DIR/requirements.txt"

cat <<EOF

[dev_setup] done.

Activate the venv:
  source vtf/api/.venv/bin/activate

Common commands (run from vtf/api/):
  python manage.py migrate
  python manage.py loaddata pricing_rules villages activities meals fuel_options promos
  python manage.py runserver

Re-generate fixtures from the frontend mocks:
  python scripts/build_fixtures_from_front_mocks.py
EOF
