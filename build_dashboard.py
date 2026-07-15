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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js" integrity="sha384-iU8HYtnGQ8Cy4zl7gbNMOhsDTTKX02BTXptVP/vqAWIaTfM7isw76iyZCsjL2eVi" crossorigin="anonymous"></script>
<style>
  :root {{
    color-scheme: dark;
    /* CaptiveAire — "Forest slate" dark theme */
    --ca-bg: #13181a;
    --ca-card: #1c2224;
    --ca-card-alt: #20262a;
    --ca-border: #262d30;
    --ca-red: #A8291E;        /* Very High — darker red */
    --ca-red-on: #FCEAEA;
    --ca-red-light: #E08424;  /* High — orange */
    --ca-red-light-on: #3D1F02;
    --ca-green: #4CAF7D;      /* Medium */
    --ca-green-on: #0D2E1C;
    --ca-gray: #78838A;       /* Low */
    --ca-gray-on: #14181B;
    --ca-text: #E8ECEE;
    --ca-text-muted: #9AA4AA;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0 0 40px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--ca-bg); color: var(--ca-text);
    border-top: 4px solid var(--ca-red);
  }}
  .page {{ padding: 24px 28px 0; }}
  .brand-header {{
    display: flex; align-items: baseline; gap: 10px; margin: 0 0 2px;
  }}
  .brand-mark {{
    color: var(--ca-red); font-weight: 800; font-size: 20px; letter-spacing: 0.2px;
  }}
  h1 {{ font-size: 20px; margin: 0; font-weight: 600; color: var(--ca-text); }}
  .subtitle {{ color: var(--ca-text-muted); font-size: 13px; margin-bottom: 20px; }}
  .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 22px; }}
  .card {{
    flex: 1 1 140px; background: var(--ca-card); border-radius: 10px; padding: 14px 16px;
    border: 1px solid var(--ca-border); text-align: left;
  }}
  .card .num-row {{ display: flex; align-items: center; gap: 7px; }}
  .card .dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex: none; }}
  .card .num {{ font-size: 26px; font-weight: 700; line-height: 1.1; }}
  .card .label {{ font-size: 12px; color: var(--ca-text-muted); margin-top: 4px; }}
  .very-high .dot {{ background: var(--ca-red); }}
  .very-high .num {{ color: var(--ca-red); }}
  .high .dot {{ background: var(--ca-red-light); }}
  .high .num {{ color: var(--ca-red-light); }}
  .medium .dot {{ background: var(--ca-green); }}
  .medium .num {{ color: var(--ca-green); }}
  .low .dot {{ background: var(--ca-gray); }}
  .low .num {{ color: var(--ca-text-muted); }}
  .total .dot {{ background: var(--ca-text-muted); }}
  .total .num {{ color: var(--ca-text); }}
  .source-status {{
    background: var(--ca-card); border: 1px solid var(--ca-border); border-radius: 10px;
    padding: 12px 16px; margin-bottom: 20px; font-size: 12.5px; color: var(--ca-text-muted);
  }}
  .source-status-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
  .source-status strong {{ color: var(--ca-text); }}
  .src-reset {{ font-size: 11px; color: var(--ca-green); cursor: pointer; font-weight: 600; display: none; }}
  .src-reset.active {{ display: inline; }}
  .source-status table {{ width: 100%; border-collapse: collapse; }}
  .source-status td {{ padding: 5px 8px 5px 0; }}
  .source-status td.n {{ text-align: right; font-variant-numeric: tabular-nums; color: var(--ca-text); font-weight: 600; }}
  tr.src-row {{ cursor: pointer; }}
  tr.src-row td {{ border-radius: 6px; transition: background 0.1s; }}
  tr.src-row:hover td {{ background: var(--ca-card-alt); }}
  tr.src-row.active td {{ background: var(--ca-card-alt); }}
  tr.src-row.active td:first-child {{ color: var(--ca-red); font-weight: 700; }}
  .pill {{
    display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px;
    font-weight: 600; white-space: nowrap;
  }}
  .pill.Very-High {{ background: var(--ca-red); color: var(--ca-red-on); }}
  .pill.High {{ background: var(--ca-red-light); color: var(--ca-red-light-on); }}
  .pill.Medium {{ background: var(--ca-green); color: var(--ca-green-on); }}
  .pill.Low {{ background: var(--ca-gray); color: var(--ca-gray-on); }}
  .pill.Not-Relevant {{ background: var(--ca-card-alt); color: var(--ca-text-muted); }}
  #grid {{ font-size: 13px; }}
  #grid .gridjs-container {{ background: transparent !important; }}
  #grid .gridjs-wrapper {{ background: var(--ca-card) !important; border-color: var(--ca-border) !important; }}
  #grid .gridjs-th {{ background: var(--ca-card-alt) !important; color: var(--ca-text) !important; border-color: var(--ca-border) !important; }}
  #grid .gridjs-td {{ background: var(--ca-card) !important; color: var(--ca-text) !important; border-color: var(--ca-border) !important; }}
  #grid .gridjs-tr:hover td {{ background: var(--ca-card-alt) !important; }}
  #grid .gridjs-footer {{ background: transparent !important; border-color: var(--ca-border) !important; }}
  #grid .gridjs-pagination {{ color: var(--ca-text-muted) !important; }}
  #grid .gridjs-pagination .gridjs-pages button {{ background: var(--ca-card) !important; color: var(--ca-text) !important; border-color: var(--ca-border) !important; }}
  #grid input.gridjs-input {{ background: var(--ca-card) !important; color: var(--ca-text) !important; border-color: var(--ca-border) !important; }}
  #grid input.gridjs-input:focus {{ border-color: var(--ca-green) !important; outline: none; }}
  a.src-link {{ color: var(--ca-green); text-decoration: none; font-size: 12px; font-weight: 600; }}
  a.src-link:hover {{ color: var(--ca-red); text-decoration: underline; }}
  .desc-cell {{ max-width: 420px; white-space: normal; line-height: 1.35; }}
  .trend-section {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 22px; }}
  .trend-card {{
    background: var(--ca-card); border: 1px solid var(--ca-border); border-radius: 10px;
    padding: 14px 16px;
  }}
  .trend-chart-card {{ flex: 2 1 380px; }}
  .trend-table-card {{ flex: 1 1 240px; }}
  .trend-title {{ font-size: 13px; font-weight: 600; color: var(--ca-text); margin: 0 0 10px; }}
  .trend-chart-wrap {{ position: relative; height: 200px; }}
  .trend-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  .trend-table th {{ text-align: left; color: var(--ca-text-muted); font-weight: 600; padding: 0 6px 6px 0; border-bottom: 1px solid var(--ca-border); }}
  .trend-table td {{ padding: 5px 6px 5px 0; border-bottom: 1px solid var(--ca-border); }}
  .trend-table td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .trend-table tr:last-child td {{ border-bottom: none; }}
  footer {{ margin-top: 18px; font-size: 11.5px; color: var(--ca-text-muted); }}
