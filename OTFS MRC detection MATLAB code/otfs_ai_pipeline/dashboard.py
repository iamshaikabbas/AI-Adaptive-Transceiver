"""
dashboard.py
============
Phase-2 "Prediction Evaluation & Dashboard" module.

Reads AI_Results/predictions_vs_actual.csv + detector_recommendation_eval.csv
+ evaluation_summary.json (written by `predict.py`) and renders a single,
self-contained, INTERACTIVE HTML dashboard -- no static PNGs. Charts are
Chart.js, loaded from a CDN inside the HTML file; the file itself needs no
server, just open it in a browser.

Every panel is data-driven: the Python side inspects which columns/files are
actually present for this run and only emits the sections that apply, then
hands the browser a single JSON payload (`DASHBOARD_DATA`) built from that
data. The JS never hardcodes panel counts or metric names -- it just loops
over whatever sections/series show up in the payload. That means:
  - forward-mode runs (predict.py, no ground truth) get the decision panels
    (Environment mix, Detector mix, Quality mix, Confidence histogram)
  - validation-mode runs (predict.py --input <matlab_results.csv>) get those
    PLUS the accuracy panels (Predicted-vs-Actual scatter per metric,
    detector confusion matrix) because Actual_* columns / detector_eval.csv
    exist for that run
  - if a future run adds/removes a metric target in config.METRIC_TARGETS,
    or the confusion-matrix / quality files aren't produced, the dashboard
    silently adapts -- no code change needed here.

Called by MATLAB's Module 6 as:  python dashboard.py &   (non-blocking)
predict.py also calls `build_dashboard(df)` directly at the end of both its
forward and validation modes, passing the in-memory predictions frame so the
dashboard doesn't need a round-trip through disk.

Usage:
    python dashboard.py
"""

import json
import math
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from config import AI_RESULTS_DIR, METRIC_TARGETS, REPORTS_DIR
from communication_quality import classify_quality_frame, build_throughput_reference, QUALITY_ORDER

PRED_VS_ACTUAL = os.path.join(AI_RESULTS_DIR, "predictions_vs_actual.csv")
DET_EVAL = os.path.join(AI_RESULTS_DIR, "detector_recommendation_eval.csv")
SUMMARY = os.path.join(AI_RESULTS_DIR, "evaluation_summary.json")
DASHBOARD_SUMMARY_CSV = os.path.join(REPORTS_DIR, "dashboard_summary.csv")

LOG_TARGETS = {"BER", "SER", "PER"}
QUALITY_COLORS = {"Excellent": "#2ca02c", "Good": "#8fbc8f", "Moderate": "#e6b800", "Poor": "#d62728"}
PALETTE = ["#4C72B0", "#55A868", "#8172B2", "#C44E52", "#CCB974", "#64B5CD", "#DD8452", "#937860"]


def _ensure_quality(df: pd.DataFrame) -> pd.DataFrame:
    """predictions_vs_actual.csv may pre-date this column (older runs) --
    recompute it here if missing so the dashboard always has it."""
    if "Quality" in df.columns:
        return df
    if {"Predicted_BER", "Predicted_CQI", "Predicted_Throughput_bps"}.issubset(df.columns):
        ref = build_throughput_reference(df.rename(columns={"Predicted_Throughput_bps": "Throughput_bps"})) \
            if "Modulation" in df.columns else None
        df["Quality"] = classify_quality_frame(
            df, ber_col="Predicted_BER", cqi_col="Predicted_CQI",
            throughput_col="Predicted_Throughput_bps", throughput_ref=ref)
    return df


