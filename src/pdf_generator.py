"""PDF report generator using ReportLab — project weekly reports + portfolio summary."""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from src.models import Project

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
try:
    from reportlab.lib.colors import HexColor, white, black, Color
    C_GREEN   = HexColor("#2ecc71")
    C_AMBER   = HexColor("#f39c12")
    C_RED     = HexColor("#e74c3c")
    C_BLUE    = HexColor("#3498db")
    C_DARK    = HexColor("#2c3e50")
    C_GREY    = HexColor("#95a5a6")
    C_LIGHT   = HexColor("#f8f9fa")
    C_LIGHTBL = HexColor("#eaf4fb")
    C_WHITE   = white
    C_BLACK   = black
except ImportError:
    pass

_RAG_COLOR = {"Green": "#2ecc71", "Amber": "#f39c12", "Red": "#e74c3c"}
_RAG_HEX   = {"Green": C_GREEN,   "Amber": C_AMBER,   "Red": C_RED}

def _rag_hex(status: str):
    return _RAG_HEX.get(status, C_GREY)

def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name)


# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    styles = getSampleStyleSheet()

    custom = {
        "CoverTitle": ParagraphStyle("CoverTitle", parent=styles["Title"],
            fontSize=28, leading=34, textColor=C_WHITE, alignment=TA_CENTER),
        "CoverSub": ParagraphStyle("CoverSub", parent=styles["Normal"],
            fontSize=14, leading=18, textColor=C_WHITE, alignment=TA_CENTER, spaceAfter=8),
        "SectionH1": ParagraphStyle("SectionH1", parent=styles["Heading1"],
            fontSize=16, leading=20, textColor=C_DARK, spaceBefore=14, spaceAfter=4,
            borderPad=(0,0,4,0)),
        "SectionH2": ParagraphStyle("SectionH2", parent=styles["Heading2"],
            fontSize=13, leading=17, textColor=C_DARK, spaceBefore=10, spaceAfter=3),
        "Body": ParagraphStyle("Body", parent=styles["Normal"],
            fontSize=10, leading=14, textColor=C_DARK, spaceAfter=4),
        "BodySmall": ParagraphStyle("BodySmall", parent=styles["Normal"],
            fontSize=9, leading=12, textColor=C_DARK, spaceAfter=2),
        "Bullet": ParagraphStyle("Bullet", parent=styles["Normal"],
            fontSize=10, leading=14, textColor=C_DARK, leftIndent=12,
            bulletIndent=4, spaceAfter=3),
        "RagLabel": ParagraphStyle("RagLabel", parent=styles["Normal"],
            fontSize=11, leading=14, textColor=C_WHITE, alignment=TA_CENTER),
        "Footer": ParagraphStyle("Footer", parent=styles["Normal"],
            fontSize=8, textColor=C_GREY, alignment=TA_CENTER),
        "MetricVal": ParagraphStyle("MetricVal", parent=styles["Normal"],
            fontSize=18, leading=22, textColor=C_DARK, alignment=TA_CENTER),
        "MetricLbl": ParagraphStyle("MetricLbl", parent=styles["Normal"],
            fontSize=9, leading=12, textColor=C_GREY, alignment=TA_CENTER),
        "SummaryBox": ParagraphStyle("SummaryBox", parent=styles["Normal"],
            fontSize=11, leading=15, textColor=C_DARK, leftIndent=8, rightIndent=8,
            spaceBefore=4, spaceAfter=4),
    }
    styles.add(custom["CoverTitle"], alias="CoverTitle")
    return styles, custom


def _table_style_base(header_color=None):
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    hc = header_color or C_DARK
    return TableStyle([
        ("BACKGROUND",  (0,0), (-1,0),  hc),
        ("TEXTCOLOR",   (0,0), (-1,0),  C_WHITE),
        ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,0),  10),
        ("ALIGN",       (0,0), (-1,0),  "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_LIGHT]),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,1), (-1,-1), 9),
        ("ALIGN",       (1,1), (-1,-1), "CENTER"),
        ("ALIGN",       (0,1), (0,-1),  "LEFT"),
        ("GRID",        (0,0), (-1,-1), 0.4, C_GREY),
        ("TOPPADDING",  (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING",(0,0), (-1,-1), 6),
    ])


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _score_bar_drawing(score: float, color, width=120, height=12):
    from reportlab.graphics.shapes import Drawing, Rect
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=HexColor("#e0e0e0"), strokeWidth=0))
    d.add(Rect(0, 0, width * score, height, fillColor=color, strokeWidth=0))
    return d


