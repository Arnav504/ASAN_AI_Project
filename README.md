# ASAN Macro – Maritime & Trade Analysis Agent

**Team:** Anders, Sam, Arnav, Nico  

ASAN Macro analyzes real-time and lagged maritime/trade data to study the shifting geopolitical trade landscape—e.g., whether middle economies are decoupling from US/China and forming their own trade partnerships (e.g. BRICS). The agent uses an LLM plus a **database** and **user-created tools** to produce thematic synthesis, contextual filtering, and sentiment reports with “so what” and “what’s next.”

---

## Quick start

1. **Clone or download** this repo.
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Or use the project venv: `./run.sh` (uses `.venv` if present).
3. **Choose one LLM backend** (see below). **Recommended:** local Ollama (no API key, no quota).
4. **Run the application:**
   ```bash
   python main.py
   python main.py -q "BRICS" -o report.txt
   ./run.sh -q "BRICS" -o report.txt
   ```

**Input:** Raw data = seeded trade database (`data/trade.db`), optionally a CSV via `--data`, and an optional focus via `--query`.  
**Output:** A trade sentiment report is written to a file and printed (no extra manual steps).

### LLM options (pick one)

The app checks in this order: **Ollama (local)** → **Gemini** → **OpenAI**. Configure one in `.env`.

| Option | Setup | Use case |
|--------|--------|----------|
| **Local Ollama** (recommended) | Install [Ollama](https://ollama.com), run `ollama pull qwen2:7b` (or `llama3.2`, `mistral`). In `.env`: `USE_LOCAL_LLM=1` and `OLLAMA_MODEL=qwen2:7b`. | No API key or quota; runs fully on your machine. |
| **Gemini** | Get free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). In `.env`: `GEMINI_API_KEY=your_key`. | Free tier when OpenAI quota is exceeded. |
| **OpenAI** | In `.env`: `OPENAI_API_KEY=sk-...`. | Full tool-calling loop; requires API credits. |

Optional for Ollama: `OLLAMA_BASE_URL=http://localhost:11434/v1` (default).

### Command-line options

| Flag | Description |
|------|-------------|
| `-q "BRICS"` / `--query` | Focus the analysis (e.g. BRICS, US-China electronics). |
| `-o report.txt` / `--output` | Write report to this file (default: timestamped `report_YYYYMMDD_HHMMSS.txt`). |
| `-d sample_trade.csv` / `--data` | Load CSV into the DB before analysis (columns: year, reporter_region, partner_region, sector, flow_type, value_usd). |

Examples:
```bash
python main.py -q "BRICS" -o report.txt
python main.py -q "US-China electronics" -d sample_trade.csv -o report.txt
```

### If you get 429 (quota exceeded)

