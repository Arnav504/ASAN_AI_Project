# Presenting ASAN Macro on LinkedIn

Use this guide to describe and showcase the project on LinkedIn so it stands out as a dynamic, data-driven AI project.

---

## Elevator pitch (1–2 sentences)

**ASAN Macro** is an AI-powered trade and maritime analysis agent that turns raw trade data (CSV, URLs, optional APIs) into structured sentiment reports with “so what” and “what’s next” insights—using an LLM plus a database, RAG, and custom analysis tools (YoY growth, top flows, trends).

---

## Key bullets for your post or profile

- **Dynamic data**: Ingest from local CSV, CSV URLs, and optional JSON APIs (e.g. UN Comtrade–style) so analysis isn’t limited to static files.
- **Richer analysis**: Custom tools for year-over-year growth, top flows by value, and trade trends so the LLM reasons over real metrics, not just raw rows.
- **LLM flexibility**: Supports OpenAI (e.g. gpt-4o / gpt-4o-mini), Google Gemini (e.g. gemini-2.0-flash / gemini-1.5-pro), and local Ollama; model choice via env for better quality when you need it.
- **End-to-end pipeline**: Single command from data + optional focus query to report file (text, HTML, or LinkedIn-ready one-liner).
- **Stack**: Python, SQLite, OpenAI / Gemini / Ollama, RAG-style retrieval, function-calling agents.

---

## Suggested LinkedIn post template

**Headline (optional):**  
Built an AI agent that turns trade data into executive-style sentiment reports.

**Body:**  
I worked with [team] on **ASAN Macro**: an AI agent that analyzes maritime and trade data to study shifts in global trade (e.g. BRICS, US–China decoupling, South–South trade).

- **Data:** We support dynamic ingestion—local CSV, CSV from URLs, and optional APIs—so the pipeline isn’t tied to one static dataset.
- **Analysis:** Custom tools compute YoY growth, top flows, and trends so the LLM can cite real numbers and themes.
- **Models:** We use [OpenAI / Gemini / local Ollama] with a configurable model (e.g. gpt-4o or Gemini 1.5 Pro) for higher-quality synthesis when needed.
- **Output:** One command produces a full report plus optional HTML and a short “LinkedIn one-liner” for sharing.

Tech: Python, SQLite, RAG, tool-augmented LLMs. Great example of turning messy trade data into clear “so what” and “what’s next” for strategy and policy.

[Link to repo or demo]

---

## How to demo in a post or video

1. **Show the command:**  
   `python main.py -q "BRICS" -o report.txt -f linkedin`
2. **Show the report** (or a snippet) and the generated `LINKEDIN_SUMMARY.txt`.
3. **Mention data options:**  
   “We can point it at a CSV on the web with `--data-url` or load from an API so the same pipeline works for different data sources.”
4. **Optional:** Show `-f html` and open the generated HTML in a browser for a shareable report.

---

## Skills and keywords to include

- **AI/ML:** LLM agents, RAG, function calling, prompt engineering  
- **Data:** Data ingestion pipelines, SQL, CSV/JSON, optional API integration  
- **Analysis:** Trade/maritime analysis, sentiment synthesis, YoY growth, trend detection  
- **Tech:** Python, SQLite, OpenAI API, Google Gemini, Ollama  

---

## Repo description (short)

**ASAN Macro** – AI-powered trade and maritime analysis agent. Dynamic data ingestion (CSV, URLs, APIs), custom analysis tools (YoY growth, top flows, trends), and configurable LLMs (OpenAI, Gemini, Ollama) produce sentiment reports with “so what” and “what’s next.” Python, SQLite, RAG, tool-augmented LLMs.
