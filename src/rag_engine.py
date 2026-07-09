"""Hybrid RAG scoring engine.

Phase 1 — Rule engine: deterministic scoring on structured metrics.
Phase 2 — Gemini reasoning: final RAG with confidence, narrative, and recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.models import Project

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

WEIGHTS = {
    "schedule":    0.25,
    "milestones":  0.20,
    "completion":  0.20,
    "risks":       0.15,
    "blockers":    0.10,
    "data_quality": 0.10,
}

GREEN_THRESHOLD = 0.70
AMBER_THRESHOLD = 0.40


# ── Metric computation ────────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    """Score for a single RAG dimension."""

    name: str
    raw_score: float         # 0.0 (red) – 1.0 (green)
    weight: float
    rationale: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        return self.raw_score * self.weight


def _schedule_score(project: Project) -> DimensionScore:
    """Score based on schedule variance and delayed tasks."""
    tasks = project.tasks
    if not tasks:
        return DimensionScore("schedule", 0.5, WEIGHTS["schedule"], "No task data available", {"missing": True})

    delayed = project.delayed_tasks
    total = project.total_tasks

    # Average variance days (positive = late)
    variances = [t.variance_days for t in tasks if t.variance_days is not None]
    avg_variance = sum(variances) / len(variances) if variances else 0.0

    delay_ratio = delayed / total if total else 0.0

    # Score: penalise delay ratio and avg variance
    score = 1.0
    score -= delay_ratio * 0.5
    if avg_variance > 0:
        score -= min(avg_variance / 30.0, 0.5)  # up to -0.5 for 30+ days late

    score = max(0.0, min(1.0, score))
    rationale = (
        f"{delayed}/{total} tasks delayed; avg schedule variance {avg_variance:+.1f} days"
        if variances else
        f"{delayed}/{total} tasks delayed (no variance data)"
    )
    return DimensionScore(
        "schedule", score, WEIGHTS["schedule"], rationale,
        {"delayed_tasks": delayed, "total_tasks": total, "avg_variance_days": round(avg_variance, 1)},
    )


def _milestone_score(project: Project) -> DimensionScore:
    """Score based on milestone completion and delays."""
    milestones = project.milestones
    if not milestones:
        return DimensionScore("milestones", 0.6, WEIGHTS["milestones"], "No milestone data", {"missing": True})

    overdue = len(project.overdue_milestones)
    total = len(milestones)
    ratio = overdue / total if total else 0.0
    score = max(0.0, 1.0 - ratio * 1.2)  # More weight on missed milestones
    score = min(1.0, score)
    return DimensionScore(
        "milestones", score, WEIGHTS["milestones"],
        f"{overdue}/{total} milestones overdue",
        {"overdue_milestones": overdue, "total_milestones": total},
    )


def _completion_score(project: Project) -> DimensionScore:
    """Score based on overall completion percentage."""
    pct = project.completion_percent
    if pct is None:
        return DimensionScore("completion", 0.5, WEIGHTS["completion"], "No completion data", {"missing": True})

    # Normalise 0-100 → 0-1
    score = pct / 100.0
    return DimensionScore(
        "completion", score, WEIGHTS["completion"],
        f"Overall completion: {pct:.1f}%",
        {"completion_percent": pct},
    )


def _risk_score(project: Project) -> DimensionScore:
    """Score based on open risks and their severity."""
    risks = project.risks
    if not risks:
        return DimensionScore("risks", 0.8, WEIGHTS["risks"], "No risk register found", {"missing": True})

    severity_map = {"high": 1.0, "critical": 1.0, "medium": 0.5, "low": 0.2}
    _CLOSED_STATUSES = {"closed", "resolved", "done", "complete", "completed", "fixed"}
    open_risks = [r for r in risks if (r.status or "").lower() not in _CLOSED_STATUSES]

    high_risks = sum(1 for r in open_risks if (r.severity or "").lower() in {"high", "critical"})
    medium_risks = sum(1 for r in open_risks if (r.severity or "").lower() == "medium")

    # Penalty per high risk; lighter for medium
    penalty = min(1.0, high_risks * 0.25 + medium_risks * 0.10)
    score = max(0.0, 1.0 - penalty)
    return DimensionScore(
        "risks", score, WEIGHTS["risks"],
        f"{len(open_risks)} open risks ({high_risks} high/critical, {medium_risks} medium)",
        {"open_risks": len(open_risks), "high_risks": high_risks, "medium_risks": medium_risks},
    )


def _blocker_score(project: Project) -> DimensionScore:
    """Score based on critical path tasks that are blocked/delayed."""
    critical = project.critical_tasks
    if not critical:
        return DimensionScore("blockers", 0.7, WEIGHTS["blockers"], "No critical path identified", {"missing": True})

    blocked = [t for t in critical if t.is_delayed and not t.is_complete]
    ratio = len(blocked) / len(critical)
    score = max(0.0, 1.0 - ratio)
    return DimensionScore(
        "blockers", score, WEIGHTS["blockers"],
        f"{len(blocked)}/{len(critical)} critical path tasks delayed",
        {"blocked_critical_tasks": len(blocked), "total_critical_tasks": len(critical)},
    )


def _data_quality_score(project: Project) -> DimensionScore:
    """Penalise missing data that limits analysis confidence."""
    missing: list[str] = []
    if not project.tasks:
        missing.append("task list")
    if not project.milestones:
        missing.append("milestones")
    if not project.risks:
        missing.append("risk register")
    if project.completion_percent is None:
        missing.append("completion % data")
    all_vars = [t.variance_days for t in project.tasks if t.variance_days is not None]
    if not all_vars and project.tasks:
        missing.append("schedule variance data")

    score = max(0.0, 1.0 - len(missing) * 0.18)
    rationale = f"Missing: {', '.join(missing)}" if missing else "Data quality good"
    return DimensionScore(
        "data_quality", score, WEIGHTS["data_quality"], rationale,
        {"missing_fields": missing},
    )


# ── Rule engine ───────────────────────────────────────────────────────────────

def compute_rule_rag(project: Project) -> tuple[str, float, list[DimensionScore]]:
    """Return (rag_status, composite_score, dimension_scores) from rule engine."""
    dimensions = [
        _schedule_score(project),
        _milestone_score(project),
        _completion_score(project),
        _risk_score(project),
        _blocker_score(project),
        _data_quality_score(project),
    ]

    composite = sum(d.weighted_score for d in dimensions)

    if composite >= GREEN_THRESHOLD:
        rag = "Green"
    elif composite >= AMBER_THRESHOLD:
        rag = "Amber"
    else:
        rag = "Red"

    return rag, composite, dimensions


def build_metrics_dict(project: Project, dimensions: list[DimensionScore], composite: float) -> dict:
    """Assemble the metrics dict stored on the Project."""
    return {
        "composite_score": round(composite, 3),
        "completion_percent": project.completion_percent,
        "total_tasks": project.total_tasks,
        "completed_tasks": project.completed_tasks,
        "delayed_tasks": project.delayed_tasks,
        "total_milestones": len(project.milestones),
        "overdue_milestones": len(project.overdue_milestones),
        "open_risks": len([r for r in project.risks if (r.status or "").lower() not in {"closed", "resolved", "done", "complete", "completed", "fixed"}]),
        "critical_tasks": len(project.critical_tasks),
        "comments_count": len(project.comments),
        "dimensions": {d.name: {"score": round(d.raw_score, 3), "rationale": d.rationale, **d.details}
                       for d in dimensions},
        "thresholds": {"green": GREEN_THRESHOLD, "amber": AMBER_THRESHOLD},
        "weights": WEIGHTS,
    }


def build_gemini_prompt(project: Project, dimensions: list[DimensionScore], composite: float,
                         rule_rag: str) -> str:
    """Build the structured prompt sent to Gemini for final RAG reasoning."""
    dim_text = "\n".join(
        f"  - {d.name.upper()} (weight {d.weight:.0%}): score={d.raw_score:.2f} — {d.rationale}"
        for d in dimensions
    )

    comments_text = (
        "\n".join(f"  • {c}" for c in project.comments[:10])
        if project.comments else "  (none provided)"
    )

    high_risks = [r for r in project.risks if (r.severity or "").lower() in {"high", "critical"}]
    risk_text = (
        "\n".join(f"  • [{r.severity}] {r.description}" for r in high_risks[:5])
        if high_risks else "  (none identified)"
    )

    critical_delayed = [t for t in project.critical_tasks if t.is_delayed and not t.is_complete]
    blocker_text = (
        "\n".join(f"  • {t.name} (variance: {t.variance_days:+.0f}d)" if t.variance_days else f"  • {t.name}"
                  for t in critical_delayed[:5])
        if critical_delayed else "  (none)"
    )

    return f"""You are an expert PMO analyst. Evaluate the project health below and return a structured JSON response.