- **OpenAI:** Add billing/credits at [platform.openai.com](https://platform.openai.com), or switch to Gemini or Ollama.
- **Gemini:** Wait and retry, or use a different key; or set `USE_LOCAL_LLM=1` and use Ollama instead.

---

## Logic flow and run details

For a **step-by-step explanation** of how the app runs (main → DB → agent → LLM choice → tools → report), see **[RUN_AND_LOGIC.md](RUN_AND_LOGIC.md)**. It covers:

- How `main.py` loads `.env`, ensures the DB, and optionally loads CSV.
- How the agent chooses Ollama vs Gemini vs OpenAI.
- How context is gathered (tools + DB) for each backend.
- Single-prompt path (Ollama, Gemini) vs tool-calling loop (OpenAI).
- End-to-end flow diagram and summary table.

---

## Project structure

```
├── README.md           # This file + deliverable checklist
├── RUN_AND_LOGIC.md    # How to run + full logic flow
├── requirements.txt   # openai, python-dotenv, google-generativeai
├── .env.example       # Template for API keys and Ollama
├── config.py          # Paths, API keys, Ollama (use_local_ollama, get_ollama_*)
├── database.py        # SQLite schema + seed (trade_flows, rag_chunks)
├── tools.py           # User-created tools (list_regions, query_trade_flows, rag_retrieve, etc.)
├── agent.py           # run_agent, Ollama/Gemini/OpenAI paths, tool use
├── main.py            # CLI: raw input → report output
├── run.sh             # Convenience: runs main.py (uses .venv if present)
├── sample_trade.csv   # Example CSV for --data
└── data/
    └── trade.db       # Created on first run (trade_flows + rag_chunks)
```

---

## How this meets the deliverable (Application Code 60%)

| Criterion | How it’s satisfied |
|-----------|--------------------|
| **LLM use (10%)** | The app uses a large language model via **OpenAI API**, **Gemini API**, or a **local open-source model (Ollama)**. The LLM drives synthesis and report generation. |
| **Non-triviality (20%)** | The task is not “one ChatGPT prompt”: the app combines **structured trade data** (DB), **RAG-style retrieval** (rag_chunks), and **tool use**. The LLM filters, synthesizes, and extrapolates to produce a “so what” / “what’s next” report that would require manual data pulling and analysis with a plain chatbot. |
| **Augmentation (20%)** | **1) Database for RAG/agentic memory:** SQLite `trade_flows` + `rag_chunks`; the agent queries these via tools. **2) User-created tools:** `tools.py` implements `list_regions`, `list_sectors`, `query_trade_flows`, `get_region_summary`, `get_sector_summary`, `rag_retrieve`—used by the agent (and by the OpenAI model via function calling when using OpenAI). |
| **Input/output completeness (50%)** | **Input:** Raw data = the database (seeded + optional `--data` CSV) and optional `--query`. **Output:** The app writes the report to a file and prints it; no manual intervention after running `main.py`. |

---

## Demo (40%) – Suggested slides and talking points

- **Use case (10%)**  
  Purpose: give economists, macro strategists, multilateral bodies, and businesses a single run that turns trade/maritime-style data into a short sentiment report (themes, regions/sectors, so what, what’s next). Value: saves manual data gathering and synthesis.

- **Non-triviality (10%)**  
  Alternatives: manually querying UN Comtrade, Census, Eurostat, etc., then pasting into ChatGPT. Our app: structured DB + tools + RAG so the LLM reasons over real data and produces a consistent report format.

- **Architecture (30%)**  
  Use the diagram in [RUN_AND_LOGIC.md](RUN_AND_LOGIC.md#5-end-to-end-flow-diagram). Short version: **User / CSV** → **main.py** → **DB + tools** → **agent** (Ollama or Gemini or OpenAI) → **Report file**. Call out: SQLite (trade_flows, rag_chunks), tools in `tools.py`, and the three LLM backends (local Ollama, Gemini, OpenAI).

- **Live demo (50%)**  
  1. Show `data/trade.db` or run `python database.py`.  
  2. Run `python main.py -q "BRICS" -o report.txt` (with Ollama running, or an API key set).  
  3. Show the generated report and the “so what” / “what’s next” sections.

---

## Running in Google Colab

In Colab you typically use an API (Gemini or OpenAI) rather than local Ollama:

1. Upload this project (or clone from GitHub) into Colab.
2. In a cell: `!pip install -r requirements.txt`
3. Set an API key (e.g. Colab secrets or a cell):
   ```python
   import os
   os.environ["GEMINI_API_KEY"] = "..."   # or OPENAI_API_KEY
   ```
4. Run: `!python main.py -q "BRICS" -o report.txt`  
   Then read and display `report.txt`.

---

## Data sources (from your planning doc)

The current seed data is synthetic but aligned with your planned sources (e.g. Comtrade, Census, Eurostat, MarineTraffic, VesselFinder). To extend the app:

- Add more rows to `SAMPLE_TRADE` / `SAMPLE_RAG_CHUNKS` in `database.py`, or  
- Load CSVs via `main.py --data yourfile.csv` (columns: year, reporter_region, partner_region, sector, flow_type, value_usd).

---

## License

Use as needed for your course submission. Ensure the repo or Drive folder is **public or shared with the instructor** as required.
