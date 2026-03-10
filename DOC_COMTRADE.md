# Ingesting live UN Comtrade data

ASAN Macro can ingest **live trade data** from the [UN Comtrade](https://comtrade.un.org/) API (free tier) and map it into the project’s CSV/DB schema so you can say **“ingests live Comtrade data.”**

---

## 1. Get an API key (recommended)

- Go to **[UN Comtrade Developer Portal](https://comtradedeveloper.un.org/)**.
- Sign in and create a subscription to get an **API key**.
- Without a key you may still use the public endpoint with strict rate limits (~1 req/s, lower record caps).

## 2. Configure environment

In the project root, create or edit `.env`:

```bash
# Optional: for higher limits and more records per request
COMTRADE_API_KEY=your_subscription_key_here

# Optional: override API base URL if the default endpoint changes
# COMTRADE_BASE_URL=https://comtradeplus.un.org/api/get
```

## 3. Run the fetch script

From the project root, install dependencies (including the official UN Comtrade package and pandas):

```bash
pip install -r requirements.txt
# or: pip install requests comtradeapicall pandas
python scripts/fetch_comtrade.py
```

The script **prefers the official `comtradeapicall` package** when installed (no API key needed for preview; 500 records per request). If the package is not available or returns no data, it falls back to the HTTP API (`COMTRADE_BASE_URL`). With `COMTRADE_API_KEY` in `.env`, the package uses the key for higher limits (e.g. 2500 records per request).

This will:

- Call the UN Comtrade API for the default years (2022–2024) and a default set of reporters (e.g. China, USA, Brazil, India, Russia, South Africa, Mexico, Vietnam).
- Map each record to: `year`, `reporter_region`, `partner_region`, `sector`, `flow_type`, `value_usd`.
- Insert rows into `data/trade.db` (same DB used by `main.py`).

Then run the report as usual:

```bash
python main.py -q "BRICS" -o report.txt
```

## 4. Script options

| Option | Description |
|--------|-------------|
| `--years 2022 2023 2024` | Years to fetch |
| `--reporters 156 842 076` | M49 reporter codes (156=China, 842=USA, 076=Brazil, 356=India, 643=Russia, 710=South Africa, 484=Mexico, 704=Vietnam) |
| `--partner 0` | Partner code (0 = World) |
| `--flow all` | `all`, `export`, or `import` |
| `--commodity TOTAL` | Commodity code (TOTAL or HS 2-digit) |
| `--max-records 5000` | Max records per API request |
| `--no-db` | Only fetch; do not load into DB |
| `--replace` | Clear `trade_flows` before loading (use only Comtrade data in the report) |
| `--use-package` | Use only the comtradeapicall package (skip HTTP API fallback) |
| `--save-csv PATH` | Save mapped data to a CSV file (ASAN Macro schema) |

Examples:

```bash
# Fetch 2023–2024 for China and USA only, and save a CSV
python scripts/fetch_comtrade.py --years 2023 2024 --reporters 156 842 --save-csv data/comtrade_sample.csv

# Fetch but do not load into DB (e.g. to inspect CSV only)
python scripts/fetch_comtrade.py --no-db --save-csv data/comtrade_export.csv
```

## 5. Rate limits (free tier)

- **Without API key:** about 1 request per second; lower record limits per call.
- **With API key:** higher limits (see [Comtrade Developer Portal](https://comtradedeveloper.un.org/) for current quotas).

The script adds a 1-second delay between requests to stay within limits. On 429 (rate limit), it waits 60 seconds and retries once.

## 6. Schema mapping

| Comtrade field (typical) | ASAN Macro field |
|--------------------------|------------------|
| `period` / `refYear` | `year` |
| `reporterDesc` / `reporterCode` | `reporter_region` |
| `partnerDesc` / `partnerCode` | `partner_region` |
| `cmdDesc` / `cmdCode` | `sector` |
| `flowDesc` / `flowCode` (1=M, 2=X) | `flow_type` (import/export) |
| `primaryValue` | `value_usd` |

The same schema is used for CSV import (`main.py --data`) and for the JSON API loader (`data_ingestion.load_json_api`), so Comtrade data fits the rest of the pipeline.

## 7. Scheduling

To run Comtrade fetch + report on a schedule, use:

- **Cron:** `scripts/run_scheduled.sh` (see [SCHEDULING.md](SCHEDULING.md)).
- **GitHub Actions:** `.github/workflows/scheduled_report.yml` for daily or weekly runs.

Both can run `scripts/fetch_comtrade.py` then `python main.py` so reports use up-to-date Comtrade data.
