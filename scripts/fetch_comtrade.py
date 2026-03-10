#!/usr/bin/env python3
"""
Fetch trade data from UN Comtrade (free tier) and load into ASAN Macro DB.
Maps Comtrade JSON to our schema: year, reporter_region, partner_region, sector, flow_type, value_usd.

Usage:
  python scripts/fetch_comtrade.py
  python scripts/fetch_comtrade.py --years 2022 2023 2024 --reporters 156 842 --save-csv
  COMTRADE_API_KEY=your_key python scripts/fetch_comtrade.py

Requires: requests. Optional: COMTRADE_API_KEY in .env for higher limits.
See DOC_COMTRADE.md for API key and rate limits.
"""
import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_env = PROJECT_ROOT / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_env), override=True)
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

DEFAULT_BASE = "https://comtradeplus.un.org/api/get"


def _base_url():
    return os.environ.get("COMTRADE_BASE_URL", DEFAULT_BASE).strip() or DEFAULT_BASE


def _api_key():
    return os.environ.get("COMTRADE_API_KEY", "").strip()


M49 = {
    "156": "China", "842": "USA", "076": "Brazil", "356": "India", "643": "Russia",
    "710": "South Africa", "484": "Mexico", "704": "Viet Nam", "818": "Egypt",
    "360": "Indonesia", "784": "United Arab Emirates", "0": "World",
}


def _country_name(code) -> str:
    if code is None:
        return "Unknown"
    return M49.get(str(code).strip(), str(code).strip())


def _map_comtrade_record(rec: dict) -> tuple:
    """Map one Comtrade API record to (year, reporter_region, partner_region, sector, flow_type, value_usd)."""
    year = rec.get("period") or rec.get("refYear") or rec.get("year") or (str(rec.get("pfDate", ""))[:4] or 0)
    try:
        year = int(year) if year else 0
    except (TypeError, ValueError):
        return None
    reporter = (rec.get("reporterDesc") or rec.get("reporter") or _country_name(rec.get("reporterCode"))).strip()
    partner = (rec.get("partnerDesc") or rec.get("partner") or _country_name(rec.get("partnerCode"))).strip()
    sector = (rec.get("cmdDesc") or rec.get("cmdCode") or rec.get("aggLevel") or "TOTAL").strip()
    flow_raw = rec.get("flowDesc") or rec.get("flowCode") or rec.get("rgDesc") or ""
    flow = "import" if str(flow_raw).lower().startswith("i") or str(rec.get("flowCode")) in ("1", "M") else "export"
    value = rec.get("primaryValue") or rec.get("customsValue") or rec.get("netWgt") or 0
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not reporter or not partner:
        return None
    return (year, reporter, partner, sector, flow, value)


def _dataframe_row_to_record(row) -> dict:
    """Convert a comtradeapicall DataFrame row (Series or dict) to a dict _map_comtrade_record understands."""
    if isinstance(row, dict):
        return row
    d = {}
    for col in ["period", "refYear", "year", "reporterCode", "reporterDesc", "reporter",
                "partnerCode", "partnerDesc", "partner", "cmdCode", "cmdDesc", "aggLevel",
                "flowCode", "flowDesc", "rgDesc", "primaryValue", "customsValue", "netWgt"]:
        try:
            if hasattr(row, "get") and row.get(col) is not None:
                d[col] = row.get(col)
            elif hasattr(row, "__getitem__") and col in row:
                d[col] = row[col]
        except Exception:
            pass
    return d


def fetch_comtrade_via_package(
    years=None,
    reporters=None,
    partner_code=None,
    max_records=500,
    api_key=None,
) -> list:
    """
    Fetch using official comtradeapicall package (pip install comtradeapicall).
    Uses previewFinalData (no key, 500/request) or getFinalData (with key, 2500/request).
    Returns list of raw record dicts for _map_comtrade_record / load_into_db.
    """
    try:
        import comtradeapicall
    except ImportError:
        return []

    years = years or [2022, 2023, 2024]
    # Reporter M49 codes: 156=China, 842=USA, 076=Brazil, 356=India, 643=Russia, 710=South Africa, 484=Mexico, 704=Viet Nam
    reporters = reporters or ["156", "842", "076", "356", "643", "710", "484", "704"]
    api_key = api_key or _api_key()
    all_records = []
    for year in years:
        for rep in reporters:
            for flow_code in ("X", "M"):  # export, import
                try:
                    if api_key:
                        df = comtradeapicall.getFinalData(
                            api_key,
                            typeCode="C",
                            freqCode="A",
                            clCode="HS",
                            period=str(year),
                            reporterCode=str(rep),
                            cmdCode="TOTAL",
                            flowCode=flow_code,
                            partnerCode=partner_code,
                            partner2Code=None,
                            customsCode=None,
                            motCode=None,
                            maxRecords=max_records,
                            format_output="JSON",
                            aggregateBy=None,
                            breakdownMode="classic",
                            countOnly=None,
                            includeDesc=True,
                        )
                    else:
                        df = comtradeapicall.previewFinalData(
                            typeCode="C",
                            freqCode="A",
                            clCode="HS",
                            period=str(year),
                            reporterCode=str(rep),
                            cmdCode="TOTAL",
                            flowCode=flow_code,
                            partnerCode=partner_code,
                            partner2Code=None,
                            customsCode=None,
                            motCode=None,
                            maxRecords=min(max_records, 500),
                            format_output="JSON",
                            aggregateBy=None,
                            breakdownMode="classic",
                            countOnly=None,
                            includeDesc=True,
                        )
                except Exception as e:
                    print(f"comtradeapicall request failed (year={year}, reporter={rep}, flow={flow_code}): {e}", file=sys.stderr)
                    continue
                if df is None or (hasattr(df, "empty") and df.empty):
                    continue
                # DataFrame -> list of dicts (each row as dict for _map_comtrade_record)
                if hasattr(df, "iterrows"):
                    for _, row in df.iterrows():
                        rec = dict(row) if hasattr(row, "index") else (row if isinstance(row, dict) else _dataframe_row_to_record(row))
                        if rec:
                            all_records.append(rec)
                elif isinstance(df, list):
                    for row in df:
                        all_records.append(row if isinstance(row, dict) else _dataframe_row_to_record(row))
                time.sleep(1)
    return all_records