</style>
</head>
<body>
<div class="page">

<div class="brand-header"><span class="brand-mark">CaptiveAire</span><h1>&mdash; Tampa Bay Commercial Permit Leads</h1></div>
<div class="subtitle">Generated {generated_at} &nbsp;&middot;&nbsp; run date {run_date} &nbsp;&middot;&nbsp; {new_today} new today &nbsp;&middot;&nbsp; showing all {active_total} active leads from the last {active_window_days} days</div>

<div class="cards">
  <div class="card very-high"><div class="num-row"><span class="dot"></span><div class="num">{very_high}</div></div><div class="label">Very High priority</div></div>
  <div class="card high"><div class="num-row"><span class="dot"></span><div class="num">{high}</div></div><div class="label">High priority</div></div>
  <div class="card medium"><div class="num-row"><span class="dot"></span><div class="num">{medium}</div></div><div class="label">Medium priority</div></div>
  <div class="card low"><div class="num-row"><span class="dot"></span><div class="num">{low}</div></div><div class="label">Low priority</div></div>
  <div class="card total"><div class="num-row"><span class="dot"></span><div class="num">{new_today}</div></div><div class="label">New today</div></div>
</div>

<div class="trend-section">
  <div class="trend-card trend-chart-card">
    <div class="trend-title">Lead volume &amp; quality &mdash; last {trend_days} days</div>
    <div class="trend-chart-wrap"><canvas id="trendChart"></canvas></div>
  </div>
  <div class="trend-card trend-table-card">
    <div class="trend-title">All-time by source</div>
    <table class="trend-table">
      <tr><th>Jurisdiction</th><th style="text-align:right">Total</th><th style="text-align:right">V.High</th><th style="text-align:right">High</th></tr>
      {trend_jurisdiction_rows}
    </table>
  </div>
