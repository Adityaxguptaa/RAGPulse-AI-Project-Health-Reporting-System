"""HTML-based slide renderer for in-app PPTX preview.

Each slide is returned as a self-contained HTML string styled to look like a
presentation slide. Streamlit displays them via st.components.v1.html().
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.models import Project

_RAG_HEX = {"Green": "#2ecc71", "Amber": "#f39c12", "Red": "#e74c3c", "Unknown": "#95a5a6"}
_RAG_BG  = {"Green": "#d5f5e3", "Amber": "#fef9e7", "Red": "#fdedec",  "Unknown": "#f2f3f4"}

_SLIDE_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; }
  body { background: #1a1a2e; display: flex; justify-content: center; align-items: center;
         min-height: 100vh; padding: 4px; }
  .slide { width: 960px; height: 540px; position: relative; overflow: hidden; border-radius: 6px;
           box-shadow: 0 8px 32px rgba(0,0,0,.5); }
  .header-bar { position: absolute; top: 0; left: 0; right: 0; padding: 12px 24px;
                display: flex; align-items: center; z-index: 10; }
  .header-bar h2 { font-size: 20px; font-weight: 700; }
  .footer-bar { position: absolute; bottom: 0; left: 0; right: 0; padding: 8px 20px;
                font-size: 10px; display: flex; justify-content: space-between;
                align-items: center; }
  .content { position: absolute; top: 52px; bottom: 36px; left: 0; right: 0; padding: 12px 20px;
             overflow: hidden; }
  .rag-badge { display: inline-block; padding: 4px 16px; border-radius: 20px;
               font-weight: 700; font-size: 13px; color: #fff; }
  .kpi-grid { display: flex; gap: 10px; margin-bottom: 10px; }
  .kpi-box { flex: 1; border-radius: 8px; padding: 10px 8px; text-align: center; }
  .kpi-val { font-size: 22px; font-weight: 700; }
  .kpi-lbl { font-size: 10px; opacity: .85; margin-top: 2px; }
  .score-row { display: flex; align-items: center; margin-bottom: 5px; }
  .score-lbl { width: 160px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
  .score-bar-wrap { flex: 1; height: 14px; background: #ddd; border-radius: 7px; overflow: hidden; }
  .score-bar-fill { height: 100%; border-radius: 7px; display: flex; align-items: center;
                    padding-left: 6px; font-size: 10px; color: #fff; font-weight: 600; }
  .score-wt { width: 40px; text-align: right; font-size: 10px; color: #666; }
  .score-rat { width: 220px; font-size: 9px; color: #555; padding-left: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 10px; }
  th { padding: 5px 8px; text-align: left; }
  td { padding: 4px 8px; border-bottom: 1px solid rgba(0,0,0,.06); }
  tr:nth-child(even) td { background: rgba(0,0,0,.03); }
  .bullet { margin-bottom: 5px; padding-left: 12px; position: relative; font-size: 11px;
            line-height: 1.4; }
  .bullet::before { content: "•"; position: absolute; left: 0; }
  .summary-box { background: #eaf4fb; border-left: 4px solid #3498db; padding: 10px 14px;
                 border-radius: 0 8px 8px 0; font-size: 11px; line-height: 1.5; margin-bottom: 8px; }
  .two-col { display: flex; gap: 14px; }
  .col { flex: 1; }
  .section-title { font-size: 12px; font-weight: 700; margin-bottom: 5px; }
  .risk-row { display: flex; align-items: flex-start; margin-bottom: 4px;
              padding: 4px 8px; border-radius: 4px; font-size: 10px; }
  .risk-bar { width: 4px; height: 100%; border-radius: 2px; margin-right: 8px;
              flex-shrink: 0; align-self: stretch; min-height: 14px; }
  .rec-row { padding: 5px 10px; border-radius: 4px; font-size: 10px; margin-bottom: 4px;
             border-left: 3px solid #3498db; background: #eaf4fb; }
  .proj-tag { font-size: 9px; font-weight: 700; color: #3498db; }
"""