def fetch_comtrade(
    years=None,
    reporters=None,
    partner="0",
    flow="all",
    commodity="TOTAL",
    max_records=5000,
    base_url=None,
    api_key=None,
) -> list:
    years = years or [2022, 2023, 2024]
    reporters = reporters or ["156", "842", "076", "356", "643", "710", "484", "704"]
    base_url = base_url or _base_url()
    api_key = api_key or _api_key()
    headers = {}
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key

    all_records = []
    for year in years:
        for rep in reporters:
            for rg in ([1, 2] if flow == "all" else [2 if flow == "export" else 1]):
                params = {
                    "type": "C", "freq": "A", "px": "HS", "ps": year,
                    "r": rep, "p": partner, "rg": rg, "cc": commodity,
                    "fmt": "json", "maxRecords": min(max_records, 50000),
                }
                try:
                    r = requests.get(base_url, params=params, headers=headers, timeout=60)
                    if r.status_code == 429:
                        time.sleep(60)
                        r = requests.get(base_url, params=params, headers=headers, timeout=60)
                    r.raise_for_status()
                    data = r.json()
                except Exception as e:
                    print(f"API request failed (year={year}, reporter={rep}): {e}", file=sys.stderr)
                    continue
                records = data if isinstance(data, list) else data.get("data", data.get("results", []))
                if not records and isinstance(data, dict):
                    records = data.get("dataset", [])
                for rec in records:
                    if isinstance(rec, dict):
                        all_records.append(rec)
                time.sleep(1)
    return all_records


def load_into_db(records: list, replace: bool = False) -> int:
    from config import DB_PATH
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    if replace:
        cur.execute("DELETE FROM trade_flows")
    count = 0
    for rec in records:
        row = _map_comtrade_record(rec)
        if not row:
            continue
        year, reporter, partner, sector, flow_type, value_usd = row
        cur.execute(
            """INSERT INTO trade_flows (year, reporter_region, partner_region, sector, flow_type, value_usd)
               VALUES (?,?,?,?,?,?)""",
            (year, reporter, partner, sector, flow_type, value_usd),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def save_csv(records: list, path: Path) -> int:
    import csv
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "reporter_region", "partner_region", "sector", "flow_type", "value_usd"])
        for rec in records:
            row = _map_comtrade_record(rec)
            if not row:
                continue
            w.writerow(row)
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Fetch UN Comtrade data into ASAN Macro DB.")
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024], help="Years to fetch")
    parser.add_argument("--reporters", nargs="+", default=["156", "842", "076", "356", "643", "710", "484", "704"],
                        help="M49 reporter codes")
    parser.add_argument("--partner", default="0", help="Partner code (0=World)")
    parser.add_argument("--flow", choices=["all", "export", "import"], default="all")
    parser.add_argument("--commodity", default="TOTAL", help="Commodity code")
    parser.add_argument("--max-records", type=int, default=5000)
    parser.add_argument("--no-db", action="store_true", help="Do not load into DB")
    parser.add_argument("--replace", action="store_true", help="Clear trade_flows before loading (use only dynamic data)")
    parser.add_argument("--use-package", action="store_true", help="Use only comtradeapicall package (skip HTTP fallback)")
    parser.add_argument("--save-csv", type=str, default=None, metavar="PATH", help="Save mapped data to CSV")
    args = parser.parse_args()

    from database import ensure_db
    ensure_db()

    print("Fetching from UN Comtrade ...", file=sys.stderr)
    records = []
    # Prefer official comtradeapicall package when installed (more reliable than raw HTTP)
    records = fetch_comtrade_via_package(
        years=args.years, reporters=args.reporters, partner_code=args.partner if args.partner != "0" else None,
        max_records=min(args.max_records, 2500), api_key=_api_key() or None,
    )
    if records:
        print("Fetched via comtradeapicall package.", file=sys.stderr)
    if not records and not args.use_package:
        records = fetch_comtrade(
            years=args.years, reporters=args.reporters, partner=args.partner,
            flow=args.flow, commodity=args.commodity, max_records=args.max_records,
        )
    print(f"Fetched {len(records)} raw records", file=sys.stderr)

    if not records:
        print("No records returned. Check COMTRADE_BASE_URL and API. See DOC_COMTRADE.md.", file=sys.stderr)
        return 1

    if args.save_csv:
        n = save_csv(records, Path(args.save_csv))
        print(f"Saved {n} rows to {args.save_csv}", file=sys.stderr)

    if not args.no_db:
        n = load_into_db(records, replace=args.replace)
        print(f"Loaded {n} rows into DB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
