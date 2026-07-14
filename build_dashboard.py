#!/usr/bin/env python3
"""Builds the dashboard.html artifact source from latest_summary.json.

Run this after cowork_collect.py each day, then pass the output HTML path
to mcp__cowork__create_artifact (first run) or mcp__cowork__update_artifact
(subsequent runs) with id "captiveaire-tampa-bay-permit-leads".
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CaptiveAire Tampa Bay Permit Leads</title>
<script src="https://cdn.jsdelivr.net/npm/gridjs@5.0.2/dist/gridjs.umd.js" integrity="sha384-/XXDzxe4FsGiAe50i/u9pY/Vy/uX654MHB1xoc1BJNnH1WXHhqHga9g3q5tF4gj7" crossorigin="anonymous"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gridjs@5.0.2/dist/theme/mermaid.min.css" integrity="sha384-jZvDSsmGB9oGGT/4l9bHXGoAv1OxvG/cFmSo0dZaSqmBgvQTKDBFAMftlXTmMbNW" crossorigin="anonymous">
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 28px 40px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: #f7f7f8; color: #1a1a1a;
  }}
  h1 {{ font-size: 20px; margin: 0 0 2px; }}
  .subtitle {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
  .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 22px; }}
  .card {{
    flex: 1 1 140px; background: #fff; border-radius: 10px; padding: 14px 16px;
    border: 1px solid #e5e5e7; text-align: left;
  }}
  .card .num {{ font-size: 26px; font-weight: 700; line-height: 1.1; }}
  .card .label {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .very-high .num {{ color: #b91c1c; }}
  .high .num {{ color: #c2410c; }}
  .medium .num {{ color: #a16207; }}
  .low .num {{ color: #6b7280; }}
  .total .num {{ color: #1a1a1a; }}
  .source-status {{
    background: #fff; border: 1px solid #e5e5e7; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 20px; font-size: 12.5px; color: #444;
  }}
  .source-status table {{ width: 100%; border-collapse: collapse; }}
  .source-status td {{ padding: 3px 8px 3px 0; }}
  .source-status td.n {{ text-align: right; font-variant-numeric: tabular-nums; color: #111; font-weight: 600; }}
  .pill {{
    display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px;
    font-weight: 600; color: #fff; white-space: nowrap;
  }}
  .pill.Very-High {{ background: #dc2626; }}
  .pill.High {{ background: #ea580c; }}
  .pill.Medium {{ background: #ca8a04; }}
  .pill.Low {{ background: #9ca3af; }}
  .pill.Not-Relevant {{ background: #d1d5db; color: #444; }}
  #grid {{ font-size: 13px; }}
  a.src-link {{ color: #2563eb; text-decoration: none; font-size: 12px; }}
  a.src-link:hover {{ text-decoration: underline; }}
  .desc-cell {{ max-width: 420px; white-space: normal; line-height: 1.35; }}
  footer {{ margin-top: 18px; font-size: 11.5px; color: #999; }}
</style>
</head>
<body>

<h1>CaptiveAire &mdash; Tampa Bay Commercial Permit Leads</h1>
<div class="subtitle">Generated {generated_at} &nbsp;&middot;&nbsp; run date {run_date} &nbsp;&middot;&nbsp; {new_today} new today &nbsp;&middot;&nbsp; showing all {active_total} active leads from the last {active_window_days} days</div>

<div class="cards">
  <div class="card very-high"><div class="num">{very_high}</div><div class="label">Very High priority</div></div>
  <div class="card high"><div class="num">{high}</div><div class="label">High priority</div></div>
  <div class="card medium"><div class="num">{medium}</div><div class="label">Medium priority</div></div>
  <div class="card low"><div class="num">{low}</div><div class="label">Low priority</div></div>
  <div class="card total"><div class="num">{new_today}</div><div class="label">New today</div></div>
</div>

<div class="source-status">
  <strong>Source status this run</strong>
  <table>{source_rows}</table>
</div>

<div id="grid"></div>

<footer>
  CaptiveAire permit lead system &middot; 6 verified public sources (City of Tampa, Hillsborough County x2, City of Lakeland,
  Hernando County, Pinellas County DRS) &middot; scored via keyword + heuristic rules, no LLM &middot; full data also saved to
  CaptiveAire_Leads_Latest.csv in your connected folder.
</footer>

<script>
const LEADS = {leads_json};

function pillClass(cat) {{ return cat.replace(/\\s+/g, '-'); }}

const gridData = LEADS.map(r => [
  {{ cat: r.priority_category, score: r.score }},
  r.jurisdiction || '',
  r.permit_number || '',
  {{ issued: r.issue_date || '', applied: r.application_date || '' }},
  [r.address, r.city].filter(Boolean).join(', '),
  r.work_description || '',
  r.status || '',
  r.source_record_url || ''
]);

new gridjs.Grid({{
  columns: [
    {{
      name: 'Priority',
      sort: {{ compare: (a, b) => b.score - a.score }},
      formatter: (cell) => gridjs.html(`<span class="pill ${{pillClass(cell.cat)}}">${{cell.cat}} (${{cell.score}})</span>`)
    }},
    {{ name: 'Jurisdiction' }},
    {{ name: 'Permit #' }},
    {{
      name: 'Permit Date',
      sort: {{ compare: (a, b) => (a.issued || a.applied || '').localeCompare(b.issued || b.applied || '') }},
      formatter: (cell) => cell.issued
        ? gridjs.html(`<span title="Issued">${{cell.issued}}</span>`)
        : (cell.applied ? gridjs.html(`<span title="Applied (not yet issued)" style="color:#888">${{cell.applied}} <em>(applied)</em></span>`) : '')
    }},
    {{ name: 'Address' }},
    {{
      name: 'Description',
      formatter: (cell) => gridjs.html(`<div class="desc-cell">${{cell ? cell.replace(/</g,'&lt;') : ''}}</div>`)
    }},
    {{ name: 'Status' }},
    {{
      name: 'Source',
      formatter: (cell) => cell ? gridjs.html(`<a class="src-link" href="${{cell}}" target="_blank" rel="noopener">Open &rarr;</a>`) : ''
    }},
  ],
  data: gridData,
  sort: true,
  search: true,
  pagination: {{ limit: 20 }},
  className: {{ table: 'gridjs-table' }},
}}).render(document.getElementById("grid"));
</script>

</body>
</html>
"""


def build(summary_path: Path, out_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    source_rows = "".join(
        f"<tr><td>{html.escape(info['jurisdiction'])}</td>"
        f"<td class='n'>{info['fetched']} fetched</td>"
        f"<td class='n'>{info['new']} new</td></tr>"
        for info in summary["per_source_counts"].values()
    )

    out_html = TEMPLATE.format(
        generated_at=html.escape(summary["generated_at"]),
        run_date=html.escape(summary["run_date"]),
        new_today=summary.get("new_today", summary.get("total_new", 0)),
        active_total=summary.get("active_total", len(summary.get("leads", []))),
        active_window_days=summary.get("active_window_days", 30),
        very_high=summary["very_high"],
        high=summary["high"],
        medium=summary["medium"],
        low=summary["low"],
        source_rows=source_rows,
        leads_json=json.dumps(summary["leads"]),
    )
    out_path.write_text(out_html, encoding="utf-8")
    print(f"Wrote {out_path} ({len(out_html):,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(Path(args.summary), Path(args.out))
