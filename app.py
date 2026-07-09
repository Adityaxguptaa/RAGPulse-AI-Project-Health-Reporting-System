from __future__ import annotations

import base64
import io
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

gemini_key = st.secrets["GEMINI_API_KEY"]

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="RAGPulse : AI Project Health Reporting System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

RAG_HEX = {
    "Green": "#2ecc71",
    "Amber": "#f39c12",
    "Red": "#e74c3c",
    "Unknown": "#95a5a6",
}
RAG_BG = {
    "Green": "#d5f5e3",
    "Amber": "#fef9e7",
    "Red": "#fdedec",
    "Unknown": "#f2f3f4",
}


# Utility helpers
def _check_gemini() -> bool:
    return bool(
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY")
    )


def _rag_badge(status: str) -> str:
    c = RAG_HEX.get(status, "#999")
    return (
        f'<span style="background:{c};color:#fff;padding:5px 18px;'
        f'border-radius:20px;font-weight:700;font-size:14px">{status}</span>'
    )


def _metric_card(label: str, value: Any, color: str = "#3498db") -> str:
    return (
        f'<div style="background:{color}15;border-left:4px solid {color};'
        f'border-radius:8px;padding:12px 16px;text-align:center">'
        f'<div style="font-size:24px;font-weight:700;color:{color}">{value}</div>'
        f'<div style="font-size:11px;color:#555;margin-top:3px">{label}</div></div>'
    )


def _show_pdf(pdf_path: str | Path, height: int = 680) -> None:
    """Embed a PDF inline using pdf.js (works on Streamlit Cloud, unlike raw iframes)."""
    p = Path(pdf_path)
    if not p.exists():
        st.warning("PDF file not found.")
        return
    from streamlit_pdf_viewer import pdf_viewer

    pdf_viewer(p.read_bytes(), height=height)


def _show_slides(slides_html: list[str], label: str = "Slide") -> None:
    """Display a list of HTML slides using Streamlit tabs."""
    if not slides_html:
        st.info("Slide preview not available.")
        return
    tab_labels = [f"{label} {i+1}" for i in range(len(slides_html))]
    tabs = st.tabs(tab_labels)
    for tab, html in zip(tabs, slides_html):
        with tab:
            components.html(html, height=570, scrolling=False)


def _zip_outputs() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in OUTPUT_DIR.iterdir():
            if f.is_file():
                zf.write(f, f.name)
    return buf.getvalue()


def _load_css() -> None:
    st.markdown(
        """
    <style>
    .block-container { padding-top: 1.4rem; }
    div[data-testid="stExpander"] { border-radius: 10px; border: 1px solid #e8ecf0; }
    div[data-testid="metric-container"] { background: #f8f9fa; border-radius: 8px; padding: 8px; }
    .stTabs [data-baseweb="tab"] { font-size: 13px; }
    </style>
    """,
        unsafe_allow_html=True,
    )


# sidebar
def render_sidebar() -> dict[str, Any]:
    st.sidebar.image("https://img.icons8.com/fluency/96/bar-chart.png", width=60)
    st.sidebar.title("RAGPulse : AI Project Health Reporting System")
    st.sidebar.markdown("*AI-powered RAG analysis*")
    st.sidebar.divider()

    gemini_ok = _check_gemini()
    if not gemini_ok:
        st.sidebar.warning(
            "⚠️ **GEMINI_API_KEY not set.**\nAdd to Replit Secrets for AI analysis."
        )

    use_gemini = st.sidebar.toggle(
        "Enable Gemini AI",
        value=gemini_ok,
        disabled=not gemini_ok,
        help="Adds AI-generated summaries, risks, and recommendations. Advisory only — never changes the official RAG colour, which always comes from the rule engine.",
    )

    return {"use_gemini": use_gemini}


