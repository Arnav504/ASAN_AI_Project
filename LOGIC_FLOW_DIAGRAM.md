# AI Project — Logic Flow Diagram

**ASAN Macro:** CLI app that turns trade data (DB + optional CSV / CSV URL / UN Comtrade + focus query) into a sentiment report via an LLM (Ollama, Gemini, or OpenAI) and tools (DB + RAG + analysis). Output can be text, HTML, LinkedIn one-liner, or structured JSON. Optional scheduling (cron / GitHub Actions) runs ingestion + report.

---

## High-level flow

```mermaid
flowchart TB
    subgraph Input[" "]
        User["User"]
        CLI["python main.py -q BRICS -o report.txt"]
        Env[".env"]
        CSV["--data CSV (optional)"]
        DataURL["--data-url URL (optional)"]
        Format["--format text | html | linkedin | json"]
    end

    subgraph Ingest["Optional ingestion"]
        Comtrade["scripts/fetch_comtrade.py\n(UN Comtrade → DB)"]
        RunSched["scripts/run_scheduled.sh\n(ingest + main.py)"]
    end

    subgraph Main["main.py"]
        LoadEnv["1. Load .env"]
        EnsureDB["2. ensure_db()"]
        LoadData["3. Load --data CSV or\n--data-url into trade_flows"]
        RunAgent["4. run_agent(user_query)"]
        WriteOut["5. Write by --format:\ntext / html / linkedin / json\n6. Print to console"]
    end

    subgraph Data["Data layer"]
        DB[("data/trade.db")]
        Tools["tools.py\n(list_regions, list_sectors,\nquery_trade_flows, get_region_summary,\nget_sector_summary, rag_retrieve,\nget_yoy_growth, get_top_flows,\nget_trade_trends)"]
    end

    subgraph Agent["agent.run_agent"]
        LLMChoice["Which LLM?"]
        Ollama["Ollama (local)"]
        Gemini["Gemini API"]
        OpenAI["OpenAI API"]
    end

    User --> CLI
    User --> Comtrade
    User --> RunSched
    Comtrade --> DB
    RunSched --> Main
    CLI --> LoadEnv
    LoadEnv --> Env
    LoadEnv --> EnsureDB
    EnsureDB --> DB
    CSV --> LoadData
    DataURL --> LoadData
    LoadData --> DB
    EnsureDB --> RunAgent
    LoadData --> RunAgent
    RunAgent --> LLMChoice
    LLMChoice --> Ollama
    LLMChoice --> Gemini
    LLMChoice --> OpenAI
    Ollama --> Tools
    Gemini --> Tools
    OpenAI --> Tools
    Tools --> DB
    Ollama --> WriteOut
    Gemini --> WriteOut
    OpenAI --> WriteOut
    Format --> WriteOut
```

---

## LLM selection (agent entry)

```mermaid
flowchart LR
    A[run_agent] --> B{USE_LOCAL_LLM\nor OLLAMA_MODEL?}
    B -->|Yes| C[_run_agent_ollama]
    B -->|No| D{GEMINI_API_KEY?}
    D -->|Yes| E[_run_agent_gemini]
    D -->|No| F{OPENAI_API_KEY?}
    F -->|Yes| G[OpenAI tool-calling loop]
    F -->|No| H[Error: set one of\nOllama / Gemini / OpenAI]
```

---

## Ollama / Gemini path (single-prompt)

Context is gathered once by calling tools (including get_yoy_growth, get_top_flows, get_trade_trends); one prompt is sent to the LLM; report is parsed from the response.

```mermaid
flowchart TB
    subgraph Gather["Gather context (no LLM yet)"]
        T1["list_regions()"]
        T2["list_sectors()"]
        T3["rag_retrieve('BRICS decoupling trade')"]
        T4["rag_retrieve('US China electronics')"]
        T5["query_trade_flows(year_from=2022, limit=30)"]
        T6["get_yoy_growth(year_from=2022, year_to=2024)"]
        T7["get_top_flows(n=10, year_from=2022)"]
        T8["get_trade_trends(limit=10)"]
        T9["rag_retrieve(user_query) if set"]
    end

    subgraph Build["Build prompt"]
        Ctx["Single context string"]
        Prompt["One user prompt:\n'Use this data... REPORT_START ... REPORT_END'"]
    end

    subgraph Call["LLM call"]
        O["Ollama: localhost:11434\nor\nGemini: GEMINI_MODEL"]
    end

    subgraph Parse["Parse & return"]
        Extract["Extract text between\nREPORT_START and REPORT_END"]
    end

    T1 --> Ctx
    T2 --> Ctx
    T3 --> Ctx
    T4 --> Ctx
    T5 --> Ctx
    T6 --> Ctx
    T7 --> Ctx
    T8 --> Ctx
    T9 --> Ctx
    Ctx --> Prompt
    Prompt --> O
    O --> Extract
```

---

## OpenAI path (multi-turn tool-calling)

The model decides when to call tools and when to output the final report. Tools include list_regions, list_sectors, query_trade_flows, get_region_summary, get_sector_summary, rag_retrieve, get_yoy_growth, get_top_flows, get_trade_trends.