def build_summary_table(df: pd.DataFrame):
    """Writes the exact per-row view the spec's DASHBOARD section asks for:
    Environment, Predicted BER, Actual BER, Prediction Error, CQI, Detector,
    Confidence, Runtime, Throughput, Spectral Efficiency, Communication
    Quality -- one row per prediction. Any column not available in this run
    is simply omitted rather than crashing. Also feeds the HTML dashboard's
    searchable/sortable table panel."""
    wanted = {
        "Environment": "Environment",
        "Detector": "Detector",
        "BER": "Actual_BER",
        "Predicted_BER": "Predicted_BER",
        "CQI": "CQI",
        "Recommendation_Confidence": "Confidence",
        "Metric_Confidence": "Metric_Confidence",
        "Runtime_sec": "Runtime_sec",
        "Throughput_bps": "Throughput_bps",
        "SpectralEfficiency_bps_per_Hz": "SpectralEfficiency_bps_per_Hz",
        "Quality": "Communication_Quality",
    }
    available = {src: dst for src, dst in wanted.items() if src in df.columns}
    if not available:
        return None

    out = df[list(available.keys())].rename(columns=available)
    if "Actual_BER" in out.columns and "Predicted_BER" in out.columns:
        denom = np.maximum(np.abs(out["Actual_BER"]), 1e-9)
        out["Prediction_Error_pct"] = 100.0 * np.abs(out["Actual_BER"] - out["Predicted_BER"]) / denom

    out.to_csv(DASHBOARD_SUMMARY_CSV, index=False)
    print(f"Dashboard summary table saved -> {DASHBOARD_SUMMARY_CSV}")
    return out


# ---------------------------------------------------------------------------
# JSON-safety helpers -- NaN/Inf/pandas & numpy scalar types aren't valid
# JSON, so every value that flows into DASHBOARD_DATA goes through these.
# ---------------------------------------------------------------------------
def _clean_num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _clean_list(values):
    return [_clean_num(v) for v in values]


# ---------------------------------------------------------------------------
# Panel builders -- each returns a small dict (or None if the data needed
# for it isn't present) that becomes one entry in DASHBOARD_DATA["sections"].
# The HTML/JS side only knows how to render five generic panel "type"s
# (scatter / bar / hist / confusion / table); which of them show up, and
# with what data, is decided entirely here from what's actually in df.
# ---------------------------------------------------------------------------
def _scatter_panel(df, target):
    y_true = df[target].astype(float)
    y_pred = df[f"Predicted_{target}"].astype(float)
    log_scale = target in LOG_TARGETS
    if log_scale:
        y_true = y_true.clip(lower=1e-8)
        y_pred = y_pred.clip(lower=1e-8)
    points = [{"x": _clean_num(a), "y": _clean_num(b)} for a, b in zip(y_true, y_pred)]
    points = [p for p in points if p["x"] is not None and p["y"] is not None]
    lo = min(min(p["x"] for p in points), min(p["y"] for p in points))
    hi = max(max(p["x"] for p in points), max(p["y"] for p in points))
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    return {
        "type": "scatter", "title": f"{target}: Predicted vs Actual",
        "log_scale": log_scale, "x_label": "Actual (MATLAB ground truth)",
        "y_label": "Predicted (AI)", "points": points, "ref_line": {"lo": lo, "hi": hi},
    }


