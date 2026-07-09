"""Data models for the AI Project Health Reporting System."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Task:

    name: str
    status: Optional[str] = None
    baseline_start: Optional[date] = None
    baseline_finish: Optional[date] = None
    actual_start: Optional[date] = None
    actual_finish: Optional[date] = None
    planned_finish: Optional[date] = None
    percent_complete: Optional[float] = None
    variance_days: Optional[float] = None
    float_days: Optional[float] = None
    is_milestone: bool = False
    is_critical: bool = False
    dependencies: list[str] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def is_delayed(self) -> bool:
        """Return True if the task is behind schedule."""
        if self.variance_days is not None:
            return self.variance_days > 0
        if self.planned_finish and self.actual_finish:
            return self.actual_finish > self.planned_finish
        return False

    @property
    def is_complete(self) -> bool:
        """Return True if the task is 100% complete."""
        if self.percent_complete is not None:
            return self.percent_complete >= 100
        return self.status in {"complete", "done", "finished", "closed"} if self.status else False


@dataclass
class Risk:
    """Represents a project risk or issue."""

    description: str
    severity: Optional[str] = None  # High / Medium / Low
    probability: Optional[str] = None
    impact: Optional[str] = None
    mitigation: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None


@dataclass
class Project:
    """Normalized representation of a project plan workbook."""

    name: str
    source_file: str
    pm: Optional[str] = None
    start: Optional[date] = None
    finish: Optional[date] = None
    tasks: list[Task] = field(default_factory=list)
    milestones: list[Task] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    # Computed / derived fields populated by the RAG engine
    rag_status: Optional[str] = None          # Red / Amber / Green
    rag_confidence: Optional[float] = None    # 0.0 – 1.0
    rule_rag: Optional[str] = None            # Deterministic rule result
    gemini_rag: Optional[str] = None          # Gemini's own opinion (transparency only, never authoritative)
    gemini_agrees: Optional[bool] = None      # Whether Gemini's opinion matches the rule-engine RAG
    executive_summary: Optional[str] = None
    reasoning: Optional[str] = None
    identified_risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    next_week_priorities: list[str] = field(default_factory=list)

    # Computed metrics (filled by RAG engine)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tasks(self) -> int:
        return len(self.tasks)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.is_complete)

    @property
    def delayed_tasks(self) -> int:
        return sum(1 for t in self.tasks if t.is_delayed)

    @property
    def critical_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.is_critical]

    @property
    def overdue_milestones(self) -> list[Task]:
        return [m for m in self.milestones if m.is_delayed and not m.is_complete]

    @property
    def completion_percent(self) -> Optional[float]:
        values = [t.percent_complete for t in self.tasks if t.percent_complete is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 1)
