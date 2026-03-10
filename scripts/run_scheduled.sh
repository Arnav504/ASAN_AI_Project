#!/usr/bin/env bash
# Run Comtrade ingestion + ASAN Macro report (for cron or manual scheduled runs).
# Usage: ./scripts/run_scheduled.sh [--query "BRICS"] [--output report.txt]
# Set COMTRADE_API_KEY and LLM keys in .env for full pipeline.

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(pwd)"

if command -v python3 &>/dev/null; then
  PY=python3
elif command -v python &>/dev/null; then
  PY=python
else
  echo "Python not found" >&2
  exit 1
fi

echo "[$(date -Iseconds)] Starting scheduled run: ingest + report"

if [ -f "$SCRIPT_DIR/scripts/fetch_comtrade.py" ]; then
  echo "[$(date -Iseconds)] Fetching UN Comtrade data ..."
  $PY scripts/fetch_comtrade.py --years 2022 2023 2024 --max-records 3000 || true
fi

echo "[$(date -Iseconds)] Running ASAN Macro report ..."
$PY main.py "$@"

echo "[$(date -Iseconds)] Done."