def _html_wrap(slide_html: str, bg: str = "#2c3e50") -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>{_SLIDE_CSS}</style>
</head>
<body style="background:{bg};">
{slide_html}
</body></html>"""


def _rag_badge(status: str) -> str:
    color = _RAG_HEX.get(status, "#95a5a6")
    return f'<span class="rag-badge" style="background:{color}">{status}</span>'


# ── Portfolio slides ───────────────────────────────────────────────────────────

def _portfolio_slide_title(summary: dict[str, Any]) -> str:
    rpt_date = summary.get("report_date", date.today().isoformat())
    total    = summary.get("total_projects", 0)
    html = f"""
<div class="slide" style="background:linear-gradient(135deg,#2c3e50 0%,#1a252f 100%)">
  <div style="position:absolute;left:0;right:0;top:42%;height:6px;background:#3498db"></div>
  <div style="position:absolute;left:0;right:0;bottom:0;height:55px;background:#3498db"></div>
  <div style="position:absolute;top:25%;left:0;right:0;text-align:center;padding:0 80px">
    <div style="font-size:13px;color:#aaa;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px">Monthly Portfolio Report</div>
    <div style="font-size:36px;font-weight:800;color:#fff;line-height:1.2">AI Project Health<br>Portfolio Overview</div>
    <div style="margin-top:18px;font-size:14px;color:#bdc3c7">{total} Project{'s' if total!=1 else ''} Analysed</div>
  </div>
  <div style="position:absolute;bottom:12px;left:0;right:0;text-align:center;color:#fff;font-size:11px">
    Report Date: {rpt_date} &nbsp;|&nbsp; AI Project Health Reporting System &nbsp;|&nbsp; Confidential
  </div>
</div>"""
    return _html_wrap(html)


def _portfolio_slide_overview(summary: dict[str, Any]) -> str:
    dist   = summary.get("rag_distribution", {})
    total  = summary.get("total_projects", 0)
    avg    = summary.get("avg_composite_score", "N/A")
    signal = summary.get("health_signal", "")
    sig_color = "#e74c3c" if "high risk" in signal.lower() else ("#f39c12" if "pressure" in signal.lower() else "#2ecc71")
    max_count = max(dist.get("Green",0), dist.get("Amber",0), dist.get("Red",0), 1)

    bars_html = ""
    for rag, color in [("Green","#2ecc71"),("Amber","#f39c12"),("Red","#e74c3c")]:
        count = dist.get(rag, 0)
        pct   = count / max_count * 100
        bars_html += f"""<div style="text-align:center;flex:1">
          <div style="height:100px;background:#eee;border-radius:6px;display:flex;align-items:flex-end;overflow:hidden;margin:0 10px">
            <div style="width:100%;height:{pct}%;background:{color};border-radius:6px 6px 0 0;
                 display:flex;align-items:flex-start;justify-content:center;padding-top:4px;
                 color:#fff;font-weight:700;font-size:18px">{count}</div>
          </div>
          <div style="margin-top:5px;font-size:12px;font-weight:600;color:#333">{rag}</div>
        </div>"""

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#2c3e50;color:#fff">
    <h2>📊 Portfolio Overview</h2>
  </div>
  <div class="content">
    <div class="kpi-grid">
      <div class="kpi-box" style="background:#2c3e50;color:#fff">
        <div class="kpi-val">{total}</div><div class="kpi-lbl">Total Projects</div>
      </div>
      <div class="kpi-box" style="background:#2ecc71;color:#fff">
        <div class="kpi-val">{dist.get('Green',0)}</div><div class="kpi-lbl">🟢 Green</div>
      </div>
      <div class="kpi-box" style="background:#f39c12;color:#fff">
        <div class="kpi-val">{dist.get('Amber',0)}</div><div class="kpi-lbl">🟡 Amber</div>
      </div>
      <div class="kpi-box" style="background:#e74c3c;color:#fff">
        <div class="kpi-val">{dist.get('Red',0)}</div><div class="kpi-lbl">🔴 Red</div>
      </div>
      <div class="kpi-box" style="background:#3498db;color:#fff">
        <div class="kpi-val">{avg}</div><div class="kpi-lbl">Avg Score</div>
      </div>
    </div>
    <div style="background:{sig_color};color:#fff;padding:7px 14px;border-radius:6px;
         font-size:12px;font-weight:700;margin-bottom:10px">Portfolio Signal: {signal}</div>
    <div style="display:flex;height:130px;align-items:flex-end;justify-content:center;gap:0">
      {bars_html}
    </div>
  </div>
  <div class="footer-bar" style="background:#2c3e50;color:#aaa">
    <span>Portfolio Health Summary</span><span>Slide 2 of 7</span>
  </div>
</div>"""
    return _html_wrap(html)