def _cover_canvas(canvas, doc, rag_status: str, project_name: str):
    """Draw the colored cover background."""
    from reportlab.lib.units import inch
    canvas.saveState()
    rag_color = _rag_hex(rag_status)
    canvas.setFillColor(C_DARK)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas.setFillColor(rag_color)
    canvas.rect(0, doc.pagesize[1]*0.35, doc.pagesize[0], doc.pagesize[1]*0.08, fill=1, stroke=0)
    canvas.setFillColor(C_BLUE)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1]*0.08, fill=1, stroke=0)
    canvas.restoreState()


def _page_header_footer(canvas, doc, title: str = "AI Project Health Report"):
    from reportlab.lib.units import inch
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setFillColor(C_DARK)
    canvas.rect(0, h - 0.55*inch, w, 0.55*inch, fill=1, stroke=0)
    canvas.setFillColor(C_WHITE)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(0.4*inch, h - 0.35*inch, title)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 0.4*inch, h - 0.35*inch, date.today().isoformat())
    canvas.setFillColor(C_LIGHT)
    canvas.rect(0, 0, w, 0.4*inch, fill=1, stroke=0)
    canvas.setFillColor(C_GREY)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(w/2, 0.15*inch, f"AI Project Health Reporting System  —  Page {canvas.getPageNumber()}")
    canvas.restoreState()


# ── Project PDF ───────────────────────────────────────────────────────────────

