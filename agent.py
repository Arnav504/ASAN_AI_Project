"""
ASAN Macro agent: uses LLM with tool augmentation (DB + RAG) to produce
trade sentiment/synthesis reports. Satisfies: LLM use, augmentation (tools + DB/RAG),
non-triviality (thematic synthesis, filtering, extrapolation, so-what/what-next).
"""
import json
from config import get_openai_api_key, get_gemini_api_key, use_local_ollama, get_ollama_base_url, get_ollama_model, get_openai_model, get_gemini_model
from tools import TOOLS, TOOL_BY_NAME

SYSTEM_PROMPT = """You are ASAN Macro, an analyst agent that studies global trade (physical goods) and shifting geopolitical trade landscape. You have access to tools that query a trade database and a RAG store of trade bulletins.

Your tasks:
1. Use the tools to gather data on regions, sectors, and flows (e.g. BRICS, US-China, Vietnam, Mexico, minerals, electronics, textiles).
2. Synthesize themes: decoupling, South-South trade growth, sector shifts.
3. Produce a short trade sentiment report that includes:
   - Summary of what the data shows (thematic synthesis)
   - Key regions and sectors leading any shift
   - "So what": implications for trade and geopolitics
   - "What's next": what to watch or expect next

After you have enough context from the tools, output your final report in this exact format:

REPORT_START
[Your report text here: summary, so what, what's next]
REPORT_END

Do not output REPORT_START/REPORT_END until you are ready to give the final report. Call multiple tools first to gather data."""


def _parse_tool_calls(content: str):
    """Parse tool calls from LLM output. Expects lines like: TOOL: tool_name | arg1 | arg2 or TOOL: tool_name"""
    out = []
    for line in content.split("\n"):
        line = line.strip()
        if line.upper().startswith("TOOL:"):
            rest = line[5:].strip()
            parts = [p.strip() for p in rest.split("|")]
            name = parts[0].strip() if parts else ""
            args = parts[1:] if len(parts) > 1 else []
            if name in TOOL_BY_NAME:
                out.append((name, args))
    return out


def _run_tool(name: str, args: list) -> str:
    import tools as T
    fn = T.TOOL_BY_NAME.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        if name == "list_regions":
            return T.list_regions()
        if name == "list_sectors":
            return T.list_sectors()
        if name == "query_trade_flows":
            kwargs = {}
            if len(args) >= 1 and args[0]:
                kwargs["reporter"] = args[0]
            if len(args) >= 2 and args[1]:
                kwargs["partner"] = args[1]
            if len(args) >= 3 and args[2]:
                kwargs["sector"] = args[2]
            if len(args) >= 4 and args[3]:
                try:
                    kwargs["year_from"] = int(args[3])
                except ValueError:
                    pass
            if len(args) >= 5 and args[4]:
                try:
                    kwargs["year_to"] = int(args[4])
                except ValueError:
                    pass
            if len(args) >= 6 and args[5]:
                try:
                    kwargs["limit"] = int(args[5])
                except ValueError:
                    pass
            return fn(**kwargs)
        if name == "get_region_summary":
            return fn(args[0] if args else "")
        if name == "get_sector_summary":
            return fn(args[0] if args else "")
        if name == "rag_retrieve":
            return fn(args[0] if args else "trade", limit=5)
        if name == "get_yoy_growth":
            kwargs = {}
            if len(args) >= 1 and args[0]:
                kwargs["region"] = args[0]
            if len(args) >= 2 and args[1]:
                kwargs["sector"] = args[1]
            if len(args) >= 3 and args[2]:
                try:
                    kwargs["year_from"] = int(args[2])
                except ValueError:
                    pass
            if len(args) >= 4 and args[3]:
                try:
                    kwargs["year_to"] = int(args[3])
                except ValueError:
                    pass
            return fn(**kwargs)
        if name == "get_top_flows":
            kwargs = {"n": 10}
            if len(args) >= 1 and args[0]:
                try:
                    kwargs["n"] = int(args[0])
                except ValueError:
                    pass
            if len(args) >= 2 and args[1]:
                try:
                    kwargs["year_from"] = int(args[1])
                except ValueError:
                    pass
            if len(args) >= 3 and args[2]:
                try:
                    kwargs["year_to"] = int(args[2])
                except ValueError:
                    pass
            if len(args) >= 4 and args[3]:
                kwargs["flow_type"] = args[3]
            return fn(**kwargs)
        if name == "get_trade_trends":
            kwargs = {}
            if len(args) >= 1 and args[0]:
                kwargs["region"] = args[0]
            if len(args) >= 2 and args[1]:
                try:
                    kwargs["limit"] = int(args[1])
                except ValueError:
                    pass
            return fn(**kwargs)
        return fn()
    except Exception as e:
        return f"Tool error: {e}"