def render_portfolio_overview(
    projects: list[Any],
    summary: dict,
    portfolio_pdf: str | None,
    portfolio_slides: list[str],
    pptx_path: str | None,
) -> None:
    st.header("📊 Portfolio Overview")

    dist = summary.get("rag_distribution", {})
    total = summary.get("total_projects", 0)
    avg = summary.get("avg_composite_score", "N/A")
    signal = summary.get("health_signal", "")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Projects", total)
    c2.metric("🟢 Green", dist.get("Green", 0))
    c3.metric("🟡 Amber", dist.get("Amber", 0))
    c4.metric("🔴 Red", dist.get("Red", 0))
    c5.metric("Avg Score", str(avg))

    if signal:
        fn = (
            st.error
            if "high risk" in signal.lower()
            else st.warning if "pressure" in signal.lower() else st.success
        )
        fn(
            f"{'🔴' if 'high risk' in signal.lower() else '🟡' if 'pressure' in signal.lower() else '🟢'}  {signal}"
        )

    # Bar chart
    try:
        import pandas as pd

        chart_df = pd.DataFrame(
            {"Status": list(dist.keys()), "Count": list(dist.values())}
        )
        chart_df = chart_df[chart_df["Count"] > 0]
        if not chart_df.empty:
            st.bar_chart(chart_df.set_index("Status"))
    except Exception:
        pass

    # Cross-project score comparison table
    if len(projects) > 1:
        with st.expander("📋 Cross-Project Score Comparison", expanded=True):
            try:
                import pandas as pd

                rows = []
                for p in projects:
                    m = p.metrics
                    rows.append(
                        {
                            "Project": p.name,
                            "RAG": p.rag_status or "Unknown",
                            "Score": m.get("composite_score", "N/A"),
                            "Confidence": (
                                f"{p.rag_confidence*100:.0f}%"
                                if p.rag_confidence is not None
                                else "N/A"
                            ),
                            "Completion": f"{m.get('completion_percent','N/A')}%",
                            "Delayed": m.get("delayed_tasks", 0),
                            "Open Risks": m.get("open_risks", 0),
                            "Crit. Delayed": m.get("critical_delayed", 0),
                        }
                    )
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception:
                pass

    # Portfolio slides
    if portfolio_slides:
        with st.expander(
            "🎞️ Portfolio Presentation Preview (7 slides)", expanded=False
        ):
            _show_slides(portfolio_slides, label="Slide")
            if pptx_path and Path(pptx_path).exists():
                st.download_button(
                    "⬇️ Download Portfolio PPTX",
                    data=Path(pptx_path).read_bytes(),
                    file_name=Path(pptx_path).name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="dl_portfolio_pptx",
                )

    # Portfolio PDF
    if portfolio_pdf and Path(portfolio_pdf).exists():
        with st.expander("📊 Portfolio Summary PDF", expanded=False):
            _show_pdf(portfolio_pdf, height=720)
            st.download_button(
                "⬇️ Download Portfolio PDF",
                data=Path(portfolio_pdf).read_bytes(),
                file_name=Path(portfolio_pdf).name,
                mime="application/pdf",
                key="dl_portfolio_pdf",
            )

    st.divider()


# Detailed project card