def _bar_panel(series, title, color_map=None, sort_by_quality=False):
    counts = series.value_counts()
    if sort_by_quality:
        order = [q for q in QUALITY_ORDER if q in counts.index]
        counts = counts.reindex(order)
    labels = [str(x) for x in counts.index]
    colors = [color_map.get(l, PALETTE[i % len(PALETTE)]) for i, l in enumerate(labels)] if color_map \
        else [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
    return {"type": "bar", "title": title, "labels": labels,
            "values": _clean_list(counts.values), "colors": colors}


def _hist_panel(values, title, bins=20, x_min=0.0, x_max=1.0):
    values = pd.Series(values).astype(float).dropna()
    counts, edges = np.histogram(values, bins=bins, range=(x_min, x_max))
    labels = [f"{edges[i]:.2f}-{edges[i + 1]:.2f}" for i in range(len(edges) - 1)]
    return {"type": "hist", "title": title, "labels": labels,
            "values": _clean_list(counts), "color": PALETTE[2]}


def _confusion_panel(det_df):
    labels = sorted(set(det_df["Detector"]) | set(det_df["Predicted_Best_Detector"]))
    cm = pd.crosstab(det_df["Detector"], det_df["Predicted_Best_Detector"],
                      rownames=["Actual"], colnames=["Recommended"])
    cm = cm.reindex(index=labels, columns=labels, fill_value=0)
    return {"type": "confusion", "title": "Detector Recommendation: Actual-best vs AI-recommended",
            "labels": labels, "matrix": [[int(v) for v in row] for row in cm.values]}


def _table_panel(summary_df, title="Per-Scenario Detail"):
    if summary_df is None or summary_df.empty:
        return None
    cols = list(summary_df.columns)
    rows = []
    for _, r in summary_df.iterrows():
        row = []
        for c in cols:
            v = r[c]
            if isinstance(v, (int, float, np.floating, np.integer)):
                row.append(_clean_num(v))
            else:
                row.append(str(v))
        rows.append(row)
    # Cap the browser payload -- the full data still lives in dashboard_summary.csv.
    truncated = len(rows) > 2000
    return {"type": "table", "title": title, "columns": cols, "rows": rows[:2000],
            "truncated": truncated, "total_rows": len(rows)}


# ---------------------------------------------------------------------------
def build_dashboard(df: pd.DataFrame = None):
    """Build the interactive HTML dashboard.

    df: optional in-memory predictions frame (forward or validation mode,
        passed straight from predict.py). If omitted, loads
        AI_Results/predictions_vs_actual.csv from disk (validation report
        use-case -- e.g. running `python dashboard.py` standalone after
        MATLAB's Module 6 has already called predict.py).
    """
    if df is None:
        if not os.path.exists(PRED_VS_ACTUAL):
            print(f"ERROR: {PRED_VS_ACTUAL} not found. Run "
                  f"'python predict.py --input <matlab_results.csv>' first.", file=sys.stderr)
            sys.exit(1)
        df = pd.read_csv(PRED_VS_ACTUAL)

    df = _ensure_quality(df.copy())
    present_targets = [t for t in METRIC_TARGETS if t in df.columns and f"Predicted_{t}" in df.columns]

    summary_table = build_summary_table(df)

    sections = []

    # Accuracy panels -- only meaningful in validation mode (Actual_* present)
    for target in present_targets:
        sections.append(_scatter_panel(df, target))

    if os.path.exists(DET_EVAL):
        det_df = pd.read_csv(DET_EVAL)
        if {"Detector", "Predicted_Best_Detector"}.issubset(det_df.columns):
            sections.append(_confusion_panel(det_df))

    # Decision panels -- available in both forward and validation mode
    if "Quality" in df.columns:
        sections.append(_bar_panel(df["Quality"], "Communication Quality Distribution",
                                    color_map=QUALITY_COLORS, sort_by_quality=True))

    if "Environment" in df.columns:
        sections.append(_bar_panel(df["Environment"], "Environment Mix"))

    det_col = "Detector" if "Detector" in df.columns else (
        "Recommended_Detector" if "Recommended_Detector" in df.columns else None)
    if det_col:
        sections.append(_bar_panel(df[det_col], "Recommended Detector"))

    if "Recommendation_Confidence" in df.columns:
        vals = df["Recommendation_Confidence"].astype(float)
        sections.append(_hist_panel(vals, "Detector Recommendation Confidence",
                                     x_min=0.0, x_max=1.0))

    table_section = _table_panel(summary_table)
    if table_section:
        sections.append(table_section)

    sections = [s for s in sections if s]

    accuracy_str = ""
    if os.path.exists(SUMMARY):
        with open(SUMMARY) as f:
            summary = json.load(f)
        acc = summary.get("detector_recommendation_accuracy")
        if acc is not None:
            accuracy_str = f"Detector recommendation accuracy: {acc * 100:.1f}%"

    payload = {
        "title": "OTFS AI Prediction Evaluation Dashboard",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accuracy_str": accuracy_str,
        "n_rows": int(len(df)),
        "sections": sections,
    }

    html = _render_html(payload)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(AI_RESULTS_DIR, f"AI_Dashboard_{ts}.html")
    latest_file = os.path.join(AI_RESULTS_DIR, "AI_Dashboard_latest.html")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard saved -> {out_file}")
    print(f"Dashboard saved -> {latest_file}")
    return latest_file


# ---------------------------------------------------------------------------
# HTML/JS template. Kept as one generic renderer -- it switches on
# section["type"] and never assumes how many panels of each type there are,
# so it stays correct as the payload's shape changes run to run.
# ---------------------------------------------------------------------------
def _render_html(payload: dict) -> str:
    data_json = json.dumps(payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{payload['title']}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1420; --panel: #171d2b; --border: #2a3244; --text: #e7ebf3;
    --muted: #94a3b8; --accent: #4C72B0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  header {{ margin-bottom: 20px; }}
  h1 {{ margin: 0 0 6px 0; font-size: 22px; }}
  .meta {{ color: var(--muted); font-size: 13px; }}
  .meta b {{ color: var(--text); }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 18px;
  }}
  .panel {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px; min-width: 0;
  }}
  .panel.wide {{ grid-column: 1 / -1; }}
  .panel h2 {{ margin: 0 0 12px 0; font-size: 14px; font-weight: 600; color: var(--text); }}
  canvas {{ max-height: 340px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }}
  th {{ position: sticky; top: 0; background: var(--panel); cursor: pointer; user-select: none; color: var(--muted); }}
  th:hover {{ color: var(--text); }}
  .table-wrap {{ max-height: 420px; overflow: auto; border: 1px solid var(--border); border-radius: 6px; }}
  input#search {{
    background: #0d1220; border: 1px solid var(--border); color: var(--text);
    padding: 7px 10px; border-radius: 6px; margin-bottom: 10px; width: 240px; font-size: 13px;
  }}
  .conf-table {{ border-collapse: collapse; }}
  .conf-table td, .conf-table th {{ text-align: center; padding: 10px; border: 1px solid var(--border); white-space: nowrap; }}
  .row-count {{ color: var(--muted); font-size: 12px; margin-left: 8px; }}