def run_agent(user_query: str = None, max_rounds: int = 8) -> str:
    """
    Run the ASAN Macro agent: LLM + tools -> final report.
    user_query: optional focus (e.g. "BRICS" or "US-China electronics"). If None, analyze overall trade shift.
    Returns the extracted report text (between REPORT_START and REPORT_END) or full response.
    """
    if use_local_ollama():
        return _run_agent_ollama(user_query, max_rounds)
    if get_gemini_api_key():
        return _run_agent_gemini(user_query, max_rounds)
    client = _get_client()
    if not client:
        return "Error: Set USE_LOCAL_LLM=1 and run Ollama, or set OPENAI_API_KEY or GEMINI_API_KEY in .env."

    openai_tools = [
        {"type": "function", "function": {"name": "list_regions", "description": "List all regions in the trade database."}},
        {"type": "function", "function": {"name": "list_sectors", "description": "List all sectors in the trade database."}},
        {"type": "function", "function": {"name": "query_trade_flows", "description": "Query trade flows with optional filters.", "parameters": {"type": "object", "properties": {"reporter": {"type": "string"}, "partner": {"type": "string"}, "sector": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}, "limit": {"type": "integer"}}}}},
        {"type": "function", "function": {"name": "get_region_summary", "description": "Get trade summary for one region.", "parameters": {"type": "object", "properties": {"region": {"type": "string"}}}}},
        {"type": "function", "function": {"name": "get_sector_summary", "description": "Get trade summary for one sector.", "parameters": {"type": "object", "properties": {"sector": {"type": "string"}}}}},
        {"type": "function", "function": {"name": "rag_retrieve", "description": "Retrieve context from trade bulletins. Argument: short query string.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}},
        {"type": "function", "function": {"name": "get_yoy_growth", "description": "Get year-over-year growth in trade value. Optional filters: region, sector, year_from, year_to.", "parameters": {"type": "object", "properties": {"region": {"type": "string"}, "sector": {"type": "string"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}}}}},
        {"type": "function", "function": {"name": "get_top_flows", "description": "Get top N trade flows by value. Optional: n, year_from, year_to, flow_type.", "parameters": {"type": "object", "properties": {"n": {"type": "integer"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"}, "flow_type": {"type": "string"}}}}},
        {"type": "function", "function": {"name": "get_trade_trends", "description": "Summarize trade trends (sectors/partners that grew or shrank). Optional: region, limit.", "parameters": {"type": "object", "properties": {"region": {"type": "string"}, "limit": {"type": "integer"}}}}},
    ]

    prompt = (
        "Analyze the trade database and RAG context using the tools, then produce the sentiment report."
        if not user_query
        else f"Focus on: {user_query}. Use tools to get data, then produce the sentiment report."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    for _ in range(max_rounds):
        response = client.chat.completions.create(
            model=get_openai_model(),
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0.3,
        )
        choice = response.choices[0]
        msg = choice.message
        content = (msg.content or "").strip()

        # Final report in content
        if content and "REPORT_START" in content and "REPORT_END" in content:
            start = content.find("REPORT_START") + len("REPORT_START")
            end = content.find("REPORT_END")
            return content[start:end].strip()

        # OpenAI tool calls
        if getattr(msg, "tool_calls", None):
            messages.append(msg)
            for tc in msg.tool_calls:
                if tc.function.name not in TOOL_BY_NAME:
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": "Unknown tool."})
                    continue
                try:
                    kwargs = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    kwargs = {}
                result = _run_tool_native(tc.function.name, kwargs)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        # Fallback: parse TOOL: lines from content (if no tool_calls)
        tool_calls = _parse_tool_calls(content)
        if tool_calls:
            tool_results = []
            for name, args in tool_calls:
                result = _run_tool(name, args)
                tool_results.append(f"[{name}]:\n{result}")
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {"role": "user", "content": "Tool results:\n" + "\n\n".join(tool_results) + "\n\nNow produce your final report in REPORT_START/REPORT_END format."}
            )
            continue

        if content:
            return content
    return "Agent reached max rounds without producing REPORT_START/REPORT_END."


def _run_agent_ollama(user_query: str = None, max_rounds: int = 8) -> str:
    """Use local Ollama (open-source model). No API key or quota. Pre-gathers tool data, single prompt."""
    import tools as T
    base_url = get_ollama_base_url()
    model = get_ollama_model()
    context_parts = [
        T.list_regions(),
        T.list_sectors(),
        T.rag_retrieve("BRICS decoupling trade"),
        T.rag_retrieve("US China electronics"),
        T.query_trade_flows(year_from=2022, limit=30),
        T.get_yoy_growth(year_from=2022, year_to=2024),
        T.get_top_flows(n=10, year_from=2022),
        T.get_trade_trends(limit=10),
    ]
    if user_query:
        context_parts.append(T.rag_retrieve(user_query))
    context = "\n\n".join(context_parts)
    prompt = f"""Use this trade data and context to write a short sentiment report.

Context and data:
{context}

Write a report that includes: (1) Summary of what the data shows, (2) Key regions/sectors, (3) "So what" implications, (4) "What's next".
Output in this exact format:
REPORT_START
[your report]
REPORT_END"""
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key="ollama")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        text = (response.choices[0].message.content or "").strip()
        if "REPORT_START" in text and "REPORT_END" in text:
            start = text.find("REPORT_START") + len("REPORT_START")
            end = text.find("REPORT_END")
            return text[start:end].strip()
        return text
    except Exception as e:
        return f"Ollama error (is Ollama running? try: ollama serve && ollama run {model}): {e}"


def _run_agent_gemini(user_query: str = None, max_rounds: int = 8) -> str:
    """Use Google Gemini (free tier) when OpenAI quota is exceeded."""
    import tools as T
    key = get_gemini_api_key()
    if not key:
        return "Error: GEMINI_API_KEY not set in .env"
    try:
        import google.generativeai as genai
    except ImportError:
        return "Error: Install with: pip install google-generativeai"
    genai.configure(api_key=key)
    model = genai.GenerativeModel(get_gemini_model())
    # Gather context by calling tools once
    context_parts = [
        T.list_regions(),
        T.list_sectors(),
        T.rag_retrieve("BRICS decoupling trade"),
        T.rag_retrieve("US China electronics"),
        T.query_trade_flows(year_from=2022, limit=30),
        T.get_yoy_growth(year_from=2022, year_to=2024),
        T.get_top_flows(n=10, year_from=2022),
        T.get_trade_trends(limit=10),
    ]
    if user_query:
        context_parts.append(T.rag_retrieve(user_query))
    context = "\n\n".join(context_parts)
    prompt = f"""Use this trade data and context to write a short sentiment report.

Context and data:
{context}

Write a report that includes: (1) Summary of what the data shows, (2) Key regions/sectors, (3) "So what" implications, (4) "What's next".
Output in this exact format:
REPORT_START
[your report]
REPORT_END"""
    try:
        response = model.generate_content(prompt, generation_config={"temperature": 0.3})
        text = (response.text or "").strip()
        if "REPORT_START" in text and "REPORT_END" in text:
            start = text.find("REPORT_START") + len("REPORT_START")
            end = text.find("REPORT_END")
            return text[start:end].strip()
        return text
    except Exception as e:
        if "429" in str(e):
            import time
            time.sleep(45)
            try:
                response = model.generate_content(prompt, generation_config={"temperature": 0.3})
                text = (response.text or "").strip()
                if "REPORT_START" in text and "REPORT_END" in text:
                    start = text.find("REPORT_START") + len("REPORT_START")
                    end = text.find("REPORT_END")
                    return text[start:end].strip()
                return text
            except Exception as e2:
                return _sample_report_after_error(f"Gemini API error (after retry): {e2}")
        return f"Gemini API error: {e}"


def _sample_report_after_error(error_msg: str) -> str:
    sample = "Summary: BRICS intra-trade (minerals, energy) up; US-China electronics down; Vietnam/Mexico gaining. So what: Decoupling. What's next: Watch customs data and BRICS."
    return f"[API quota exceeded - sample report]\n\n{error_msg}\n\n--- Sample report ---\n{sample}"


def _run_tool_native(name: str, kwargs: dict) -> str:
    """Run tool with keyword arguments (from OpenAI function call)."""
    import tools as T
    fn = T.TOOL_BY_NAME.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        if name == "list_regions":
            return fn()
        if name == "list_sectors":
            return fn()
        if name == "query_trade_flows":
            return fn(
                reporter=kwargs.get("reporter"),
                partner=kwargs.get("partner"),
                sector=kwargs.get("sector"),
                year_from=kwargs.get("year_from"),
                year_to=kwargs.get("year_to"),
                limit=kwargs.get("limit", 50),
            )
        if name == "get_region_summary":
            return fn(kwargs.get("region") or "")
        if name == "get_sector_summary":
            return fn(kwargs.get("sector") or "")
        if name == "rag_retrieve":
            return fn(kwargs.get("query") or "trade", limit=kwargs.get("limit", 5))
        if name == "get_yoy_growth":
            return fn(
                region=kwargs.get("region"),
                sector=kwargs.get("sector"),
                year_from=kwargs.get("year_from"),
                year_to=kwargs.get("year_to"),
            )
        if name == "get_top_flows":
            return fn(
                n=kwargs.get("n", 10),
                year_from=kwargs.get("year_from"),
                year_to=kwargs.get("year_to"),
                flow_type=kwargs.get("flow_type"),
            )
        if name == "get_trade_trends":
            return fn(region=kwargs.get("region"), limit=kwargs.get("limit", 10))
        return fn()
    except Exception as e:
        return f"Tool error: {e}"


def _get_client():
    try:
        from openai import OpenAI
        key = get_openai_api_key()
        if key:
            return OpenAI(api_key=key)
    except ImportError:
        pass
    return None