def _portfolio_slide_scorecard(projects: list[Project]) -> str:
    rows_html = ""
    for p in projects[:8]:
        rag   = p.rag_status or "Unknown"
        color = _RAG_HEX.get(rag, "#95a5a6")
        score = p.metrics.get("composite_score","N/A")
        comp  = p.metrics.get("completion_percent","N/A")
        delay = p.metrics.get("delayed_tasks",0)
        risks = p.metrics.get("open_risks",0)
        rows_html += f"""<tr>
          <td style="font-weight:600">{p.name[:30]}</td>
          <td><span class="rag-badge" style="background:{color};padding:2px 10px;font-size:10px">{rag}</span></td>
          <td style="text-align:center">{score}</td>
          <td style="text-align:center">{comp}%</td>
          <td style="text-align:center">{delay}</td>
          <td style="text-align:center">{risks}</td>
          <td style="font-size:9px">{(p.executive_summary or '')[:55]}</td>
        </tr>"""

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#2c3e50;color:#fff"><h2>🏗️ Project Health Scorecard</h2></div>
  <div class="content">
    <table>
      <thead style="background:#2c3e50;color:#fff">
        <tr><th>Project</th><th>RAG</th><th>Score</th><th>Completion</th><th>Delayed</th><th>Risks</th><th>Summary</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div class="footer-bar" style="background:#2c3e50;color:#aaa">
    <span>Project Health Scorecard</span><span>Slide 3 of 7</span>
  </div>
</div>"""
    return _html_wrap(html)


def _portfolio_slide_risks(projects: list[Project]) -> str:
    risks_html = ""
    count = 0
    for p in projects:
        for r in (p.identified_risks or [])[:2]:
            if r and count < 10:
                rag   = p.rag_status or "Unknown"
                color = _RAG_HEX.get(rag, "#95a5a6")
                bg    = _RAG_BG.get(rag, "#f2f3f4")
                risks_html += f"""<div class="risk-row" style="background:{bg}">
                  <div class="risk-bar" style="background:{color}"></div>
                  <div><span style="font-size:9px;font-weight:700;color:{color}">[{p.name[:18]}]</span>
                  &nbsp;{r[:100]}</div></div>"""
                count += 1
    if not risks_html:
        risks_html = "<div style='color:#666;font-size:12px;margin-top:20px'>No significant risks identified.</div>"

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#c0392b;color:#fff"><h2>🚨 Key Risks &amp; Issues</h2></div>
  <div class="content">{risks_html}</div>
  <div class="footer-bar" style="background:#c0392b;color:#fff">
    <span>Risk Summary</span><span>Slide 4 of 7</span>
  </div>
</div>"""
    return _html_wrap(html)


def _portfolio_slide_recommendations(projects: list[Project]) -> str:
    recs_html = ""
    count = 0
    for p in projects:
        for rec in (p.recommendations or [])[:2]:
            if rec and count < 10:
                recs_html += f"""<div class="rec-row">
                  <div class="proj-tag">[{p.name[:20]}]</div>
                  <div>{rec[:110]}</div></div>"""
                count += 1
    if not recs_html:
        recs_html = "<div style='color:#666;font-size:12px;margin-top:20px'>Enable Gemini AI to generate recommendations.</div>"

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#3498db;color:#fff"><h2>✅ Recommendations &amp; Next Steps</h2></div>
  <div class="content">{recs_html}</div>
  <div class="footer-bar" style="background:#3498db;color:#fff">
    <span>Recommendations</span><span>Slide 5 of 7</span>
  </div>