</style>
</head>
<body>
<header>
  <h1 id="dash-title"></h1>
  <div class="meta">Generated <b id="dash-generated"></b> &middot; <span id="dash-accuracy"></span>
    &middot; <b id="dash-rows"></b> rows</div>
</header>
<div class="grid" id="grid"></div>

<script>
const DASHBOARD_DATA = {data_json};

document.getElementById('dash-title').textContent = DASHBOARD_DATA.title;
document.getElementById('dash-generated').textContent = DASHBOARD_DATA.generated;
document.getElementById('dash-accuracy').textContent = DASHBOARD_DATA.accuracy_str || '';
document.getElementById('dash-rows').textContent = DASHBOARD_DATA.n_rows;

const grid = document.getElementById('grid');

const CHART_DEFAULTS = {{
  color: '#e7ebf3',
  scales_grid: 'rgba(255,255,255,0.08)',
}};

function makePanel(wide) {{
  const div = document.createElement('div');
  div.className = 'panel' + (wide ? ' wide' : '');
  grid.appendChild(div);
  return div;
}}

function renderScatter(section) {{
  const panel = makePanel(false);
  panel.innerHTML = `<h2>${{section.title}}</h2><canvas></canvas>`;
  const ctx = panel.querySelector('canvas').getContext('2d');
  const ref = section.ref_line;
  new Chart(ctx, {{
    type: 'scatter',
    data: {{
      datasets: [
        {{ label: 'Predictions', data: section.points, backgroundColor: 'rgba(76,114,176,0.55)',
           pointRadius: 3 }},
        {{ label: 'y = x', data: [{{x: ref.lo, y: ref.lo}}, {{x: ref.hi, y: ref.hi}}],
           type: 'line', borderColor: '#d62728', borderWidth: 1.5, pointRadius: 0, borderDash: [6,4] }}
      ]
    }},
    options: {{
      responsive: true,
      scales: {{
        x: {{ type: section.log_scale ? 'logarithmic' : 'linear', title: {{ display: true, text: section.x_label, color: CHART_DEFAULTS.color }},
              ticks: {{ color: CHART_DEFAULTS.color }}, grid: {{ color: CHART_DEFAULTS.scales_grid }} }},
        y: {{ type: section.log_scale ? 'logarithmic' : 'linear', title: {{ display: true, text: section.y_label, color: CHART_DEFAULTS.color }},
              ticks: {{ color: CHART_DEFAULTS.color }}, grid: {{ color: CHART_DEFAULTS.scales_grid }} }},
      }},
      plugins: {{ legend: {{ labels: {{ color: CHART_DEFAULTS.color }} }} }}
    }}
  }});
}}

function renderBar(section) {{
  const panel = makePanel(false);
  panel.innerHTML = `<h2>${{section.title}}</h2><canvas></canvas>`;
  const ctx = panel.querySelector('canvas').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{ labels: section.labels, datasets: [{{ data: section.values, backgroundColor: section.colors,
             borderColor: 'rgba(0,0,0,0.4)', borderWidth: 1 }}] }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: CHART_DEFAULTS.color }}, grid: {{ display: false }} }},
        y: {{ beginAtZero: true, ticks: {{ color: CHART_DEFAULTS.color }}, grid: {{ color: CHART_DEFAULTS.scales_grid }} }},
      }}
    }}
  }});
}}

