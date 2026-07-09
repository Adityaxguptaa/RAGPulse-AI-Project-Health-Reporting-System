"""High-level analysis orchestrator tying parsing, RAG, Gemini, PDF, and PPT together."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.gemini_client import call_gemini_json
from src.models import Project
from src.rag_engine import build_gemini_prompt, build_metrics_dict, compute_rule_rag

logger = logging.getLogger(__name__)


def analyse_project(project: Project, use_gemini: bool = True) -> Project:

    rule_rag, composite, dimensions = compute_rule_rag(project)
    project.rule_rag = rule_rag
    project.metrics = build_metrics_dict(project, dimensions, composite)
    project.rag_status = rule_rag  # authoritative in both modes
    project.rag_confidence = round(composite, 2)  # authoritative in both modes
    logger.info(
        "Rule engine RAG for '%s': %s (score=%.3f)", project.name, rule_rag, composite
    )

    if not use_gemini:
        project.executive_summary = f"Rule-engine determined {rule_rag} status (composite score: {composite:.3f})."
        project.reasoning = "; ".join(d.rationale for d in dimensions)
        return project

    prompt = build_gemini_prompt(project, dimensions, composite, rule_rag)
    try:
        result: dict[str, Any] = call_gemini_json(prompt)

        raw_rag = result.get("final_rag", rule_rag)
        project.gemini_rag = (
            raw_rag if raw_rag in {"Green", "Amber", "Red"} else rule_rag
        )
        project.gemini_agrees = project.gemini_rag == rule_rag

        def _safe_str(val: Any, fallback: str = "") -> str:
            return str(val).strip() if val else fallback

        def _safe_list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(i) for i in val if i]
            if isinstance(val, str) and val:
                return [val]
            return []

        project.executive_summary = _safe_str(result.get("executive_summary")) or (
            f"Rule-engine determined {rule_rag} status (composite score: {composite:.3f})."
        )
        project.reasoning = _safe_str(result.get("reasoning")) or "; ".join(
            d.rationale for d in dimensions
        )
        project.identified_risks = _safe_list(result.get("risks"))
        project.recommendations = _safe_list(result.get("recommendations"))
        project.missing_data = _safe_list(result.get("missing_data"))
        project.next_week_priorities = _safe_list(result.get("next_week_priorities"))

        if not project.gemini_agrees:
            note = (
                f"Note: Gemini's holistic read leans {project.gemini_rag}, "
                f"but the rule-engine score of {composite:.3f} keeps the official "
                f"status at {rule_rag} for consistency."
            )
            project.reasoning = f"{project.reasoning} {note}".strip()

        logger.info(
            "Gemini enrichment for '%s' complete (rule_rag=%s kept as final; "
            "gemini_rag=%s, agrees=%s)",
            project.name,
            rule_rag,
            project.gemini_rag,
            project.gemini_agrees,
        )

    except Exception as exc:
        logger.warning(
            "Gemini failed for '%s', continuing with rule-engine result only: %s",
            project.name,
            exc,
        )
        project.executive_summary = (
            f"Rule-engine determined {rule_rag} status (Gemini unavailable)."
        )
        project.reasoning = "; ".join(d.rationale for d in dimensions)

    return project


def run_full_pipeline(
    workbook_dir: str | Path,
    output_dir: str | Path,
    use_gemini: bool = True,
    status_callback: Any = None,
) -> dict[str, Any]:
    """End-to-end pipeline: parse → analyse → PDF reports → portfolio → PPTXs.

    Returns a results dict with paths, HTML slide data, and project objects.
    """
    from src.parser import load_all_workbooks
    from src.pdf_generator import generate_portfolio_pdf, generate_project_pdf
    from src.portfolio import compute_portfolio_summary, generate_and_save_portfolio
    from src.ppt_generator import generate_pptx, generate_project_pptx
    from src.slide_renderer import render_portfolio_slides, render_project_slides

    def _status(msg: str) -> None:
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    _status(f"Loading workbooks from {workbook_dir}...")
    projects = load_all_workbooks(workbook_dir)

    if not projects:
        return {"error": "No Excel workbooks found", "projects": [], "report_paths": {}}

    _status(f"Found {len(projects)} project(s). Running analysis...")

    all_report_paths: dict[str, dict] = {}

    for project in projects:
        _status(f"Analysing: {project.name}")
        analyse_project(project, use_gemini=use_gemini)

        _status(f"Generating PDF report: {project.name}")
        try:
            pdf_path = generate_project_pdf(project, output_dir)
            all_report_paths[project.name] = {"pdf": str(pdf_path)}
        except Exception as exc:
            logger.error("PDF generation failed for '%s': %s", project.name, exc)
            all_report_paths[project.name] = {}

    # Portfolio summary
    _status("Building portfolio summary...")
    portfolio_md_path, portfolio_summary = generate_and_save_portfolio(
        projects, output_dir
    )

    _status("Generating portfolio PDF...")
    portfolio_pdf_path: str | None = None
    try:
        p = generate_portfolio_pdf(projects, portfolio_summary, output_dir)
        portfolio_pdf_path = str(p)
    except Exception as exc:
        logger.error("Portfolio PDF failed: %s", exc)

    # Portfolio PPTX
    _status("Generating portfolio presentation (PPTX)...")
    pptx_path: str | None = None
    try:
        pptx_path = str(generate_pptx(projects, portfolio_summary, output_dir))
    except Exception as exc:
        logger.error("Portfolio PPTX failed: %s", exc)

    # Per-project PPTXs
    _status("Generating per-project presentations...")
    project_pptx_paths: dict[str, str] = {}
    for project in projects:
        try:
            pp = generate_project_pptx(project, output_dir)
            project_pptx_paths[project.name] = str(pp)
        except Exception as exc:
            logger.error("Per-project PPTX failed for '%s': %s", project.name, exc)

    # HTML slide previews (for in-app display)
    _status("Rendering slide previews...")
    portfolio_slides_html: list[str] = []
    try:
        portfolio_slides_html = render_portfolio_slides(projects, portfolio_summary)
    except Exception as exc:
        logger.error("Portfolio slide render failed: %s", exc)

    project_slides_html: dict[str, list[str]] = {}
    for project in projects:
        try:
            project_slides_html[project.name] = render_project_slides(project)
        except Exception as exc:
            logger.error("Project slide render failed for '%s': %s", project.name, exc)

    _status("Pipeline complete!")

    return {
        "projects": projects,
        "report_paths": all_report_paths,  # {proj_name: {"pdf": path}}
        "portfolio_pdf_path": portfolio_pdf_path,
        "portfolio_summary": portfolio_summary,
        "pptx_path": pptx_path,  # portfolio PPTX
        "project_pptx_paths": project_pptx_paths,  # {proj_name: path}
        "portfolio_slides_html": portfolio_slides_html,  # [html, html, ...]
        "project_slides_html": project_slides_html,  # {proj_name: [html, ...]}
    }
