"""In-memory stores for plans and generation jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from shpoet.common.types import PlayDesignBrief, PlayPlan, UserPlayInput


@dataclass
class PlanRecord:
    """Stored record for a generated play plan."""

    user_input: UserPlayInput
    brief: PlayDesignBrief
    plan: PlayPlan
    approved: bool = False


@dataclass
class GenerationRecord:
    """Stored record for a generation job."""

    job_id: str
    plan_id: str
    status: str
    output_lines: List[str] = field(default_factory=list)
    markdown: str = ""
    play_json: dict = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PlanStore:
    """Simple in-memory store for play plans."""

    def __init__(self) -> None:
        """Initialize an empty plan store."""

        self._plans: Dict[str, PlanRecord] = {}

    def save(self, record: PlanRecord) -> None:
        """Save a plan record to the store."""

        self._plans[record.plan.plan_id] = record

    def get(self, plan_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan record by identifier."""

        return self._plans.get(plan_id)

    def approve(self, plan_id: str) -> PlanRecord:
        """Mark a plan as approved and return the updated record."""

        record = self._plans[plan_id]
        record.approved = True
        return record


class JobStore:
    """Simple in-memory store for generation jobs."""

    def __init__(self) -> None:
        """Initialize an empty job store."""

        self._jobs: Dict[str, GenerationRecord] = {}

    def save(self, record: GenerationRecord) -> None:
        """Save a generation record to the store."""

        self._jobs[record.job_id] = record

    def get(self, job_id: str) -> Optional[GenerationRecord]:
        """Retrieve a generation record by identifier."""

        return self._jobs.get(job_id)