</div>

<div class="source-status">
  <div class="source-status-head"><strong>Source status this run</strong><span class="src-reset" id="srcReset">Show all sources &times;</span></div>
  <table id="srcTable">{source_rows}</table>
</div>

<div id="grid"></div>

<footer>
  CaptiveAire permit lead system &middot; 7 verified public sources (City of Tampa, Hillsborough County x2, City of Lakeland,
  Hernando County, Pinellas County DRS, Pasco County) &middot; scored via keyword + heuristic rules, no LLM &middot; full data also saved to
  CaptiveAire_Leads_Latest.csv in your connected folder.
</footer>

</div>

<script>
const LEADS = {leads_json};
const TREND_DAILY = {trend_daily_json};

function pillClass(cat) {{ return cat.replace(/\\s+/g, '-'); }}

new Chart(document.getElementById('trendChart'), {{
  type: 'bar',
  data: {{
    labels: TREND_DAILY.map(d => d.date.slice(5)),
    datasets: [
      {{ label: 'Very High', data: TREND_DAILY.map(d => d.very_high), backgroundColor: '#A8291E' }},
      {{ label: 'High', data: TREND_DAILY.map(d => d.high), backgroundColor: '#E08424' }},
      {{ label: 'Medium', data: TREND_DAILY.map(d => d.medium), backgroundColor: '#4CAF7D' }},
      {{ label: 'Low', data: TREND_DAILY.map(d => d.low), backgroundColor: '#78838A' }},
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      x: {{ stacked: true, ticks: {{ color: '#9AA4AA', font: {{ size: 11 }} }}, grid: {{ color: '#262d30' }} }},
      y: {{ stacked: true, beginAtZero: true, ticks: {{ color: '#9AA4AA', precision: 0 }}, grid: {{ color: '#262d30' }} }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#E8ECEE', font: {{ size: 11 }}, boxWidth: 12 }} }}
    }}
  }}
}});

const gridData = LEADS.map(r => [
  {{ cat: r.priority_category, score: r.score }},
  r.jurisdiction || '',
  r.permit_number || '',
  {{ issued: r.issue_date || '', applied: r.application_date || '' }},
  [r.address, r.city].filter(Boolean).join(', '),
  {{
    name: r.contact_name || '',
    title: r.contact_title || '',
    phone: r.contact_phone || '',
    email: r.contact_email || '',
    company: r.enriched_company_name || ''
  }},
  r.work_description || '',
  r.status || '',
  r.source_record_url || ''
]);

