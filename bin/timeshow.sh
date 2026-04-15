#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
MAIN_SCRIPT="$PROJECT_ROOT/timeshow/main.py"

REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"

# Lazy initialization: create venv and install dependencies if needed
if [[ ! -x "$PYTHON_BIN" ]]; then
  VENV_DIR="$PROJECT_ROOT/.venv"

  echo "Setting up virtual environment at $VENV_DIR..." >&2
  if ! python3 -m venv "$VENV_DIR"; then
    echo "Error: Failed to create virtual environment." >&2
    exit 1
  fi

  if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
    echo "Error: requirements.txt not found at $REQUIREMENTS_FILE" >&2
    exit 1
  fi

  PIP_BIN="$VENV_DIR/bin/pip"
  echo "Installing dependencies..." >&2
  if ! "$PIP_BIN" install -r "$REQUIREMENTS_FILE"; then
    echo "Error: Failed to install dependencies." >&2
    exit 1
  fi

  echo "Setup complete." >&2
fi

if [[ ! -f "$MAIN_SCRIPT" ]]; then
  echo "Error: Could not find $MAIN_SCRIPT" >&2
  exit 1
fi

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON_BIN" "$MAIN_SCRIPT" "$@"