</div>"""
    return _html_wrap(html)


def _portfolio_slide_methodology() -> str:
    dims = [
        ("Schedule Performance", "25%", "Variance to baseline, delayed task ratio"),
        ("Milestone Completion", "20%", "Overdue milestones vs total milestones"),
        ("Task Completion",      "20%", "Completed tasks as % of total"),
        ("Risk Exposure",        "15%", "Open risks weighted by severity"),
        ("Critical Path",        "10%", "Critical tasks that are delayed"),
        ("Data Quality",         "10%", "Completeness of plan data"),
    ]
    rows_html = "".join(
        f"<tr><td style='font-weight:600'>{d[0]}</td><td style='text-align:center'>{d[1]}</td><td>{d[2]}</td></tr>"
        for d in dims)
    thresh_html = "".join(
        f'<div style="flex:1;background:{c};color:#fff;padding:8px;border-radius:6px;text-align:center;font-size:11px;font-weight:700">{l}<br><span style="font-weight:400;font-size:9px">{t}</span></div>'
        for l, c, t in [("🟢 GREEN","#2ecc71","Score ≥ 0.70"),("🟡 AMBER","#f39c12","0.40 – 0.69"),("🔴 RED","#e74c3c","Score < 0.40")]
    )
    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#2c3e50;color:#fff"><h2>📘 RAG Scoring Methodology</h2></div>
  <div class="content">
    <table>
      <thead style="background:#3498db;color:#fff">
        <tr><th>Dimension</th><th>Weight</th><th>Scoring Criteria</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div style="display:flex;gap:8px;margin-top:12px">{thresh_html}</div>
  </div>
  <div class="footer-bar" style="background:#2c3e50;color:#aaa">
    <span>Methodology</span><span>Slide 6 of 7</span>
  </div>
</div>"""
    return _html_wrap(html)


def _portfolio_slide_closing(summary: dict[str, Any], projects: list[Project]) -> str:
    signal   = summary.get("health_signal", "")
    sig_color = "#e74c3c" if "high risk" in signal.lower() else ("#f39c12" if "pressure" in signal.lower() else "#2ecc71")
    projs_html = ""
    for p in projects[:5]:
        rag   = p.rag_status or "Unknown"
        sym   = {"Green":"🟢","Amber":"🟡","Red":"🔴"}.get(rag,"⚪")
        projs_html += f"""<div style="margin-bottom:5px;padding:5px 10px;background:rgba(255,255,255,.07);
            border-radius:5px;font-size:11px;color:#ecf0f1">
          <b>{sym} {p.name}:</b> {(p.executive_summary or 'No summary.')[:120]}
        </div>"""
    html = f"""
<div class="slide" style="background:linear-gradient(135deg,#2c3e50 0%,#1a252f 100%)">
  <div class="header-bar" style="background:rgba(255,255,255,.08);color:#fff;border-bottom:2px solid #3498db">
    <h2>Executive Summary &amp; Closing</h2>
  </div>
  <div class="content">
    <div style="background:{sig_color};color:#fff;padding:7px 14px;border-radius:6px;
         font-size:12px;font-weight:700;margin-bottom:10px">{signal}</div>
    {projs_html}
  </div>
  <div style="position:absolute;bottom:0;left:0;right:0;padding:8px 20px;
       background:#3498db;color:#fff;font-size:10px;text-align:center">
    AI Project Health Reporting System  •  Powered by Gemini AI  •  Confidential
  </div>
</div>"""
    return _html_wrap(html)


def render_portfolio_slides(
    projects: list[Project],
    portfolio_summary: dict[str, Any],
) -> list[str]:
    """Return 7 slide HTML strings for the portfolio presentation."""
    return [
        _portfolio_slide_title(portfolio_summary),
        _portfolio_slide_overview(portfolio_summary),
        _portfolio_slide_scorecard(projects),
        _portfolio_slide_risks(projects),
        _portfolio_slide_recommendations(projects),
        _portfolio_slide_methodology(),
        _portfolio_slide_closing(portfolio_summary, projects),
    ]