def generate_project_pdf(project: Project, output_dir: str | Path) -> Path:
    """Generate a weekly PDF health report for a single project."""
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, PageBreak, KeepTogether)
    from reportlab.lib.units import inch
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import FrameBreak

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf_path = out / f"{_safe_name(project.name)}_weekly_report.pdf"

    styles, cs = _styles()
    rag  = project.rag_status or "Unknown"
    m    = project.metrics
    conf = f"{project.rag_confidence*100:.0f}%" if project.rag_confidence is not None else "N/A"

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=0.6*inch, leftMargin=0.6*inch,
        topMargin=0.8*inch, bottomMargin=0.55*inch,
    )

    header_cb = lambda c, d: _page_header_footer(c, d, f"Weekly Report: {project.name}")

    story = []

    # ── Cover block ────────────────────────────────────────────────────────────
    rag_color_hex = _RAG_COLOR.get(rag, "#95a5a6")
    cover_data = [
        [Paragraph(f"<font color='white' size='22'><b>Weekly Project Health Report</b></font>", cs["Body"])],
        [Paragraph(f"<font color='white' size='15'>{project.name}</font>", cs["Body"])],
        [Paragraph(f"<font color='white' size='11'>Report Date: {date.today().isoformat()} &nbsp;&nbsp; PM: {project.pm or 'N/A'}</font>", cs["Body"])],
    ]
    cover_tbl = Table(cover_data, colWidths=[doc.width])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_DARK),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 6))

    # RAG + Score header strip
    rag_data = [[
        Paragraph(f"<font color='white'><b>RAG Status</b></font>", cs["MetricLbl"]),
        Paragraph(f"<font color='white'><b>Composite Score</b></font>", cs["MetricLbl"]),
        Paragraph(f"<font color='white'><b>Confidence</b></font>", cs["MetricLbl"]),
        Paragraph(f"<font color='white'><b>Completion</b></font>", cs["MetricLbl"]),
    ],[
        Paragraph(f"<font color='white' size='16'><b>{rag}</b></font>", cs["MetricVal"]),
        Paragraph(f"<font color='white' size='16'><b>{m.get('composite_score','N/A')}</b></font>", cs["MetricVal"]),
        Paragraph(f"<font color='white' size='16'><b>{conf}</b></font>", cs["MetricVal"]),
        Paragraph(f"<font color='white' size='16'><b>{m.get('completion_percent','N/A')}%</b></font>", cs["MetricVal"]),
    ]]
    rag_tbl = Table(rag_data, colWidths=[doc.width/4]*4)
    rag_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), _rag_hex(rag)),
        ("BACKGROUND", (0,0), (0,-1), _rag_hex(rag)),
        ("TOPPADDING",  (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    story.append(rag_tbl)
    story.append(Spacer(1, 10))

    # ── Executive Summary ──────────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", cs["SectionH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
    summary_text = project.executive_summary or "No summary available."
    box_data = [[Paragraph(summary_text, cs["SummaryBox"])]]
    box_tbl = Table(box_data, colWidths=[doc.width])
    box_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_LIGHTBL),
        ("BOX", (0,0), (-1,-1), 1, C_BLUE),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(box_tbl)
    story.append(Spacer(1, 8))

    # ── Key Metrics ────────────────────────────────────────────────────────────
    story.append(Paragraph("Key Metrics", cs["SectionH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))

    metrics_rows = [
        ["Metric", "Value", "Metric", "Value"],
        ["Total Tasks",          str(m.get("total_tasks",     "N/A")),
         "Completed Tasks",      str(m.get("completed_tasks", "N/A"))],
        ["Delayed Tasks",        str(m.get("delayed_tasks",   "N/A")),
         "Open Risks",           str(m.get("open_risks",      "N/A"))],
        ["Overdue Milestones",   f"{m.get('overdue_milestones','N/A')} / {m.get('total_milestones','N/A')}",
         "Critical Tasks",       str(m.get("critical_tasks",  "N/A"))],
        ["Critical Delayed",     str(m.get("critical_delayed","N/A")),
         "Data Quality Score",   str(m.get("dimensions",{}).get("data_quality",{}).get("score","N/A"))],
    ]
    mt = Table(metrics_rows, colWidths=[doc.width*0.3, doc.width*0.2]*2)
    mt.setStyle(_table_style_base(C_DARK))
    story.append(mt)
    story.append(Spacer(1, 8))

    # ── Dimension Scores ───────────────────────────────────────────────────────
    story.append(Paragraph("RAG Dimension Scores", cs["SectionH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))

    dim_rows = [["Dimension", "Score", "Weight", "Status", "Rationale"]]
    for dim_name, data in m.get("dimensions", {}).items():
        score  = float(data.get("score", 0))
        weight = m.get("weights", {}).get(dim_name, 0)
        rag_d  = "Green" if score >= 0.7 else ("Amber" if score >= 0.4 else "Red")
        rat    = (data.get("rationale", "") or "")[:80]
        dim_rows.append([
            dim_name.replace("_"," ").title(),
            f"{score:.2f}",
            f"{weight:.0%}",
            rag_d,
            rat,
        ])
    dim_col_w = [doc.width*0.25, doc.width*0.1, doc.width*0.1, doc.width*0.1, doc.width*0.45]
    dt = Table(dim_rows, colWidths=dim_col_w)
    dt_style = _table_style_base(C_BLUE)
    # Color RAG status cells
    for ri, row in enumerate(dim_rows[1:], start=1):
        rag_d = row[3]
        color = _rag_hex(rag_d)
        dt_style.add("BACKGROUND", (3, ri), (3, ri), color)
        dt_style.add("TEXTCOLOR",  (3, ri), (3, ri), C_WHITE)
        dt_style.add("FONTNAME",   (3, ri), (3, ri), "Helvetica-Bold")
    dt.setStyle(dt_style)
    story.append(dt)
    story.append(Spacer(1, 8))

    # ── AI Reasoning ───────────────────────────────────────────────────────────
    if project.reasoning:
        story.append(Paragraph("AI Reasoning", cs["SectionH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
        story.append(Paragraph(project.reasoning, cs["Body"]))
        story.append(Spacer(1, 6))

    # ── Risks & Recommendations ────────────────────────────────────────────────
    risks = project.identified_risks or []
    recs  = project.recommendations  or []
    prios = project.next_week_priorities or []

    if risks or recs or prios:
        story.append(Paragraph("Risks, Recommendations & Priorities", cs["SectionH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
        col_data = [["🚨 Identified Risks", "✅ Recommendations", "📋 Next Week Priorities"]]
        r_items = [f"• {r}" for r in risks] or ["None identified"]
        c_items = [f"• {r}" for r in recs]  or ["None"]
        p_items = [f"• {p}" for p in prios] or ["None"]
        max_len = max(len(r_items), len(c_items), len(p_items))
        r_items += [""] * (max_len - len(r_items))
        c_items += [""] * (max_len - len(c_items))
        p_items += [""] * (max_len - len(p_items))
        for r, c, p in zip(r_items, c_items, p_items):
            col_data.append([
                Paragraph(r, cs["BodySmall"]),
                Paragraph(c, cs["BodySmall"]),
                Paragraph(p, cs["BodySmall"]),
            ])
        rcp_tbl = Table(col_data, colWidths=[doc.width/3]*3)
        rcp_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0),  C_DARK),
            ("TEXTCOLOR",    (0,0), (-1,0),  C_WHITE),
            ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,0),  9),
            ("ALIGN",        (0,0), (-1,0),  "CENTER"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [C_WHITE, C_LIGHT]),
            ("GRID",         (0,0), (-1,-1), 0.4, C_GREY),
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 5),
        ]))
        story.append(rcp_tbl)
        story.append(Spacer(1, 8))

    # ── Risk Register (raw risks) ──────────────────────────────────────────────
    if project.risks:
        story.append(Paragraph("Risk Register", cs["SectionH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
        risk_rows = [["#", "Description", "Severity", "Probability", "Owner", "Status"]]
        for i, r in enumerate(project.risks[:20], 1):
            risk_rows.append([
                str(i),
                (r.description or "")[:60],
                r.severity or "",
                r.probability or "",
                (r.owner or "")[:20],
                r.status or "",
            ])
        risk_col_w = [doc.width*0.05, doc.width*0.38, doc.width*0.1,
                      doc.width*0.12, doc.width*0.18, doc.width*0.17]
        rk_tbl = Table(risk_rows, colWidths=risk_col_w)
        rk_style = _table_style_base(HexColor("#c0392b"))
        for ri, row in enumerate(risk_rows[1:], start=1):
            sev = (row[2] or "").lower()
            if sev in {"high", "critical"}:
                rk_style.add("BACKGROUND", (2, ri), (2, ri), HexColor("#fdedec"))
                rk_style.add("TEXTCOLOR",  (2, ri), (2, ri), HexColor("#c0392b"))
                rk_style.add("FONTNAME",   (2, ri), (2, ri), "Helvetica-Bold")
        rk_tbl.setStyle(rk_style)
        story.append(rk_tbl)
        story.append(Spacer(1, 8))

    # ── Task Summary ───────────────────────────────────────────────────────────
    all_tasks = project.tasks + project.milestones
    if all_tasks:
        story.append(Paragraph(f"Task Summary (Top {min(25, len(all_tasks))} of {len(all_tasks)})", cs["SectionH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
        task_rows = [["Task / Milestone", "Status", "% Done", "Milestone", "Critical", "Delayed", "Variance"]]
        for t in all_tasks[:25]:
            task_rows.append([
                (t.name or "")[:45],
                t.status or "",
                f"{t.percent_complete:.0f}%" if t.percent_complete is not None else "",
                "✓" if t.is_milestone else "",
                "⚠" if t.is_critical else "",
                "🔴" if t.is_delayed else "🟢",
                f"{t.variance_days:+.0f}d" if t.variance_days else "",
            ])
        task_col_w = [doc.width*0.38, doc.width*0.12, doc.width*0.08,
                      doc.width*0.1, doc.width*0.1, doc.width*0.1, doc.width*0.12]
        tk_tbl = Table(task_rows, colWidths=task_col_w)
        tk_tbl.setStyle(_table_style_base(C_DARK))
        story.append(tk_tbl)
        story.append(Spacer(1, 6))

    # ── Overdue Milestones ─────────────────────────────────────────────────────
    overdue = project.overdue_milestones
    if overdue:
        story.append(Paragraph("Overdue Milestones", cs["SectionH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e74c3c")))
        om_rows = [["Milestone", "Planned Finish", "Variance (days)"]]
        for ms in overdue:
            om_rows.append([
                ms.name or "",
                ms.planned_finish.isoformat() if ms.planned_finish else "N/A",
                f"{ms.variance_days:+.0f}" if ms.variance_days else "N/A",
            ])
        om_tbl = Table(om_rows, colWidths=[doc.width*0.55, doc.width*0.25, doc.width*0.2])
        om_style = _table_style_base(HexColor("#e74c3c"))
        om_tbl.setStyle(om_style)
        story.append(om_tbl)

    story.append(Spacer(1, 12))
    story.append(Paragraph("_Generated by AI Project Health Reporting System_", cs["Footer"]))

    doc.build(story, onFirstPage=header_cb, onLaterPages=header_cb)
    logger.info("Project PDF saved: %s", pdf_path)
    return pdf_path


# ── Portfolio PDF ─────────────────────────────────────────────────────────────

def generate_portfolio_pdf(
    projects: list[Project],
    portfolio_summary: dict[str, Any],
    output_dir: str | Path,
) -> Path:
    """Generate a portfolio-level summary PDF."""
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, PageBreak)
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import A4

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf_path = out / "portfolio_summary.pdf"

    styles, cs = _styles()
    dist   = portfolio_summary.get("rag_distribution", {})
    total  = portfolio_summary.get("total_projects", 0)
    avg    = portfolio_summary.get("avg_composite_score", "N/A")
    signal = portfolio_summary.get("health_signal", "")

    sig_color = (C_RED if "high risk" in signal.lower()
                 else C_AMBER if "pressure" in signal.lower()
                 else C_GREEN)

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=0.6*inch, leftMargin=0.6*inch,
        topMargin=0.8*inch, bottomMargin=0.55*inch,
    )
    header_cb = lambda c, d: _page_header_footer(c, d, "Portfolio Health Summary")
    story = []

    # Cover strip
    cov_data = [
        [Paragraph("<font color='white' size='20'><b>Portfolio Health Summary</b></font>", cs["Body"])],
        [Paragraph(f"<font color='white' size='11'>Report Date: {portfolio_summary.get('report_date', date.today().isoformat())}</font>", cs["Body"])],
    ]
    cov_tbl = Table(cov_data, colWidths=[doc.width])
    cov_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_DARK),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 16),
    ]))
    story.append(cov_tbl)
    story.append(Spacer(1, 6))

    # KPI row
    kpi_data = [
        [Paragraph("<font color='white'><b>Total</b></font>", cs["MetricLbl"]),
         Paragraph("<font color='white'><b>🟢 Green</b></font>", cs["MetricLbl"]),
         Paragraph("<font color='white'><b>🟡 Amber</b></font>", cs["MetricLbl"]),
         Paragraph("<font color='white'><b>🔴 Red</b></font>", cs["MetricLbl"]),
         Paragraph("<font color='white'><b>Avg Score</b></font>", cs["MetricLbl"])],
        [Paragraph(f"<font color='white' size='18'><b>{total}</b></font>", cs["MetricVal"]),
         Paragraph(f"<font color='white' size='18'><b>{dist.get('Green',0)}</b></font>", cs["MetricVal"]),
         Paragraph(f"<font color='white' size='18'><b>{dist.get('Amber',0)}</b></font>", cs["MetricVal"]),
         Paragraph(f"<font color='white' size='18'><b>{dist.get('Red',0)}</b></font>", cs["MetricVal"]),
         Paragraph(f"<font color='white' size='18'><b>{avg}</b></font>", cs["MetricVal"])],
    ]
    kpi_colors = [C_DARK, C_GREEN, C_AMBER, C_RED, C_BLUE]
    kpi_tbl = Table(kpi_data, colWidths=[doc.width/5]*5)
    kpi_style = TableStyle([("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)])
    for ci, col_color in enumerate(kpi_colors):
        kpi_style.add("BACKGROUND", (ci,0), (ci,-1), col_color)
    kpi_tbl.setStyle(kpi_style)
    story.append(kpi_tbl)
    story.append(Spacer(1, 6))

    # Health signal
    sig_data = [[Paragraph(f"<font color='white'><b>Portfolio Signal: {signal}</b></font>", cs["Body"])]]
    sig_tbl = Table(sig_data, colWidths=[doc.width])
    sig_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), sig_color),
        ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),12),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 10))

    # Project Scorecard
    story.append(Paragraph("Project Scorecard", cs["SectionH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
    sc_rows = [["Project", "RAG", "Score", "Confidence", "Completion", "Delayed", "Risks", "Summary"]]
    for p in projects:
        sc_rows.append([
            p.name[:28],
            p.rag_status or "Unknown",
            str(p.metrics.get("composite_score","N/A")),
            f"{p.rag_confidence*100:.0f}%" if p.rag_confidence is not None else "N/A",
            f"{p.metrics.get('completion_percent','N/A')}%",
            str(p.metrics.get("delayed_tasks","N/A")),
            str(p.metrics.get("open_risks","N/A")),
            Paragraph((p.executive_summary or "")[:80], cs["BodySmall"]),
        ])
    sc_col_w = [doc.width*0.18, doc.width*0.07, doc.width*0.07, doc.width*0.08,
                doc.width*0.1, doc.width*0.07, doc.width*0.07, doc.width*0.36]
    sc_tbl = Table(sc_rows, colWidths=sc_col_w)
    sc_style = _table_style_base(C_DARK)
    for ri, row in enumerate(sc_rows[1:], start=1):
        rag_v = row[1]
        color = _rag_hex(rag_v)
        sc_style.add("BACKGROUND", (1,ri), (1,ri), color)
        sc_style.add("TEXTCOLOR",  (1,ri), (1,ri), C_WHITE)
        sc_style.add("FONTNAME",   (1,ri), (1,ri), "Helvetica-Bold")
    sc_tbl.setStyle(sc_style)
    story.append(sc_tbl)
    story.append(Spacer(1, 10))

    # Emerging Risks
    emerging = portfolio_summary.get("emerging_risks", [])
    if emerging:
        story.append(Paragraph("Emerging Risks Across Portfolio", cs["SectionH1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e74c3c")))
        er_rows = [["#", "Risk"]]
        for i, r in enumerate(emerging, 1):
            er_rows.append([str(i), r[:120]])
        er_tbl = Table(er_rows, colWidths=[doc.width*0.06, doc.width*0.94])
        er_tbl.setStyle(_table_style_base(HexColor("#c0392b")))
        story.append(er_tbl)
        story.append(Spacer(1, 8))

    # Dimension comparison across projects
    story.append(Paragraph("Dimension Score Comparison", cs["SectionH1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE))
    dim_names = list(projects[0].metrics.get("dimensions", {}).keys()) if projects else []
    if dim_names:
        comp_header = ["Project"] + [d.replace("_"," ").title()[:12] for d in dim_names]
        comp_rows = [comp_header]
        for p in projects:
            row = [p.name[:25]]
            for dn in dim_names:
                score = p.metrics.get("dimensions",{}).get(dn,{}).get("score","N/A")
                row.append(f"{float(score):.2f}" if score != "N/A" else "N/A")
            comp_rows.append(row)
        n_cols = len(comp_header)
        comp_col_w = [doc.width*0.25] + [doc.width*0.75/max(n_cols-1,1)] * (n_cols-1)
        comp_tbl = Table(comp_rows, colWidths=comp_col_w)
        comp_style = _table_style_base(C_BLUE)
        for ri, row in enumerate(comp_rows[1:], start=1):
            for ci, val in enumerate(row[1:], start=1):
                try:
                    v = float(val)
                    color = (C_GREEN if v >= 0.7 else C_AMBER if v >= 0.4 else C_RED)
                    comp_style.add("TEXTCOLOR", (ci,ri), (ci,ri), color)
                    comp_style.add("FONTNAME",  (ci,ri), (ci,ri), "Helvetica-Bold")
                except (ValueError, TypeError):
                    pass
        comp_tbl.setStyle(comp_style)
        story.append(comp_tbl)

    story.append(Spacer(1, 12))
    story.append(Paragraph("_Generated by AI Project Health Reporting System_", cs["Footer"]))

    doc.build(story, onFirstPage=header_cb, onLaterPages=header_cb)
    logger.info("Portfolio PDF saved: %s", pdf_path)
    return pdf_path
