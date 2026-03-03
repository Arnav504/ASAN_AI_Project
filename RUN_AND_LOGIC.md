# How to Run ASAN Macro & Logic Flow

## How to run

### Prerequisites

1. **Python 3.9+** with the project dependencies:
   ```bash
   cd "/Users/arnavsahai/Desktop/AI Propject"
   pip install -r requirements.txt
   ```
   Or use the project venv: `./run.sh` (uses `.venv` if present).

2. **One of these for the LLM** (pick one):
   - **Local (recommended, no quota):** Install [Ollama](https://ollama.com), then:
     ```bash
     ollama pull qwen2:7b
     ```
     In `.env`: `USE_LOCAL_LLM=1` and `OLLAMA_MODEL=qwen2:7b`.
   - **OpenAI:** In `.env`: `OPENAI_API_KEY=sk-...`
   - **Gemini:** In `.env`: `GEMINI_API_KEY=...`

### Commands

**Basic run (uses DB + default focus):**
```bash
python main.py
```

**With options:**
```bash
python main.py -q "BRICS"              # Focus on BRICS
python main.py -q "US-China electronics"
python main.py -o report.txt            # Output to report.txt
python main.py -d sample_trade.csv     # Load extra data from CSV first
python main.py -q "BRICS" -o report.txt -d sample_trade.csv
```

**Using the run script:**
```bash
./run.sh
./run.sh -q "BRICS" -o report.txt
```

### What you get

- **Input:** The seeded trade database (`data/trade.db`), optionally plus rows from a CSV (`--data`), and an optional focus (`--query`).
- **Output:** A text report written to a file (e.g. `report.txt` or `report_YYYYMMDD_HHMMSS.txt`) and printed to the terminal. No extra manual steps.

---

## Logic flow (step by step)

High level: **main.py** loads config and DB → calls **agent** → agent picks an LLM (Ollama / OpenAI / Gemini) → gets **context from tools/DB** → **LLM** writes the report → main writes the report to disk and prints it.

---

### 1. Entry point: `main.py`

```
User runs:  python main.py -q "BRICS" -o report.txt
```

1. **Load `.env`**  
   Environment variables (API keys, `USE_LOCAL_LLM`, `OLLAMA_MODEL`, etc.) are loaded from `.env` so the rest of the app can decide which LLM to use.

2. **Ensure database exists**  
   `ensure_db()` (from `database.py`) runs:
   - Creates `data/trade.db` if missing.
   - Applies schema: tables `trade_flows` (region, partner, sector, year, value_usd) and `rag_chunks` (stored bulletins for RAG).
   - Seeds sample trade data and RAG chunks if the tables are empty.

3. **Optional: load CSV**  
   If you passed `--data sample_trade.csv`, the script reads that CSV and **inserts** rows into `trade_flows` (same columns: year, reporter_region, partner_region, sector, flow_type, value_usd). This is your “raw data” input.

4. **Run the agent**  
   `report = run_agent(user_query=args.query)`  
   This is where all LLM and tool logic lives. It returns one string: the report text.

5. **Write and print**  
   The report string is written to the path from `--output` (or a timestamped filename) and printed to the terminal. Then the script exits.

So the “logic” of the run is: **config + DB + optional CSV** → **agent** → **report file + console**.

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
   Uses `google.generativeai`, model `gemini-2.0-flash`, with that prompt. On 429, it retries once after a wait; if it still fails, it can return a sample report (quota-exceeded path).

4. **Parse report**  
   Same as Ollama: extract text between `REPORT_START` and `REPORT_END` and return it.

**Flow summary (Gemini):**  
DB + RAG + tools (called in code) → one prompt → Gemini API → parse report (or sample on error).

---

### 3c. Logic when using **OpenAI** (tool-calling loop)

Used when you have `OPENAI_API_KEY` and did **not** enable Ollama or Gemini.

1. **Define tools**  
   The agent registers tools with the API: `list_regions`, `list_sectors`, `query_trade_flows`, `get_region_summary`, `get_sector_summary`, `rag_retrieve` (with names and parameters).

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

For **Ollama and Gemini**, the agent code calls these tools **once** before the LLM call and injects their output into the prompt. For **OpenAI**, the model **requests** tool calls over multiple turns, and the code runs the tools and returns results in the conversation.

---

### 5. End-to-end flow diagram

```
User
  │
  ├─ python main.py -q "BRICS" -o report.txt
  │
  ▼
main.py
  │  1. Load .env
  │  2. ensure_db()  →  data/trade.db (schema + seed)
  │  3. Optional: load --data CSV into trade_flows
  │  4. run_agent(user_query="BRICS")
  ▼
agent.run_agent
  │
  ├─ USE_LOCAL_LLM / OLLAMA_MODEL?  ──Yes──► _run_agent_ollama
  │                                              │
  │                                              ├─ Call tools (list_regions, list_sectors,
  │                                              │   rag_retrieve, query_trade_flows)
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
  │  5. Write report text to file (-o or timestamped)
  │  6. Print report to terminal
  ▼
Done. Report on disk and in console.
```

---

### 6. Summary table

| Step | What happens |
|------|-------------------------------|
| **Run** | `python main.py` (optionally with `-q`, `-o`, `-d`) |
| **Config** | `.env` loaded; DB path, API keys, Ollama/Gemini flags read |
| **DB** | `data/trade.db` created/seeded; optional CSV loaded into `trade_flows` |
| **LLM choice** | Ollama (if local) → else Gemini (if key) → else OpenAI (if key) |
| **Context** | Tools read from DB: regions, sectors, RAG chunks, trade flows (and optional user focus) |
| **Ollama/Gemini** | Context pasted into one prompt → one LLM call → parse REPORT_START/END |
| **OpenAI** | Multi-turn chat; model calls tools; when model outputs REPORT_START/END, parse and return |
| **Output** | Report string written to file and printed |

That’s the full run process and logic flow from your command to the final report file.