# ── Per-project slides ────────────────────────────────────────────────────────

def _proj_slide_title(project: Project) -> str:
    rag   = project.rag_status or "Unknown"
    color = _RAG_HEX.get(rag, "#95a5a6")
    rpt_date = date.today().isoformat()
    score = project.metrics.get("composite_score","N/A")
    html = f"""
<div class="slide" style="background:linear-gradient(135deg,#2c3e50 0%,#1a252f 100%)">
  <div style="position:absolute;top:35%;left:0;right:0;text-align:center;padding:0 60px">
    <div style="font-size:11px;color:#aaa;text-transform:uppercase;letter-spacing:2px;margin-bottom:10px">Monthly Health Report</div>
    <div style="font-size:32px;font-weight:800;color:#fff;line-height:1.2">{project.name}</div>
    <div style="margin-top:16px">
      <span class="rag-badge" style="background:{color};font-size:14px;padding:6px 20px">{rag}</span>
      <span style="margin-left:14px;color:#bdc3c7;font-size:13px">Score: <b style="color:#fff">{score}</b></span>
    </div>
    <div style="margin-top:10px;color:#95a5a6;font-size:11px">PM: {project.pm or 'N/A'} &nbsp;|&nbsp; {rpt_date}</div>
  </div>
  <div style="position:absolute;bottom:0;left:0;right:0;height:5px;background:{color}"></div>
  <div style="position:absolute;bottom:5px;left:0;right:0;padding:8px;text-align:center;color:#666;font-size:9px">
    AI Project Health Reporting System — Monthly Report
  </div>
</div>"""
    return _html_wrap(html)


def _proj_slide_dashboard(project: Project) -> str:
    rag   = project.rag_status or "Unknown"
    color = _RAG_HEX.get(rag, "#95a5a6")
    m     = project.metrics
    conf  = f"{project.rag_confidence*100:.0f}%" if project.rag_confidence is not None else "N/A"

    kpis = [
        ("Completion",  f"{m.get('completion_percent','N/A')}%", "#3498db"),
        ("Tasks Done",  f"{m.get('completed_tasks',0)}/{m.get('total_tasks',0)}", "#2ecc71"),
        ("Delayed",     str(m.get("delayed_tasks",0)),  "#e74c3c"),
        ("Overdue MS",  str(m.get("overdue_milestones",0)), "#f39c12"),
        ("Open Risks",  str(m.get("open_risks",0)),     "#9b59b6"),
        ("Confidence",  conf,                           "#1abc9c"),
    ]
    kpi_html = "".join(
        f'<div class="kpi-box" style="background:{c};color:#fff"><div class="kpi-val">{v}</div><div class="kpi-lbl">{l}</div></div>'
        for l, v, c in kpis)

    summary = project.executive_summary or "Run analysis with Gemini enabled for AI summary."

    # Dimension bars
    dims_html = ""
    for dim_name, data in list(m.get("dimensions",{}).items())[:6]:
        score  = float(data.get("score", 0))
        pct    = int(score * 100)
        d_color = "#2ecc71" if score >= 0.7 else ("#f39c12" if score >= 0.4 else "#e74c3c")
        rat    = (data.get("rationale","") or "")[:45]
        wt     = m.get("weights",{}).get(dim_name, 0)
        dims_html += f"""<div class="score-row">
          <div class="score-lbl">{dim_name.replace('_',' ').title()}</div>
          <div class="score-bar-wrap"><div class="score-bar-fill" style="width:{pct}%;background:{d_color}">{score:.2f}</div></div>
          <div class="score-wt">{wt:.0%}</div>
          <div class="score-rat">{rat}</div>
        </div>"""

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:{color};color:#fff">
    <h2>📈 Health Dashboard — {project.name[:35]}</h2>
    <span style="margin-left:auto;font-size:12px">RAG: <b>{rag}</b></span>
  </div>
  <div class="content">
    <div class="kpi-grid">{kpi_html}</div>
    <div class="summary-box">{summary[:200]}</div>
    <div style="font-size:11px;font-weight:700;color:#2c3e50;margin-bottom:4px">Dimension Scores</div>
    {dims_html}
  </div>
  <div class="footer-bar" style="background:{color};color:#fff">
    <span>Health Dashboard</span><span>Slide 2 of 5</span>
  </div>
