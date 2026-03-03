#!/usr/bin/env bash
# Run ASAN Macro (uses .venv if present)
cd "$(dirname "$0")"
if [ -d .venv ]; then
  .venv/bin/python main.py "$@"
else
  python3 main.py "$@"
fi
