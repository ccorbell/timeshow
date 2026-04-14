#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
MAIN_SCRIPT="$PROJECT_ROOT/timeshow/main.py"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: Python executable not found at $PYTHON_BIN" >&2
  echo "Create a virtual environment and install dependencies first." >&2
  exit 1
fi

if [[ ! -f "$MAIN_SCRIPT" ]]; then
  echo "Error: Could not find $MAIN_SCRIPT" >&2
  exit 1
fi

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON_BIN" "$MAIN_SCRIPT" "$@"