def render_project_card(
    project: Any,
    slides_html: list[str],
    pdf_path: str | None,
    pptx_path: str | None,
) -> None:
    rag = project.rag_status or "Unknown"
    bg = RAG_BG.get(rag, "#f9f9f9")
    border = RAG_HEX.get(rag, "#ccc")
    m = project.metrics
    conf = (
        f"{project.rag_confidence*100:.0f}%"
        if project.rag_confidence is not None
        else "N/A"
    )
    score = m.get("composite_score")

    # ── Header strip ──────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="background:{bg};border-left:6px solid {border};'
        f'border-radius:10px;padding:16px 20px 8px 20px;margin-bottom:4px">',
        unsafe_allow_html=True,
    )
    h1, h2, h3, h4 = st.columns([3, 1.2, 1, 1])
    with h1:
        st.markdown(f"### {project.name}")
        if project.pm:
            st.caption(f"👤 PM: {project.pm}")
        if project.start or project.finish:
            dates = f"📅 {project.start or '?'} → {project.finish or '?'}"
            st.caption(dates)
    with h2:
        st.markdown(rag_badge_html := _rag_badge(rag), unsafe_allow_html=True)
        st.caption(f"Confidence: **{conf}**")
    with h3:
        if score is not None:
            st.metric("Score", f"{score:.3f}")
    with h4:
        rule_rag = getattr(project, "rule_rag", None)
        if rule_rag:
            st.caption(f"Official (rule engine): **{rule_rag}**")
        gemini_rag = getattr(project, "gemini_rag", None)
        agrees = getattr(project, "gemini_agrees", None)
        if gemini_rag:
            icon = "✅" if agrees else "ℹ️"
            st.caption(
                f"{icon} Gemini opinion: **{gemini_rag}**"
                + ("" if agrees else " (advisory only)")
            )
    st.markdown("</div>", unsafe_allow_html=True)

    # Executive summary
    if project.executive_summary:
        st.info(f"📋 **Executive Summary:** {project.executive_summary}")

    # 10 KPI metrics
    colors = [
        "#3498db",
        "#2ecc71",
        "#e74c3c",
        "#f39c12",
        "#9b59b6",
        "#1abc9c",
        "#e67e22",
        "#2980b9",
        "#c0392b",
        "#16a085",
    ]
    kpis = [
        ("Completion %", f"{m.get('completion_percent','N/A')}%", colors[0]),
        (
            "Tasks Done",
            f"{m.get('completed_tasks',0)}/{m.get('total_tasks',0)}",
            colors[1],
        ),
        ("Delayed Tasks", m.get("delayed_tasks", 0), colors[2]),
        (
            "Overdue Milestones",
            f"{m.get('overdue_milestones',0)}/{m.get('total_milestones',0)}",
            colors[3],
        ),
        ("Open Risks", m.get("open_risks", 0), colors[4]),
        ("High/Critical Risks", m.get("high_risks", 0), colors[7]),
        ("Critical Tasks", m.get("critical_tasks", 0), colors[5]),
        ("Critical Delayed", m.get("critical_delayed", 0), colors[6]),
        ("Composite Score", f"{score:.3f}" if score else "N/A", colors[0]),
        ("Confidence", conf, colors[9]),
    ]
    kpi_html = "".join(_metric_card(l, v, c) for l, v, c in kpis)
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:8px 0">'
        f"{kpi_html}</div>",
        unsafe_allow_html=True,
    )

    #  Dimension scores
    st.markdown("#### 📐 RAG Dimension Scores")
    dims = m.get("dimensions", {})
    weights = m.get("weights", {})
    if dims:
        for dim_name, data in dims.items():
            dsc = float(data.get("score", 0))
            wt = weights.get(dim_name, 0)
            rat = data.get("rationale", "") or ""
            d_col = (
                "#2ecc71" if dsc >= 0.7 else ("#f39c12" if dsc >= 0.4 else "#e74c3c")
            )
            pct = int(dsc * 100)
            d1, d2 = st.columns([2.8, 7.2])
            with d1:
                st.markdown(
                    f'<div style="font-weight:600;font-size:13px">'
                    f'{dim_name.replace("_"," ").title()}</div>'
                    f'<div style="font-size:11px;color:#888">Weight: {wt:.0%}</div>',
                    unsafe_allow_html=True,
                )
            with d2:
                st.markdown(
                    f'<div style="background:#e0e0e0;border-radius:6px;height:22px;'
                    f'overflow:hidden;margin-top:8px">'
                    f'<div style="background:{d_col};width:{pct}%;height:100%;'
                    f"border-radius:6px;display:flex;align-items:center;"
                    f'padding-left:10px;color:#fff;font-size:12px;font-weight:700">'
                    f"{dsc:.2f}</div></div>"
                    f'<div style="font-size:11px;color:#555;margin-top:2px">{rat}</div>',
                    unsafe_allow_html=True,
                )

    #  Detailed expandable sections
    with st.expander("🔍 Full Detailed Analysis", expanded=False):
        tab_slides, tab_pdf, tab_tasks, tab_risks, tab_ms, tab_ai = st.tabs(
            [
                "🎞️ Slides",
                "📄 PDF Report",
                "📋 Tasks",
                "🚨 Risk Register",
                "🗓️ Milestones",
                "🤖 AI Reasoning",
            ]
        )

        # Slides tab
        with tab_slides:
            if slides_html:
                _show_slides(slides_html, label="Slide")
            else:
                st.info("Slide preview not available.")
            if pptx_path and Path(pptx_path).exists():
                st.download_button(
                    f"⬇️ Download {project.name} PPTX (5 slides)",
                    data=Path(pptx_path).read_bytes(),
                    file_name=Path(pptx_path).name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key=f"dl_proj_pptx_{project.name}",
                )

        # PDF tab
        with tab_pdf:
            if pdf_path and Path(pdf_path).exists():
                _show_pdf(pdf_path, height=720)
                st.download_button(
                    f"⬇️ Download {project.name} PDF Report",
                    data=Path(pdf_path).read_bytes(),
                    file_name=Path(pdf_path).name,
                    mime="application/pdf",
                    key=f"dl_proj_pdf_{project.name}",
                )
            else:
                st.info("PDF report not generated yet.")

        # Tasks tab
        with tab_tasks:
            all_tasks = project.tasks + project.milestones
            if all_tasks:
                import pandas as pd

                rows = []
                for t in all_tasks[:200]:
                    rows.append(
                        {
                            "Name": t.name,
                            "Status": t.status or "",
                            "% Complete": (
                                f"{t.percent_complete:.0f}%"
                                if t.percent_complete is not None
                                else ""
                            ),
                            "Milestone": "⭐" if t.is_milestone else "",
                            "Critical": "⚠️" if t.is_critical else "",
                            "Delayed": "🔴" if t.is_delayed else "🟢",
                            "Variance (d)": (
                                f"{t.variance_days:+.0f}" if t.variance_days else ""
                            ),
                            "Planned Finish": (
                                t.planned_finish.isoformat() if t.planned_finish else ""
                            ),
                            "Actual Start": (
                                t.actual_start.isoformat() if t.actual_start else ""
                            ),
                            "Float (d)": f"{t.float_days:.0f}" if t.float_days else "",
                        }
                    )
                st.dataframe(
                    pd.DataFrame(rows), use_container_width=True, hide_index=True
                )

                # Summary stats
                total = len(all_tasks)
                done = sum(1 for t in all_tasks if t.is_complete)
                delayed = sum(1 for t in all_tasks if t.is_delayed)
                crits = sum(1 for t in all_tasks if t.is_critical)
                mss = sum(1 for t in all_tasks if t.is_milestone)
                sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                sc1.metric("Total", total)
                sc2.metric("Done", done)
                sc3.metric("Delayed", delayed)
                sc4.metric("Critical", crits)
                sc5.metric("Milestones", mss)
            else:
                st.info("No task data available.")

        # Risk register tab
        with tab_risks:
            raw_risks = project.risks
            ai_risks = project.identified_risks or []
            if raw_risks:
                import pandas as pd

                rows = [
                    {
                        "Description": r.description or "",
                        "Severity": r.severity or "",
                        "Probability": r.probability or "",
                        "Impact": r.impact or "",
                        "Owner": r.owner or "",
                        "Mitigation": (r.mitigation or "")[:80],
                        "Status": r.status or "",
                    }
                    for r in raw_risks
                ]
                st.dataframe(
                    pd.DataFrame(rows), use_container_width=True, hide_index=True
                )
                high = sum(
                    1
                    for r in raw_risks
                    if (r.severity or "").lower() in {"high", "critical"}
                )
                med = sum(
                    1 for r in raw_risks if (r.severity or "").lower() == "medium"
                )
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Total Risks", len(raw_risks))
                rc2.metric("High / Critical", high)
                rc3.metric("Medium", med)
            elif ai_risks:
                st.markdown("**AI-identified risks:**")
                for r in ai_risks:
                    st.markdown(f"- {r}")
            else:
                st.info("No risks found in project data.")

        # Milestones tab
        with tab_ms:
            milestones = project.milestones
            if milestones:
                import pandas as pd

                rows = [
                    {
                        "Milestone": t.name or "",
                        "Status": t.status or "",
                        "% Complete": (
                            f"{t.percent_complete:.0f}%"
                            if t.percent_complete is not None
                            else ""
                        ),
                        "Planned Finish": (
                            t.planned_finish.isoformat() if t.planned_finish else ""
                        ),
                        "Variance (d)": (
                            f"{t.variance_days:+.0f}" if t.variance_days else ""
                        ),
                        "Delayed": "🔴 Yes" if t.is_delayed else "🟢 No",
                        "Complete": "✅" if t.is_complete else "⏳",
                    }
                    for t in milestones
                ]
                st.dataframe(
                    pd.DataFrame(rows), use_container_width=True, hide_index=True
                )
                overdue = project.overdue_milestones
                if overdue:
                    st.error(f"⚠️ {len(overdue)} overdue milestone(s):")
                    for ms in overdue:
                        st.markdown(
                            f"- **{ms.name}** — "
                            f"Due: {ms.planned_finish.isoformat() if ms.planned_finish else 'N/A'} "
                            f"| Overdue by: {ms.variance_days:+.0f} day(s)"
                        )
            else:
                st.info("No milestone data found.")

        # AI Reasoning tab
        with tab_ai:
            if project.reasoning:
                st.markdown("**AI Reasoning:**")
                st.markdown(
                    f'<div style="background:#eaf4fb;border-left:4px solid #3498db;'
                    f"border-radius:0 8px 8px 0;padding:14px 18px;font-size:13px;"
                    f'line-height:1.6">{project.reasoning}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Enable Gemini AI to generate reasoning.")

            col_a, col_b = st.columns(2)
            with col_a:
                if project.identified_risks:
                    st.markdown("**🚨 AI Identified Risks:**")
                    for r in project.identified_risks:
                        st.markdown(f"- {r}")
                if project.missing_data:
                    st.markdown("**⚠️ Data Quality Issues:**")
                    for d in project.missing_data:
                        st.markdown(f"- {d}")
            with col_b:
                if project.recommendations:
                    st.markdown("**✅ Recommendations:**")
                    for i, r in enumerate(project.recommendations, 1):
                        st.markdown(f"{i}. {r}")
                if project.next_week_priorities:
                    st.markdown("**📅 Next Week Priorities:**")
                    for i, p in enumerate(project.next_week_priorities, 1):
                        st.markdown(f"{i}. {p}")

            # Raw metrics JSON
            with st.expander("🔧 Raw Metrics (JSON)", expanded=False):
                import json

                st.json(m)


# Downloads
def render_downloads(results: dict[str, Any]) -> None:
    st.header("📥 Download All Reports")

    has_files = False
    download_cols = st.columns(2)
    col_idx = 0

    # Per-project downloads
    for proj_name, paths in results.get("report_paths", {}).items():
        pdf_p = paths.get("pdf")
        pptx_p = results.get("project_pptx_paths", {}).get(proj_name)
        with download_cols[col_idx % 2]:
            st.markdown(f"**📁 {proj_name}**")
            if pdf_p and Path(pdf_p).exists():
                has_files = True
                st.download_button(
                    "📄 Weekly PDF Report",
                    data=Path(pdf_p).read_bytes(),
                    file_name=Path(pdf_p).name,
                    mime="application/pdf",
                    key=f"dl_pdf_{proj_name}",
                    use_container_width=True,
                )
            if pptx_p and Path(pptx_p).exists():
                has_files = True
                st.download_button(
                    "📑 Weekly PPTX (5 slides)",
                    data=Path(pptx_p).read_bytes(),
                    file_name=Path(pptx_p).name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key=f"dl_pptx_{proj_name}",
                    use_container_width=True,
                )
        col_idx += 1

    st.markdown("---")
    p_pdf = results.get("portfolio_pdf_path")
    p_pptx = results.get("pptx_path")

    c1, c2 = st.columns(2)
    with c1:
        if p_pdf and Path(p_pdf).exists():
            has_files = True
            st.download_button(
                "📊 Portfolio Summary PDF",
                data=Path(p_pdf).read_bytes(),
                file_name=Path(p_pdf).name,
                mime="application/pdf",
                key="dl_port_pdf",
                use_container_width=True,
            )
    with c2:
        if p_pptx and Path(p_pptx).exists():
            has_files = True
            st.download_button(
                "🎞️ Portfolio PPTX (7 slides)",
                data=Path(p_pptx).read_bytes(),
                file_name=Path(p_pptx).name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key="dl_port_pptx",
                use_container_width=True,
            )

    if has_files:
        st.divider()
        st.download_button(
            "⬇️ Download Everything as ZIP",
            data=_zip_outputs(),
            file_name="project_health_reports.zip",
            mime="application/zip",
            key="dl_zip",
            use_container_width=True,
        )
    else:
        st.caption("Run analysis to generate reports.")


# Main
def main() -> None:
    _load_css()
    config = render_sidebar()

    st.title("📊 RAGPulse : AI Project Health Reporting System")
    st.markdown(
        "Upload Excel project plan files to generate **AI-powered RAG health reports**, "
        "PDF weekly reports, PPTX presentations, and a portfolio summary."
    )

    # ── Upload ────────────────────────────────────────────────────────────────
    st.header("📂 Upload Project Files")
    uploaded = st.file_uploader(
        "Upload Excel project plan files (.xlsx / .xls)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Upload one or more Microsoft Project / Excel files to analyse.",
    )

    workbook_dir: Path | None = None
    if uploaded:
        tmp_dir = Path(tempfile.mkdtemp())
        for f in uploaded:
            (tmp_dir / f.name).write_bytes(f.read())
        workbook_dir = tmp_dir
        st.success(
            f"✅ {len(uploaded)} file(s) ready: {', '.join(f.name for f in uploaded)}"
        )

    #  Run Analysis
    st.divider()
    col_btn, col_status = st.columns([2, 5])
    with col_btn:
        run = st.button(
            "🚀 Run Analysis",
            type="primary",
            disabled=(workbook_dir is None),
            use_container_width=True,
        )

    if run and workbook_dir:
        if config["use_gemini"] and not _check_gemini():
            st.error("⚠️ Gemini API key not found")
        else:
            status_box = col_status.empty()
            progress = st.progress(0)
            msgs: list[str] = []

            def _cb(msg: str) -> None:
                msgs.append(msg)
                status_box.info(f"⏳ {msg}")
                progress.progress(min(len(msgs) * 9, 95))

            try:
                from src.analysis import run_full_pipeline

                results = run_full_pipeline(
                    workbook_dir=workbook_dir,
                    output_dir=OUTPUT_DIR,
                    use_gemini=config["use_gemini"],
                    status_callback=_cb,
                )
                progress.progress(100)
                status_box.success("✅ Analysis complete!")
                st.session_state["results"] = results
            except Exception as exc:
                progress.empty()
                st.error(f"❌ Analysis failed: {exc}")
                logger.exception("Pipeline error")

    # Display Results
    results = st.session_state.get("results")
    if not results:
        return

    if results.get("error"):
        st.error(f"⚠️ {results['error']}")
        return

    projects = results.get("projects", [])
    portfolio_summary = results.get("portfolio_summary", {})
    portfolio_pdf = results.get("portfolio_pdf_path")
    pptx_path = results.get("pptx_path")
    portfolio_slides = results.get("portfolio_slides_html", [])
    proj_slides = results.get("project_slides_html", {})
    proj_pptx = results.get("project_pptx_paths", {})
    report_paths = results.get("report_paths", {})

    # Portfolio overview (only when multiple projects)
    if portfolio_summary and len(projects) > 1:
        render_portfolio_overview(
            projects,
            portfolio_summary,
            portfolio_pdf,
            portfolio_slides,
            pptx_path,
        )

    # Per-project analysis
    st.header("🏗️ Weekly Project Analysis")
    for project in projects:
        slides = proj_slides.get(project.name, [])
        pdf_path = report_paths.get(project.name, {}).get("pdf")
        pptx_p = proj_pptx.get(project.name)
        render_project_card(project, slides, pdf_path, pptx_p)
        st.divider()

    # For single-project: also show its PDF and slides outside the card
    if len(projects) == 1:
        p = projects[0]
        pdf_p = report_paths.get(p.name, {}).get("pdf")
        slides = proj_slides.get(p.name, [])
        pp_path = proj_pptx.get(p.name)

        if slides:
            st.subheader(f"🎞️ {p.name} — Slide Preview (5 slides)")
            _show_slides(slides, label="Slide")
            if pp_path and Path(pp_path).exists():
                st.download_button(
                    f"⬇️ Download {p.name} PPTX",
                    data=Path(pp_path).read_bytes(),
                    file_name=Path(pp_path).name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="dl_single_pptx",
                )

        if pdf_p and Path(pdf_p).exists():
            st.subheader(f"📄 {p.name} — Weekly PDF Report")
            _show_pdf(pdf_p, height=750)

    # Downloads section
    st.divider()
    render_downloads(results)


if __name__ == "__main__":
    main()
