# Scheduling daily/weekly trade sentiment reports

ASAN Macro can run **ingestion + report** on a schedule so you can say **“daily/weekly trade sentiment reports.”**

---

## 1. Cron (Linux / macOS)

Use the provided script so Comtrade fetch (optional) and the report run in one go.

**Make the script executable (once):**

```bash
chmod +x scripts/run_scheduled.sh
```

**Run manually:**

```bash
./scripts/run_scheduled.sh
./scripts/run_scheduled.sh -q "BRICS" -o reports/report_brics.txt
```

**Cron examples:**

```bash
# Every day at 6:00 AM
0 6 * * * /path/to/AI\ Project/scripts/run_scheduled.sh -o /path/to/reports/daily.txt >> /path/to/reports/cron.log 2>&1

# Every Monday at 00:00 (weekly)
0 0 * * 1 /path/to/AI\ Project/scripts/run_scheduled.sh -o /path/to/reports/weekly.txt >> /path/to/reports/cron.log 2>&1
```

Replace `/path/to/AI Project` and `/path/to/reports` with your paths. Ensure `.env` (and `COMTRADE_API_KEY` if you use Comtrade) is in the project root so the script can load it.

---

## 2. GitHub Actions

A workflow runs the report on a schedule and on manual trigger, and uploads the report as an artifact.

**File:** `.github/workflows/scheduled_report.yml`

**Schedule:** default is **every Monday at 00:00 UTC**. Edit the `cron` in the file to change it, e.g.:

- Daily at 00:00 UTC: `"0 0 * * *"`
- Weekly on Sunday 12:00 UTC: `"0 12 * * 0"`

**Secrets (Settings → Secrets and variables → Actions):**

- `OPENAI_API_KEY` or `GEMINI_API_KEY` — required for the LLM report.
- `COMTRADE_API_KEY` — optional; if set, the workflow fetches UN Comtrade data before running the report.

**Manual run:** Actions → “Scheduled trade report” → “Run workflow”.

**Outputs:** The workflow uploads `report_scheduled.txt` (and `report_scheduled.json` if you use `-f json`) as artifacts. Download them from the run’s “Artifacts” section.

---

## 3. What runs

1. **Comtrade (optional)**  
   If `scripts/fetch_comtrade.py` exists and (for GitHub Actions) `COMTRADE_API_KEY` is set, the pipeline fetches recent Comtrade data into the DB.

2. **Report**  
   `main.py` runs with the arguments you pass (e.g. `-q "BRICS"` or default focus), producing the usual text report (and optionally JSON with `-f json`).

For cron, you control arguments in the crontab. For GitHub Actions, edit the `run: python main.py ...` step in `.github/workflows/scheduled_report.yml`.
