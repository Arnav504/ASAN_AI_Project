#!/usr/bin/env python3
"""
Update the evaluation metrics table in PROJECT_REPORT_ANSWERS.md from
evaluation/evaluation_results.json aggregate_metrics.

Usage: from project root:
  .venv/bin/python scripts/update_report_metrics.py
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = PROJECT_ROOT / "evaluation" / "evaluation_results.json"
REPORT_MD = PROJECT_ROOT / "PROJECT_REPORT_ANSWERS.md"

# Order of keys for the table (matches run_evaluation.py aggregate_metrics)
METRIC_KEYS = [
    "n_runs",
    "total_runtime_sec",
    "avg_runtime_sec",
    "avg_char_count",
    "avg_word_count",
    "pct_has_summary",
    "pct_has_key_regions_sectors",
    "pct_has_so_what",
    "pct_has_whats_next",
    "pct_all_four_sections",
    "pct_non_empty",
]


def format_value(v):
    """Format metric value for markdown table (int or float)."""
    if isinstance(v, float):
        return str(v) if v != int(v) else str(int(v))
    return str(v)


def build_table(agg: dict) -> str:
    lines = [
        "| Metric | Value |",
        "|--------|--------|",
    ]
    for k in METRIC_KEYS:
        if k in agg:
            lines.append(f"| {k} | {format_value(agg[k])} |")
    return "\n".join(lines)


def main():
    if not RESULTS_JSON.exists():
        raise SystemExit(f"Results file not found: {RESULTS_JSON}")

    with open(RESULTS_JSON, encoding="utf-8") as f:
        data = json.load(f)

    agg = data.get("aggregate_metrics")
    if not agg:
        raise SystemExit("No aggregate_metrics in results JSON")

    content = REPORT_MD.read_text(encoding="utf-8")

    # Pattern: table starts with | Metric | Value | and ends before the next paragraph
    table_start = "| Metric | Value |"
    table_end_marker = "*Source:"

    start_idx = content.find(table_start)
    if start_idx == -1:
        raise SystemExit("Could not find metrics table in PROJECT_REPORT_ANSWERS.md")

    end_idx = content.find(table_end_marker, start_idx)
    if end_idx == -1:
        raise SystemExit("Could not find end of table (Source line) in PROJECT_REPORT_ANSWERS.md")

    # Replace from start of table through the full *Source: ...* line
    line_end = content.find("\n", end_idx)
    if line_end == -1:
        line_end = len(content)
    replace_end = line_end + 1  # include newline after source line

    new_table = build_table(agg)
    new_block = (
        f"{new_table}\n\n"
        "*Source: `evaluation/evaluation_results.json` → `aggregate_metrics`. "
        "Run `.venv/bin/python scripts/update_report_metrics.py` after re-running the evaluation to refresh.*"
    )

    new_content = content[:start_idx] + new_block + content[replace_end:]

    REPORT_MD.write_text(new_content, encoding="utf-8")
    print(f"Updated metrics table in {REPORT_MD}")
    for k in METRIC_KEYS:
        if k in agg:
            print(f"  {k}: {agg[k]}")


if __name__ == "__main__":
    main()
