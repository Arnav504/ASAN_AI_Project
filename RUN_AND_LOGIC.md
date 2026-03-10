# How to Run ASAN Macro & Logic Flow

## How to run

### Prerequisites

1. **Python 3.9+** with the project dependencies:
   ```bash
   cd "/Users/arnavsahai/Desktop/AI Project"
   pip install -r requirements.txt
   ```
   Or use the project venv: `./run.sh` (uses `.venv` if present).

2. **One of these for the LLM** (pick one):
   - **Local (recommended, no quota):** Install [Ollama](https://ollama.com), then:
     ```bash
     ollama pull qwen2:7b
     ```
     In `.env`: `USE_LOCAL_LLM=1` and `OLLAMA_MODEL=qwen2:7b`.
   - **OpenAI:** In `.env`: `OPENAI_API_KEY=sk-...` (optional `OPENAI_MODEL=gpt-4o` for better quality).
   - **Gemini:** In `.env`: `GEMINI_API_KEY=...` (optional `GEMINI_MODEL=gemini-1.5-pro`).

### Commands

**Basic run (uses DB + default focus):**
```bash
python main.py
```

**With options:**
```bash
python main.py -q "BRICS"                    # Focus on BRICS
python main.py -q "US-China electronics"    # Focus query
python main.py -o report.txt                 # Output to report.txt
python main.py -d sample_trade.csv           # Load CSV into DB first
python main.py --data-url "https://..."      # Load CSV from URL (dynamic data)
python main.py -f html -o report.html        # HTML report
python main.py -f linkedin -o report.txt      # Report + LINKEDIN_SUMMARY.txt one-liner
python main.py -f json -o report.json        # Structured JSON (summary, bullets, so_what, whats_next)
python main.py -q "BRICS" -o report.txt -d sample_trade.csv
```

**Optional: ingest live UN Comtrade data first**, then run the report:
```bash
python scripts/fetch_comtrade.py            # Fetches into data/trade.db
python main.py -q "BRICS" -o report.txt
```
See **DOC_COMTRADE.md** for API key and options.

**Scheduled run (ingest + report in one go):**
```bash
chmod +x scripts/run_scheduled.sh
./scripts/run_scheduled.sh
./scripts/run_scheduled.sh -q "BRICS" -o report.txt
```
See **SCHEDULING.md** for cron and GitHub Actions.

**Using the run script:**
```bash
./run.sh
./run.sh -q "BRICS" -o report.txt
```

### What you get

- **Input:** The seeded trade database (`data/trade.db`), optionally plus:
  - Rows from a local CSV (`--data`),
  - Rows from a CSV URL (`--data-url`),
  - Or rows from `scripts/fetch_comtrade.py` (UN Comtrade API),
  and an optional focus (`--query`).
- **Output:** Depends on `--format`:
  - **text** (default): Report written to the given file (or timestamped `report_YYYYMMDD_HHMMSS.txt`) and printed.
  - **html**: Single HTML file (shareable).
  - **linkedin**: Report file + `LINKEDIN_SUMMARY.txt` (one-liner).
  - **json**: Structured JSON file with `summary`, `key_regions_sectors`, `so_what`, `whats_next`, `bullets`, `generated_at`, `full_report` (for dashboards/APIs).

---

## Logic flow (step by step)

High level: **main.py** loads config and DB → calls **agent** → agent picks an LLM (Ollama / OpenAI / Gemini) → gets **context from tools/DB** → **LLM** writes the report → main writes the report to disk and prints it.

---

### 1. Entry point: `main.py`

```
User runs:  python main.py -q "BRICS" -o report.txt
```

1. **Load `.env`**  
   Environment variables (API keys, `USE_LOCAL_LLM`, `OLLAMA_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL`, optional `COMTRADE_API_KEY`, etc.) are loaded from `.env`.

2. **Ensure database exists**  
   `ensure_db()` (from `database.py`) runs:
   - Creates `data/trade.db` if missing.
   - Applies schema: tables `trade_flows` (region, partner, sector, year, value_usd) and `rag_chunks` (stored bulletins for RAG).
   - Seeds sample trade data and RAG chunks if the tables are empty.

3. **Optional: dynamic data ingestion**  
   - If `--data path.csv` is passed and the file exists: load that CSV into `trade_flows` (via `data_ingestion.load_csv_path` or fallback `_load_csv_into_db`). Columns: year, reporter_region, partner_region, sector, flow_type, value_usd.
   - If `--data-url URL` is passed: fetch CSV from URL and load into `trade_flows` (via `data_ingestion.load_csv_url`; requires `requests`).
   - Alternatively you can run `python scripts/fetch_comtrade.py` **before** `main.py` to ingest live UN Comtrade data into the same DB (see DOC_COMTRADE.md).

4. **Run the agent**  
   `report = run_agent(user_query=args.query)`  
   All LLM and tool logic lives here. Returns one string: the report text.

5. **Write output (format depends on `--format`)**  
   - **text**: Write report to `--output` path (or timestamped file) and print to terminal.
   - **html**: Write `_report_to_html(report)` to `--output` with `.html` suffix.
   - **linkedin**: Write report to file and also write `LINKEDIN_SUMMARY.txt` (one-liner) in the same directory; print both.
   - **json**: Parse report with `_report_to_json(report)` and write JSON (summary, key_regions_sectors, so_what, whats_next, bullets, generated_at, full_report) to `--output` with `.json` suffix.

So the “logic” of the run is: **config + DB + optional ingestion (CSV/URL/Comtrade)** → **agent** → **report string** → **file(s) by format + console**.

---

### 2. Agent: which LLM to use (`agent.run_agent`)

`run_agent(user_query)` does **not** call the LLM directly. It first decides **which backend** to use, in this order:

1. **Local Ollama**  
   If `USE_LOCAL_LLM=1` or `OLLAMA_MODEL` is set in `.env` → call `_run_agent_ollama(user_query)` and return its result.

2. **Gemini**  
   Else if `GEMINI_API_KEY` is set → call `_run_agent_gemini(user_query)` and return its result.

3. **OpenAI**  
   Else if `OPENAI_API_KEY` is set → use the **OpenAI client** and the **tool-calling loop** (see below) to produce the report.

4. **Error**  
   If none of the above is configured → return an error string asking you to set one of: `USE_LOCAL_LLM` + Ollama, `OPENAI_API_KEY`, or `GEMINI_API_KEY`.

So the “flow” splits here: **Ollama and Gemini** use a **single-prompt** path (context gathered first, then one LLM call). **OpenAI** uses a **multi-turn tool-calling** path.

---

### 3a. Logic when using **Ollama** (`_run_agent_ollama`)

Used when you run with local model (e.g. `USE_LOCAL_LLM=1`, `OLLAMA_MODEL=qwen2:7b`).

1. **Gather context (no LLM yet)**  
   The code calls your **tools** and builds one big text blob:
   - `list_regions()` → list of regions from DB  
   - `list_sectors()` → list of sectors  
   - `rag_retrieve("BRICS decoupling trade")` → matching RAG chunks  
   - `rag_retrieve("US China electronics")`  
   - `query_trade_flows(year_from=2022, limit=30)` → table of flows  
   - `get_yoy_growth(year_from=2022, year_to=2024)` → YoY growth  
   - `get_top_flows(n=10, year_from=2022)` → top flows by value  
   - `get_trade_trends(limit=10)` → trends (up/down)  
   - If `user_query` is set (e.g. `"BRICS"`), also `rag_retrieve(user_query)`  

   All of this is concatenated into a single **context** string.

2. **Build one prompt**  
   A single user prompt is built that:
   - Says “use this trade data and context to write a short sentiment report”
   - Pastes the **context** (regions, sectors, RAG text, trade flows)
   - Asks for: summary, key regions/sectors, “So what,” “What’s next”
   - Requires the answer in the form:
     ```
     REPORT_START
     [report text]
     REPORT_END
     ```

3. **One LLM call**  
   The OpenAI-compatible client is pointed at Ollama:
   - `base_url = get_ollama_base_url()` (default `http://localhost:11434/v1`)
   - `api_key = "ollama"`
   - `model = get_ollama_model()` (e.g. `qwen2:7b`)  
   One `client.chat.completions.create()` with:
   - system message = `SYSTEM_PROMPT` (analyst role + instructions)
   - user message = the big prompt above  

   So: **DB/tools → context string → one prompt → Ollama → one response**.

4. **Parse report**  
   From the model’s reply, the code finds `REPORT_START` and `REPORT_END`, takes the text in between, and returns it. That string is what `main.py` writes to the file and prints.

**Flow summary (Ollama):**  
DB + RAG + tools (called in code) → one prompt → local model → parse `REPORT_START`/`REPORT_END` → report text.

---

### 3b. Logic when using **Gemini** (`_run_agent_gemini`)

Same idea as Ollama: **no tool-calling by the model**. The app gathers context first, then one Gemini call.

1. **Gather context**  
   Same as Ollama: `list_regions()`, `list_sectors()`, `rag_retrieve(...)`, `query_trade_flows(...)`, optional `rag_retrieve(user_query)`. One big context string.

2. **One prompt**  
   Same structure: “use this data…” + context + “output REPORT_START … REPORT_END”.

3. **One Gemini call**  
   Uses `google.generativeai`, model from `GEMINI_MODEL` (default `gemini-2.0-flash`), with that prompt. On 429, it retries once after a wait; if it still fails, it can return a sample report (quota-exceeded path).

4. **Parse report**  
   Same as Ollama: extract text between `REPORT_START` and `REPORT_END` and return it.

**Flow summary (Gemini):**  
DB + RAG + tools (called in code) → one prompt → Gemini API → parse report (or sample on error).

---

### 3c. Logic when using **OpenAI** (tool-calling loop)

Used when you have `OPENAI_API_KEY` and did **not** enable Ollama or Gemini.

1. **Define tools**  
   The agent registers tools with the API: `list_regions`, `list_sectors`, `query_trade_flows`, `get_region_summary`, `get_sector_summary`, `rag_retrieve`, `get_yoy_growth`, `get_top_flows`, `get_trade_trends` (with names and parameters).

2. **First LLM call**  
   Sends system prompt + user message (e.g. “Analyze the trade database and produce the sentiment report” or “Focus on: BRICS…”). Asks the model to use the tools and then output `REPORT_START` … `REPORT_END`.

3. **Loop: tool calls → run tools → send back**  
   - If the model’s response contains **tool_calls**, the code:
     - Runs each tool (e.g. `query_trade_flows`, `get_region_summary`) with the arguments the model requested.
     - Appends the **tool results** to the conversation as tool messages.
     - Calls the API again with the updated conversation.
   - If the model’s response contains **REPORT_START** and **REPORT_END**, the loop stops and the text between them is returned.
   - This repeats for several rounds (e.g. up to 8) until the model outputs the report or the limit is reached.

4. **Result**  
   The returned string is again the content between `REPORT_START` and `REPORT_END`, which `main.py` writes and prints.

**Flow summary (OpenAI):**  
DB + tools (invoked by the model via API) → multi-turn chat with tool calls → model decides when to stop and output report → parse `REPORT_START`/`REPORT_END` → report text.

---

### 4. Where the data comes from (tools + DB)

No matter which LLM is used, the **data** the report is based on comes from:

- **`database.py`**  
  - Creates and seeds `data/trade.db`.  
  - Tables: `trade_flows` (region, partner, sector, year, value_usd, etc.), `rag_chunks` (text snippets for RAG).

- **`tools.py`**  
  - **list_regions** / **list_sectors**: query distinct values from `trade_flows`.  
  - **query_trade_flows**: filter by reporter, partner, sector, year range, limit.  
  - **get_region_summary** / **get_sector_summary**: aggregated trade by region or sector.  
  - **rag_retrieve**: simple keyword search over `rag_chunks` to pull relevant bulletins.  
  - **get_yoy_growth**: year-over-year growth in trade value (optional region, sector, year range).  
  - **get_top_flows**: top N flows by value (optional year range, flow_type).  
  - **get_trade_trends**: which sectors/partners grew or shrank (optional region, limit).

Data can also be **ingested** before the run via `--data`, `--data-url`, or `scripts/fetch_comtrade.py` (see `data_ingestion.py` and DOC_COMTRADE.md).

For **Ollama and Gemini**, the agent code calls these tools **once** before the LLM call and injects their output into the prompt. For **OpenAI**, the model **requests** tool calls over multiple turns, and the code runs the tools and returns results in the conversation.

---

### 5. End-to-end flow diagram

```
User
  │
  ├─ python main.py -q "BRICS" -o report.txt
  ├─ (optional) python scripts/fetch_comtrade.py   →  load live Comtrade into DB
  ├─ (optional) ./scripts/run_scheduled.sh -o report.txt   →  ingest + report
  │
  ▼
main.py
  │  1. Load .env
  │  2. ensure_db()  →  data/trade.db (schema + seed)
  │  3. Optional: --data CSV or --data-url URL  →  load into trade_flows (data_ingestion)
  │  4. run_agent(user_query="BRICS")
  ▼
agent.run_agent
  │
  ├─ USE_LOCAL_LLM / OLLAMA_MODEL?  ──Yes──► _run_agent_ollama
  │                                              │
  │                                              ├─ Call tools (list_regions, list_sectors,
  │                                              │   rag_retrieve, query_trade_flows,
  │                                              │   get_yoy_growth, get_top_flows, get_trade_trends)
  │                                              ├─ Build one prompt with context
  │                                              ├─ Ollama (localhost:11434) → one response
  │                                              └─ Parse REPORT_START/REPORT_END → return text
  │
  ├─ GEMINI_API_KEY?  ──Yes──► _run_agent_gemini
  │                              (same idea: gather context → one Gemini call → parse report)
  │
  └─ OPENAI_API_KEY?  ──Yes──► OpenAI client + tool-calling loop
                                  (model calls tools over multiple turns → then outputs report)
  │
  ▼
main.py
  │  5. By --format: write report to file (text / html / linkedin one-liner / json)
  │  6. Print report to console
  ▼
Done. Report on disk (+ optional LINKEDIN_SUMMARY.txt or .json) and in console.
```

---

### 6. Summary table

| Step | What happens |
|------|-------------------------------|
| **Run** | `python main.py` (optionally `-q`, `-o`, `-d`, `--data-url`, `-f text\|html\|linkedin\|json`). Or `./scripts/run_scheduled.sh` for ingest + report. |
| **Optional ingest** | Before or alongside: `--data` CSV path, `--data-url` CSV URL, or `python scripts/fetch_comtrade.py` for UN Comtrade. |
| **Config** | `.env` loaded; DB path, API keys, Ollama/Gemini/OpenAI model names, optional Comtrade key. |
| **DB** | `data/trade.db` created/seeded; optional CSV or URL or Comtrade data loaded into `trade_flows`. |
| **LLM choice** | Ollama (if local) → else Gemini (if key) → else OpenAI (if key). |
| **Context** | Tools read from DB: regions, sectors, RAG chunks, trade flows, YoY growth, top flows, trends (and optional user focus). |
| **Ollama/Gemini** | Context pasted into one prompt → one LLM call → parse REPORT_START/END. |
| **OpenAI** | Multi-turn chat; model calls tools; when model outputs REPORT_START/END, parse and return. |
| **Output** | Report string → file by format (text, html, linkedin [+ one-liner file], json) and console. |

That’s the full run process and logic flow from your command to the final report file(s).
