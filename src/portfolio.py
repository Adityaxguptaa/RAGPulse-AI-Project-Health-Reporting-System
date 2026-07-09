"""Portfolio summary aggregation."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from src.models import Project

logger = logging.getLogger(__name__)


def compute_portfolio_summary(projects: list[Project]) -> dict[str, Any]:
    """Aggregate cross-project statistics into a portfolio summary dict."""
    rag_dist: dict[str, int] = {"Green": 0, "Amber": 0, "Red": 0, "Unknown": 0}
    scores: list[float] = []
    all_risks: list[str] = []
    trends: list[str] = []

    for p in projects:
        rag = p.rag_status or "Unknown"
        rag_dist[rag] = rag_dist.get(rag, 0) + 1

        if p.metrics.get("composite_score") is not None:
            scores.append(float(p.metrics["composite_score"]))

        # Collect high/critical risks across portfolio
        for r in p.risks:
            if (r.severity or "").lower() in {"high", "critical"}:
                all_risks.append(f"[{p.name}] {r.description}")

        # Trend signals from next-week priorities
        for rec in p.next_week_priorities[:2]:
            trends.append(f"[{p.name}] {rec}")

    avg_score = round(sum(scores) / len(scores), 3) if scores else None

    # Health trend signal
    red_count = rag_dist.get("Red", 0)
    total = len(projects)
    health_signal = (
        "Portfolio at high risk — multiple Red projects" if red_count >= total * 0.5
        else "Portfolio under pressure — several Amber projects" if rag_dist.get("Amber", 0) >= total * 0.5
        else "Portfolio broadly healthy"
    )

    return {
        "report_date": date.today().isoformat(),
        "total_projects": total,
        "rag_distribution": rag_dist,
        "avg_composite_score": avg_score,
        "health_signal": health_signal,
        "emerging_risks": all_risks[:10],
        "trends": trends[:10],
        "projects": [
            {
                "name": p.name,
                "rag": p.rag_status,
                "confidence": p.rag_confidence,
                "composite_score": p.metrics.get("composite_score"),
                "executive_summary": p.executive_summary,
            }
            for p in projects
        ],
    }


def render_portfolio_markdown(summary: dict[str, Any], projects: list[Project]) -> str:
    """Render a portfolio summary as Markdown."""
    rag_emoji = {"Green": "🟢", "Amber": "🟡", "Red": "🔴", "Unknown": "⚪"}
    dist = summary.get("rag_distribution", {})

    lines = [
        "# Portfolio Health Summary",
        "",
        f"**Report Date:** {summary.get('report_date', 'N/A')}  ",
        f"**Total Projects:** {summary.get('total_projects', 0)}  ",
        f"**Health Signal:** {summary.get('health_signal', 'N/A')}  ",
        f"**Avg Composite Score:** {summary.get('avg_composite_score', 'N/A')} / 1.000",
        "",
        "## RAG Distribution",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for rag, count in dist.items():
        lines.append(f"| {rag_emoji.get(rag, '⚪')} {rag} | {count} |")

    lines += ["", "## Project Snapshots", ""]
    for p in projects:
        emoji = rag_emoji.get(p.rag_status or "Unknown", "⚪")
        conf_line = (
            f"- **RAG:** {p.rag_status or 'Unknown'} (confidence: {p.rag_confidence * 100:.0f}%)"
            if p.rag_confidence is not None
            else f"- **RAG:** {p.rag_status or 'Unknown'}"
        )
        lines += [
            f"### {emoji} {p.name}",
            "",
            conf_line,
            f"- **Completion:** {p.completion_percent or 'N/A'}%",
            f"- **Summary:** {p.executive_summary or 'N/A'}",
            "",
        ]

    if summary.get("emerging_risks"):
        lines += ["## Emerging Risks Across Portfolio", ""]
        lines += [f"- {r}" for r in summary["emerging_risks"]]
        lines += [""]

    return "\n".join(lines)


def generate_and_save_portfolio(
    projects: list[Project],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    """Generate portfolio_summary.md and portfolio_summary.json, save both.

    Returns (portfolio_path, summary_dict).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary = compute_portfolio_summary(projects)

    portfolio_md = render_portfolio_markdown(summary, projects)
    portfolio_path = out / "portfolio_summary.md"
    portfolio_path.write_text(portfolio_md, encoding="utf-8")

    portfolio_json_path = out / "portfolio_summary.json"
    portfolio_json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    logger.info("Portfolio summary saved to %s", out)
    return portfolio_path, summary