function renderHist(section) {{
  const panel = makePanel(false);
  panel.innerHTML = `<h2>${{section.title}}</h2><canvas></canvas>`;
  const ctx = panel.querySelector('canvas').getContext('2d');
  new Chart(ctx, {{
    type: 'bar',
    data: {{ labels: section.labels, datasets: [{{ data: section.values, backgroundColor: section.color }}] }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: CHART_DEFAULTS.color, maxRotation: 90, minRotation: 45, autoSkip: true }}, grid: {{ display: false }} }},
        y: {{ beginAtZero: true, ticks: {{ color: CHART_DEFAULTS.color }}, grid: {{ color: CHART_DEFAULTS.scales_grid }} }},
      }}
    }}
  }});
}}

function renderConfusion(section) {{
  const panel = makePanel(false);
  const max = Math.max(1, ...section.matrix.flat());
  let html = `<h2>${{section.title}}</h2><div style="overflow:auto"><table class="conf-table"><tr><th></th>`;
  section.labels.forEach(l => html += `<th>${{l}}</th>`);
  html += `</tr>`;
  section.matrix.forEach((row, i) => {{
    html += `<tr><th>${{section.labels[i]}}</th>`;
    row.forEach(v => {{
      const alpha = 0.15 + 0.75 * (v / max);
      const textColor = alpha > 0.55 ? '#0f1420' : '#e7ebf3';
      html += `<td style="background:rgba(76,114,176,${{alpha}});color:${{textColor}};font-weight:600">${{v}}</td>`;
    }});
    html += `</tr>`;
  }});
  html += `</table></div><div class="row-count">rows = actual best detector, columns = AI-recommended</div>`;
  panel.innerHTML = html;
}}

function renderTable(section) {{
  const panel = makePanel(true);
  const rowNote = section.truncated
    ? `<span class="row-count">showing first ${{section.rows.length}} of ${{section.total_rows}} rows -- full data in Reports/dashboard_summary.csv</span>`
    : `<span class="row-count">${{section.rows.length}} rows</span>`;
  panel.innerHTML = `<h2>${{section.title}}</h2>
    <input id="search" placeholder="Filter rows...">${{rowNote}}
    <div class="table-wrap"><table id="data-table"><thead><tr>
      ${{section.columns.map((c,i) => `<th data-col="${{i}}">${{c}}</th>`).join('')}}
    </tr></thead><tbody></tbody></table></div>`;

  let rows = section.rows;
  const tbody = panel.querySelector('tbody');

  function draw(rowsToShow) {{
    tbody.innerHTML = rowsToShow.map(r =>
      `<tr>${{r.map(v => `<td>${{v === null ? '' : (typeof v === 'number' ? Number(v.toPrecision(5)) : v)}}</td>`).join('')}}</tr>`
    ).join('');
  }}
  draw(rows);

  panel.querySelector('#search').addEventListener('input', (e) => {{
    const q = e.target.value.toLowerCase();
    draw(rows.filter(r => r.some(v => String(v).toLowerCase().includes(q))));
  }});

  let sortDir = {{}};
  panel.querySelectorAll('th[data-col]').forEach(th => {{
    th.addEventListener('click', () => {{
      const col = parseInt(th.dataset.col, 10);
      sortDir[col] = !sortDir[col];
      const sorted = [...rows].sort((a, b) => {{
        const av = a[col], bv = b[col];
        const cmp = (typeof av === 'number' && typeof bv === 'number') ? av - bv
          : String(av).localeCompare(String(bv));
        return sortDir[col] ? cmp : -cmp;
      }});
      rows = sorted;
      draw(rows);
    }});
  }});
}}

const RENDERERS = {{ scatter: renderScatter, bar: renderBar, hist: renderHist,
                      confusion: renderConfusion, table: renderTable }};

DASHBOARD_DATA.sections.forEach(section => {{
  const fn = RENDERERS[section.type];
  if (fn) fn(section);
}});

if (DASHBOARD_DATA.sections.length === 0) {{
  grid.innerHTML = '<div class="panel wide">No data available to build a dashboard from.</div>';
}}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build_dashboard()
