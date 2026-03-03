"""
ASAN Macro - Main entry point.
Takes raw input (optional CSV path and/or focus query) and outputs a trade sentiment report
without additional manual intervention (input/output completeness).
"""
import argparse
import sys
from pathlib import Path

# Load .env first so OPENAI_API_KEY is set before the agent runs
_script_dir = Path(__file__).resolve().parent
_env_path = _script_dir / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_env_path), override=True)
    except Exception:
        pass

from config import PROJECT_ROOT
from database import ensure_db
from agent import run_agent


def main():
    parser = argparse.ArgumentParser(
        description="ASAN Macro: Analyze trade data and produce a sentiment/synthesis report."
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default=None,
        help="Optional focus query (e.g. 'BRICS', 'US-China electronics'). If omitted, full analysis.",
    )
    parser.add_argument(
        "--data",
        "-d",
        type=str,
        default=None,
        help="Optional path to CSV with trade data (columns: year, reporter_region, partner_region, sector, flow_type, value_usd). Loaded into DB before analysis.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path for the report. Default: report_<timestamp>.txt in project root.",
    )
    args = parser.parse_args()

    # Ensure database exists and is seeded (or load --data into it)
    ensure_db()
    if args.data:
        data_path = Path(args.data)
        if data_path.exists():
            _load_csv_into_db(data_path)
        else:
            print(f"Warning: data file not found: {data_path}", file=sys.stderr)

    # Run agent: raw input (DB + optional query) -> report
    report = run_agent(user_query=args.query)

    out_path = args.output
    if not out_path:
        from datetime import datetime
        out_path = PROJECT_ROOT / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    else:
        out_path = Path(out_path)

    out_path.write_text(report, encoding="utf-8")
    print("Report written to:", out_path)
    print("\n--- Report ---\n")
    print(report)
    return 0


def _load_csv_into_db(csv_path: Path):
    """Load a CSV with trade data into the database. Columns: year, reporter_region, partner_region, sector, flow_type, value_usd."""
    import csv
    from config import DB_PATH
    import sqlite3

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    year = int(row.get("year", 0))
                    reporter = row.get("reporter_region", "").strip()
                    partner = row.get("partner_region", "").strip()
                    sector = row.get("sector", "").strip()
                    flow_type = row.get("flow_type", "export").strip()
                    val = float(row.get("value_usd", 0))
                except (ValueError, KeyError):
                    continue
                if not reporter or not partner or not sector:
                    continue
                cur.execute(
                    "INSERT INTO trade_flows (year, reporter_region, partner_region, sector, flow_type, value_usd) VALUES (?,?,?,?,?,?)",
                    (year, reporter, partner, sector, flow_type, val),
                )
        conn.commit()
        print(f"Loaded CSV rows into DB: {csv_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
