"""SQLite-backed stores for plans and generation jobs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

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
    """SQLite-backed store for play plans."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                plan_id   TEXT PRIMARY KEY,
                user_input TEXT NOT NULL,
                brief      TEXT NOT NULL,
                plan       TEXT NOT NULL,
                approved   INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def save(self, record: PlanRecord) -> None:
        """Persist a plan record, replacing any existing row with the same plan_id."""
        self._conn.execute(
            "INSERT OR REPLACE INTO plans (plan_id, user_input, brief, plan, approved) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record.plan.plan_id,
                record.user_input.model_dump_json(),
                record.brief.model_dump_json(),
                record.plan.model_dump_json(),
                int(record.approved),
            ),
        )
        self._conn.commit()

    def get(self, plan_id: str) -> Optional[PlanRecord]:
        """Retrieve a plan record by identifier."""
        cursor = self._conn.execute(
            "SELECT user_input, brief, plan, approved FROM plans WHERE plan_id = ?",
            (plan_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return PlanRecord(
            user_input=UserPlayInput.model_validate_json(row[0]),
            brief=PlayDesignBrief.model_validate_json(row[1]),
            plan=PlayPlan.model_validate_json(row[2]),
            approved=bool(row[3]),
        )

    def approve(self, plan_id: str) -> PlanRecord:
        """Mark a plan as approved and return the updated record."""
        self._conn.execute(
            "UPDATE plans SET approved = 1 WHERE plan_id = ?",
            (plan_id,),
        )
        self._conn.commit()
        record = self.get(plan_id)
        assert record is not None
        return record


class JobStore:
    """SQLite-backed store for generation jobs."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id       TEXT PRIMARY KEY,
                plan_id      TEXT NOT NULL,
                status       TEXT NOT NULL,
                output_lines TEXT NOT NULL DEFAULT '[]',
                markdown     TEXT NOT NULL DEFAULT '',
                play_json    TEXT NOT NULL DEFAULT '{}',
                updated_at   TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(self, record: GenerationRecord) -> None:
        """Persist a generation record, replacing any existing row with the same job_id."""
        self._conn.execute(
            "INSERT OR REPLACE INTO jobs "
            "(job_id, plan_id, status, output_lines, markdown, play_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.job_id,
                record.plan_id,
                record.status,
                json.dumps(record.output_lines),
                record.markdown,
                json.dumps(record.play_json),
                record.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, job_id: str) -> Optional[GenerationRecord]:
        """Retrieve a generation record by identifier."""
        cursor = self._conn.execute(
            "SELECT job_id, plan_id, status, output_lines, markdown, play_json, updated_at "
            "FROM jobs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return GenerationRecord(
            job_id=row[0],
            plan_id=row[1],
            status=row[2],
            output_lines=json.loads(row[3]),
            markdown=row[4],
            play_json=json.loads(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
        )