const grid = new gridjs.Grid({{
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
      name: 'Contact',
      formatter: (cell) => {{
        if (!cell.name && !cell.phone && !cell.email) return gridjs.html(`<span style="color:var(--ca-text-muted)">&mdash;</span>`);
        const lines = [];
        if (cell.name) lines.push(`<div>${{cell.name}}${{cell.title ? ` <span style="color:var(--ca-text-muted)">(${{cell.title}})</span>` : ''}}</div>`);
        if (cell.phone) lines.push(`<div><a class="src-link" href="tel:${{cell.phone.replace(/[^0-9+]/g,'')}}">${{cell.phone}}</a></div>`);
        if (cell.email) lines.push(`<div><a class="src-link" href="mailto:${{cell.email}}">${{cell.email}}</a></div>`);
        return gridjs.html(`<div style="font-size:12px; line-height:1.5;">${{lines.join('')}}</div>`);
      }}
    }},
    {{
      name: 'Description',
      formatter: (cell) => gridjs.html(`<div class="desc-cell">${{cell ? cell.replace(/</g,'&lt;') : ''}}</div>`)
    }},
    {{ name: 'Status' }},
    {{
      name: 'Source',
      formatter: (cell) => {{
        if (!cell) return '';
        const isGenericSearch = cell.includes('ims.lakelandgov.net') || cell.includes('CapHome.aspx');
        const label = isGenericSearch ? 'Search &rarr;' : 'Open &rarr;';
        const title = isGenericSearch ? 'Opens a general permit/project search tool — not a direct link to this record' : '';
        return gridjs.html(`<a class="src-link" href="${{cell}}" target="_blank" rel="noopener" title="${{title}}">${{label}}</a>`);
      }}
    }},
  ],
  data: gridData,
  sort: true,
  search: true,
  pagination: {{ limit: 20 }},
  className: {{ table: 'gridjs-table' }},
}});
grid.render(document.getElementById("grid"));

const srcTable = document.getElementById('srcTable');
const srcReset = document.getElementById('srcReset');

function applyJurisdictionFilter(jurisdiction) {{
  const filtered = jurisdiction ? gridData.filter(r => r[1] === jurisdiction) : gridData;
  grid.updateConfig({{ data: filtered }}).forceRender();
  srcTable.querySelectorAll('tr.src-row').forEach(tr => {{
    tr.classList.toggle('active', tr.dataset.jurisdiction === jurisdiction);
  }});
  srcReset.classList.toggle('active', !!jurisdiction);
}}

srcTable.addEventListener('click', (e) => {{
  const tr = e.target.closest('tr.src-row');
  if (!tr) return;
  const isActive = tr.classList.contains('active');
  applyJurisdictionFilter(isActive ? null : tr.dataset.jurisdiction);
}});

srcReset.addEventListener('click', () => applyJurisdictionFilter(null));
</script>

</body>
</html>
"""


def build(summary_path: Path, out_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    source_rows = "".join(
        f"<tr class='src-row' data-jurisdiction=\"{html.escape(info['jurisdiction'])}\">"
        f"<td>{html.escape(info['jurisdiction'])}</td>"
        f"<td class='n'>{info['fetched']} fetched</td>"
        f"<td class='n'>{info['new']} new</td></tr>"
        for info in summary["per_source_counts"].values()
    )

    trend = summary.get("trend", {"daily": [], "weekly": [], "by_jurisdiction": []})
    trend_jurisdiction_rows = "".join(
        f"<tr><td>{html.escape(row['jurisdiction'])}</td>"
        f"<td class='n'>{row['total']}</td>"
        f"<td class='n'>{row['very_high']}</td>"
        f"<td class='n'>{row['high']}</td></tr>"
        for row in trend.get("by_jurisdiction", [])
    ) or "<tr><td colspan='4' style='color:var(--ca-text-muted)'>No history yet</td></tr>"

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
        trend_days=len(trend.get("daily", [])),
        trend_jurisdiction_rows=trend_jurisdiction_rows,
        trend_daily_json=json.dumps(trend.get("daily", [])),
    )
    out_path.write_text(out_html, encoding="utf-8")
    print(f"Wrote {out_path} ({len(out_html):,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(Path(args.summary), Path(args.out))