</div>"""
    return _html_wrap(html)


def _proj_slide_progress(project: Project) -> str:
    m = project.metrics
    all_tasks = project.tasks + project.milestones
    rows_html = ""
    for t in all_tasks[:12]:
        ms_icon = "⭐" if t.is_milestone else ""
        crit    = "⚠️" if t.is_critical else ""
        delay   = f'<span style="color:#e74c3c">🔴</span>' if t.is_delayed else '<span style="color:#2ecc71">🟢</span>'
        var     = f"{t.variance_days:+.0f}d" if t.variance_days else ""
        pct     = f"{t.percent_complete:.0f}%" if t.percent_complete is not None else ""
        rows_html += f"<tr><td>{ms_icon}{crit}{(t.name or '')[:38]}</td><td style='text-align:center'>{t.status or ''}</td><td style='text-align:center'>{pct}</td><td style='text-align:center'>{delay}</td><td style='text-align:center'>{var}</td></tr>"

    overdue_html = ""
    for ms in project.overdue_milestones[:4]:
        overdue_html += f"<div style='padding:3px 8px;background:#fdedec;border-left:3px solid #e74c3c;border-radius:3px;font-size:10px;margin-bottom:3px'><b>{ms.name[:40]}</b> — Due: {ms.planned_finish.isoformat() if ms.planned_finish else 'N/A'} (+{ms.variance_days:.0f}d)</div>"

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#2c3e50;color:#fff"><h2>📋 Progress &amp; Milestones</h2></div>
  <div class="content">
    {'<div style="font-size:11px;font-weight:700;color:#e74c3c;margin-bottom:4px">⚠️ Overdue Milestones</div>' + overdue_html if project.overdue_milestones else ''}
    <div style="font-size:11px;font-weight:700;color:#2c3e50;margin:5px 0 3px">Tasks (top {min(12,len(all_tasks))} of {len(all_tasks)})</div>
    <table>
      <thead style="background:#2c3e50;color:#fff">
        <tr><th>Task / Milestone</th><th>Status</th><th>% Done</th><th>Delayed</th><th>Variance</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div class="footer-bar" style="background:#2c3e50;color:#aaa">
    <span>Progress Tracker</span><span>Slide 3 of 5</span>
  </div>
</div>"""
    return _html_wrap(html)


def _proj_slide_risks_recs(project: Project) -> str:
    risks_html = ""
    for r in (project.identified_risks or [])[:6]:
        risks_html += f'<div class="bullet">{r[:95]}</div>'
    if project.risks:
        for r in project.risks[:4]:
            sev   = (r.severity or "").lower()
            bg    = "#fdedec" if sev in {"high","critical"} else ("#fef9e7" if sev=="medium" else "#d5f5e3")
            risks_html += f'<div style="padding:3px 8px;background:{bg};border-radius:3px;font-size:10px;margin-bottom:3px"><b>[{r.severity or "?"}]</b> {(r.description or "")[:80]}</div>'
    if not risks_html:
        risks_html = "<div style='color:#666;font-size:11px'>No risks identified.</div>"

    recs_html = ""
    for i, rec in enumerate((project.recommendations or [])[:5], 1):
        recs_html += f'<div style="padding:4px 10px;background:#eaf4fb;border-left:3px solid #3498db;border-radius:3px;font-size:10px;margin-bottom:4px"><b>{i}.</b> {rec[:100]}</div>'
    for p in (project.next_week_priorities or [])[:3]:
        recs_html += f'<div style="padding:4px 10px;background:#fef9e7;border-left:3px solid #f39c12;border-radius:3px;font-size:10px;margin-bottom:4px">📅 {p[:100]}</div>'
    if not recs_html:
        recs_html = "<div style='color:#666;font-size:11px'>No recommendations generated.</div>"

    html = f"""
<div class="slide" style="background:#f8f9fa">
  <div class="header-bar" style="background:#2c3e50;color:#fff"><h2>🚨 Risks &amp; Recommendations</h2></div>
  <div class="content">
    <div class="two-col">
      <div class="col">
        <div class="section-title" style="color:#e74c3c">🚨 Risks &amp; Issues</div>
        {risks_html}
      </div>
      <div class="col">
        <div class="section-title" style="color:#3498db">✅ Recommendations &amp; Priorities</div>
        {recs_html}
      </div>
    </div>
  </div>
  <div class="footer-bar" style="background:#2c3e50;color:#aaa">
    <span>Risks &amp; Recommendations</span><span>Slide 4 of 5</span>
  </div>
</div>"""
    return _html_wrap(html)