```mermaid
flowchart TB
    Start["Start: system prompt + user prompt\n(Focus on BRICS...)"]
    Define["Define tools for API:\nlist_regions, list_sectors, query_trade_flows,\nget_region_summary, get_sector_summary, rag_retrieve,\nget_yoy_growth, get_top_flows, get_trade_trends"]

    Start --> Define
    Define --> Call["Call OpenAI API\n(messages + tools)"]

    Call --> Response{"Model response"}
    Response -->|Contains REPORT_START/REPORT_END| Parse["Parse report text\n→ return to main.py"]
    Response -->|Contains tool_calls| RunTools["Run each tool with\nmodel's arguments"]
    RunTools --> Append["Append tool results\nto conversation"]
    Append --> Call

    Response -->|Neither| Next["Next round (max 8)\nor return fallback"]
    Next --> Call
```

---

## Data flow: tools and DB

All report data comes from the SQLite DB. Data can be ingested via main.py (--data, --data-url) or scripts/fetch_comtrade.py. Tools are either called by the agent (Ollama/Gemini) or by the model via the API (OpenAI).

```mermaid
flowchart LR
    subgraph Ingest["Ingestion"]
        CSV["--data CSV"]
        URL["--data-url"]
        Comtrade["fetch_comtrade.py"]
    end

    subgraph DB["data/trade.db"]
        TF["trade_flows\n(region, partner, sector, year, value_usd)"]
        RAG["rag_chunks\n(source, content, metadata)"]
    end

    subgraph Tools["tools.py"]
        list_regions["list_regions"]
        list_sectors["list_sectors"]
        query_flows["query_trade_flows"]
        region_summary["get_region_summary"]
        sector_summary["get_sector_summary"]
        rag_retrieve["rag_retrieve"]
        yoy["get_yoy_growth"]
        top["get_top_flows"]
        trends["get_trade_trends"]
    end

    CSV --> TF
    URL --> TF
    Comtrade --> TF
    TF --> list_regions
    TF --> list_sectors
    TF --> query_flows
    TF --> region_summary
    TF --> sector_summary
    TF --> yoy
    TF --> top
    TF --> trends
    RAG --> rag_retrieve
```

---

## Output format flow (main.py after run_agent)

The report string is written according to --format.

```mermaid
flowchart LR
    Report["Report text\n(from agent)"]
    F{"--format"}
    F -->|text| T["Write to file\n(.txt or timestamped)"]
    F -->|html| H["_report_to_html()\n→ .html file"]
    F -->|linkedin| L["Report file +\nLINKEDIN_SUMMARY.txt"]
    F -->|json| J["_report_to_json()\n→ .json\n(summary, bullets, so_what, whats_next)"]
    Report --> F
    T --> Out["File + console"]
    H --> Out
    L --> Out
    J --> Out
```

---

## End-to-end sequence

```mermaid
sequenceDiagram
    participant User
    participant main as main.py
    participant db as database.py
    participant agent as agent.py
    participant tools as tools.py
    participant LLM as Ollama / Gemini / OpenAI

    User->>main: python main.py -q "BRICS" -o report.txt (or -f json/html/linkedin)
    main->>main: Load .env
    main->>db: ensure_db()
    db->>db: Create/seed data/trade.db
    main->>db: Load --data CSV or --data-url into trade_flows (if present)
    main->>agent: run_agent(user_query="BRICS")

    alt Ollama or Gemini
        agent->>tools: list_regions(), list_sectors(), rag_retrieve(), query_trade_flows(), get_yoy_growth(), get_top_flows(), get_trade_trends()
        tools->>db: Query trade_flows, rag_chunks
        tools-->>agent: Context strings
        agent->>agent: Build single prompt with context
        agent->>LLM: One LLM call
        LLM-->>agent: Response with REPORT_START...REPORT_END
    else OpenAI
        agent->>LLM: System + user message + tool definitions
        loop Until report or max rounds
            LLM-->>agent: tool_calls or REPORT_START/REPORT_END
            agent->>tools: Run requested tools
            tools->>db: Query
            tools-->>agent: Tool results
            agent->>LLM: Append tool results, next round
        end
    end

    agent->>agent: Parse REPORT_START/REPORT_END
    agent-->>main: Report text
    main->>main: Write by --format (text/html/linkedin/json), print to console
    main-->>User: Done
```

---

## Summary

| Stage        | Action |
|-------------|--------|
| **Entry**   | `main.py` — CLI: `-q`, `-o`, `-d` (CSV), `--data-url`, `-f` (text \| html \| linkedin \| json). Optional: `scripts/fetch_comtrade.py` or `scripts/run_scheduled.sh`. |
| **Config**  | `.env` → API keys, `USE_LOCAL_LLM`, `OLLAMA_MODEL`, `OPENAI_MODEL`, `GEMINI_MODEL`, optional `COMTRADE_API_KEY`. |
| **DB / Ingest** | `ensure_db()` → `data/trade.db`. Optional: `--data` CSV, `--data-url`, or `scripts/fetch_comtrade.py` → `trade_flows`. |
| **Agent**   | `run_agent()` → Ollama → Gemini → OpenAI (else error). |
| **Ollama/Gemini** | Call tools (incl. get_yoy_growth, get_top_flows, get_trade_trends) → one prompt → one LLM call → parse report. |
| **OpenAI**  | Multi-turn; model calls tools → repeat until REPORT_START/REPORT_END. |
| **Output**  | Report → file by `-f` (text / html / linkedin + one-liner / json) + console. |

See **RUN_AND_LOGIC.md** for step-by-step run instructions and more detail.
