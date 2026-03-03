"""
User-created tools called by the LLM for augmentation (required by project rubric).
These tools query the trade database and RAG store so the LLM can ground its analysis.
"""
import sqlite3
from pathlib import Path
from config import DB_PATH


def _get_conn():
    return sqlite3.connect(str(DB_PATH))


def list_regions() -> str:
    """List all reporter and partner regions in the trade database."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT reporter_region FROM trade_flows UNION SELECT DISTINCT partner_region FROM trade_flows ORDER BY 1"
    )
    rows = cur.fetchall()
    conn.close()
    return "Regions: " + ", ".join(r[0] for r in rows)


def list_sectors() -> str:
    """List all sectors in the trade database."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT sector FROM trade_flows ORDER BY 1")
    rows = cur.fetchall()
    conn.close()
    return "Sectors: " + ", ".join(r[0] for r in rows)


def query_trade_flows(
    reporter: str = None,
    partner: str = None,
    sector: str = None,
    year_from: int = None,
    year_to: int = None,
    limit: int = 50,
) -> str:
    """
    Query trade flows. Pass reporter_region, partner_region, sector, year_from, year_to as filters.
    Returns a text summary of matching flows (year, reporter, partner, sector, flow_type, value_usd).
    """
    conn = _get_conn()
    cur = conn.cursor()
    q = "SELECT year, reporter_region, partner_region, sector, flow_type, value_usd FROM trade_flows WHERE 1=1"
    params = []
    if reporter:
        q += " AND reporter_region = ?"
        params.append(reporter)
    if partner:
        q += " AND partner_region = ?"
        params.append(partner)
    if sector:
        q += " AND sector = ?"
        params.append(sector)
    if year_from is not None:
        q += " AND year >= ?"
        params.append(year_from)
    if year_to is not None:
        q += " AND year <= ?"
        params.append(year_to)
    q += " ORDER BY year, value_usd DESC LIMIT ?"
    params.append(limit)
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return "No trade flows found for the given filters."
    lines = ["year | reporter | partner | sector | flow_type | value_usd"]
    for r in rows:
        lines.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]:.0f}")
    return "\n".join(lines)


def get_region_summary(region: str) -> str:
    """
    Get a summary of trade for one region (as reporter or partner): total flows by year and sector.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT year, sector, flow_type, SUM(value_usd) as total
        FROM trade_flows
        WHERE reporter_region = ? OR partner_region = ?
        GROUP BY year, sector, flow_type
        ORDER BY year, total DESC
        """,
        (region, region),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return f"No data found for region: {region}"
    lines = [f"Trade summary for {region} (year | sector | flow_type | total_usd):"]
    for r in rows:
        lines.append(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]:.0f}")
    return "\n".join(lines)


def get_sector_summary(sector: str) -> str:
    """
    Get a summary of trade for one sector across all regions and years.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT year, reporter_region, partner_region, flow_type, SUM(value_usd) as total
        FROM trade_flows
        WHERE sector = ?
        GROUP BY year, reporter_region, partner_region, flow_type
        ORDER BY year, total DESC
        LIMIT 30
        """,
        (sector,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return f"No data found for sector: {sector}"
    lines = [f"Sector {sector} (year | reporter | partner | flow_type | total_usd):"]
    for r in rows:
        lines.append(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]:.0f}")
    return "\n".join(lines)


def rag_retrieve(query: str, limit: int = 5) -> str:
    """
    Retrieve relevant context from the RAG store (stored trade bulletins/summaries).
    Use a short query like 'BRICS decoupling' or 'US China electronics'.
    """
    conn = _get_conn()
    cur = conn.cursor()
    # Simple keyword retrieval: chunks containing any word from query
    words = [w.strip().lower() for w in query.split() if len(w.strip()) > 1]
    if not words:
        cur.execute("SELECT source, content FROM rag_chunks ORDER BY id LIMIT ?", (limit,))
    else:
        placeholders = " OR ".join("content LIKE ?" for _ in words)
        params = [f"%{w}%" for w in words] + [limit]
        cur.execute(
            f"SELECT source, content FROM rag_chunks WHERE {placeholders} LIMIT ?",
            params,
        )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return "No relevant RAG chunks found."
    return "\n---\n".join(f"[{r[0]}] {r[1]}" for r in rows)


# Registry for the agent: name -> (function, description)
TOOLS = [
    ("list_regions", list_regions, "List all regions in the trade database."),
    ("list_sectors", list_sectors, "List all sectors in the trade database."),
    ("query_trade_flows", query_trade_flows, "Query trade flows with optional filters: reporter, partner, sector, year_from, year_to, limit."),
    ("get_region_summary", get_region_summary, "Get trade summary for one region (as reporter or partner). Argument: region name."),
    ("get_sector_summary", get_sector_summary, "Get trade summary for one sector across regions and years. Argument: sector name."),
    ("rag_retrieve", rag_retrieve, "Retrieve relevant context from stored trade bulletins. Argument: short query string (e.g. 'BRICS decoupling')."),
]

TOOL_BY_NAME = {name: fn for name, fn, _ in TOOLS}