PROJECT: {project.name}
PM: {project.pm or "Unknown"}
Rule-engine RAG: {rule_rag} (composite score: {composite:.3f} / 1.000)

DIMENSION SCORES:
{dim_text}

HIGH/CRITICAL RISKS:
{risk_text}

CRITICAL PATH BLOCKERS:
{blocker_text}

STAKEHOLDER COMMENTS:
{comments_text}

MISSING DATA:
{', '.join(project.metrics.get('dimensions', {}).get('data_quality', {}).get('missing_fields', [])) or 'None'}

INSTRUCTIONS:
1. Review all metrics holistically.
2. The rule-engine RAG above is FINAL and authoritative — it will be used as the official
   status regardless of your answer. Your "final_rag" is only your own advisory opinion for
   transparency; if it differs from the rule-engine RAG, briefly justify why in "reasoning",
   but do not expect it to change the displayed status.
3. Return ONLY valid JSON with this exact schema:
{{
  "final_rag": "Green" | "Amber" | "Red",
  "confidence": <float 0.0-1.0>,
  "executive_summary": "<2-3 sentences>",
  "reasoning": "<plain-English explanation, 3-5 sentences>",
  "risks": ["<risk 1>", "<risk 2>", ...],
  "recommendations": ["<action 1>", "<action 2>", ...],
  "missing_data": ["<item 1>", ...],
  "next_week_priorities": ["<priority 1>", "<priority 2>", ...]
}}
Return JSON only. No markdown fences. No commentary outside the JSON."""