def _proj_slide_closing(project: Project) -> str:
    rag    = project.rag_status or "Unknown"
    color  = _RAG_HEX.get(rag, "#95a5a6")
    m      = project.metrics
    missing_html = "".join(
        f'<div style="font-size:10px;color:#e74c3c;margin-bottom:3px">⚠️ {d[:100]}</div>'
        for d in (project.missing_data or [])[:3]
    ) or "<div style='font-size:10px;color:#2ecc71'>No data quality issues found.</div>"

    action_html = "".join(
        f'<div style="padding:4px 10px;background:#eaf4fb;border-left:3px solid #3498db;border-radius:3px;font-size:11px;margin-bottom:5px;font-weight:600">→ {p[:110]}</div>'
        for p in (project.next_week_priorities or [])[:4]
    ) or "<div style='color:#666;font-size:11px'>No priorities set.</div>"

    html = f"""
<div class="slide" style="background:linear-gradient(135deg,#2c3e50 0%,#1a252f 100%)">
  <div class="header-bar" style="background:rgba(255,255,255,.08);color:#fff;border-bottom:2px solid {color}">
    <h2>Monthly Summary — {project.name[:40]}</h2>
    <span class="rag-badge" style="background:{color};margin-left:auto">{rag}</span>
  </div>
  <div class="content">
    <div class="two-col">
      <div class="col">
        <div style="color:#ecf0f1;font-size:12px;font-weight:700;margin-bottom:8px">📅 Next Week Actions</div>
        {action_html}
        <div style="color:#ecf0f1;font-size:12px;font-weight:700;margin-top:10px;margin-bottom:5px">⚠️ Data Quality Notes</div>
        {missing_html}
      </div>
      <div class="col">
        <div style="background:rgba(255,255,255,.07);border-radius:8px;padding:12px">
          <div style="color:#aaa;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Health Snapshot</div>
          {''.join(f'<div style="display:flex;justify-content:space-between;color:#ecf0f1;font-size:11px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.08)"><span>{label}</span><b>{val}</b></div>' for label,val in [("Composite Score",m.get("composite_score","N/A")),("Completion",f"{m.get('completion_percent','N/A')}%"),("Delayed Tasks",m.get("delayed_tasks",0)),("Open Risks",m.get("open_risks",0)),("Confidence",f"{project.rag_confidence*100:.0f}%" if project.rag_confidence is not None else "N/A")])}
        </div>
      </div>
    </div>
  </div>
  <div style="position:absolute;bottom:0;left:0;right:0;padding:6px;background:{color};color:#fff;font-size:9px;text-align:center">
    AI Project Health Reporting System — Monthly Report — {date.today().isoformat()}
  </div>
</div>"""
    return _html_wrap(html)


def render_project_slides(project: Project) -> list[str]:
    """Return 5 slide HTML strings for a single-project presentation."""
    return [
        _proj_slide_title(project),
        _proj_slide_dashboard(project),
        _proj_slide_progress(project),
        _proj_slide_risks_recs(project),
        _proj_slide_closing(project),
    ]
