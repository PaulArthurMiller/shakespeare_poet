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
    # Serialized IntegrityReport (see validation/quote_integrity.py). Empty for
    # runs recorded before quote integrity was validated -- an empty dict means
    # "not checked", which is not the same as "passed".
    quote_integrity: dict = field(default_factory=dict)


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


@dataclass
class LineMarkRecord:
    """Stored review mark for a generated line."""

    job_id: str
    line_index: int
    note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AdminConfigRecord:
    """Stored runtime configuration edited from the admin page."""

    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.2
    beam_width: int = 3
    max_length: int = 3
    checkpoint_interval: int = 2
    use_critic: bool = True
    use_chooser: bool = False
    anchor_pressure: float = 1.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobStore:
    """SQLite-backed store for generation jobs."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id          TEXT PRIMARY KEY,
                plan_id         TEXT NOT NULL,
                status          TEXT NOT NULL,
                output_lines    TEXT NOT NULL DEFAULT '[]',
                markdown        TEXT NOT NULL DEFAULT '',
                play_json       TEXT NOT NULL DEFAULT '{}',
                updated_at      TEXT NOT NULL,
                quote_integrity TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        # CREATE TABLE IF NOT EXISTS does nothing to a database created before
        # this column existed, so existing job stores are migrated explicitly.
        self._add_missing_column("jobs", "quote_integrity", "TEXT NOT NULL DEFAULT '{}'")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS line_marks (
                job_id     TEXT NOT NULL,
                line_index INTEGER NOT NULL,
                note       TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                PRIMARY KEY (job_id, line_index)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_config (
                config_id           TEXT PRIMARY KEY,
                model               TEXT NOT NULL,
                temperature         REAL NOT NULL,
                beam_width          INTEGER NOT NULL,
                max_length          INTEGER NOT NULL,
                checkpoint_interval INTEGER NOT NULL,
                use_critic          INTEGER NOT NULL,
                use_chooser         INTEGER NOT NULL,
                anchor_pressure     REAL NOT NULL,
                updated_at          TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _add_missing_column(self, table: str, column: str, definition: str) -> None:
        """Add a column to an existing table when a prior schema version lacks it."""
        cursor = self._conn.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column in existing:
            return
        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        self._conn.commit()

    def save(self, record: GenerationRecord) -> None:
        """Persist a generation record, replacing any existing row with the same job_id."""
        self._conn.execute(
            "INSERT OR REPLACE INTO jobs "
            "(job_id, plan_id, status, output_lines, markdown, play_json, updated_at, "
            "quote_integrity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.job_id,
                record.plan_id,
                record.status,
                json.dumps(record.output_lines),
                record.markdown,
                json.dumps(record.play_json),
                record.updated_at.isoformat(),
                json.dumps(record.quote_integrity),
            ),
        )
        self._conn.commit()

    def _record_from_row(self, row: tuple) -> GenerationRecord:
        """Build a GenerationRecord from a jobs row in the canonical column order."""
        return GenerationRecord(
            job_id=row[0],
            plan_id=row[1],
            status=row[2],
            output_lines=json.loads(row[3]),
            markdown=row[4],
            play_json=json.loads(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            quote_integrity=json.loads(row[7] or "{}"),
        )

    def get(self, job_id: str) -> Optional[GenerationRecord]:
        """Retrieve a generation record by identifier."""
        cursor = self._conn.execute(
            "SELECT job_id, plan_id, status, output_lines, markdown, play_json, updated_at, "
            "quote_integrity FROM jobs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._record_from_row(row)


    def list_recent(self, limit: int = 50) -> List[GenerationRecord]:
        """Return recent generation jobs for the composer library."""
        cursor = self._conn.execute(
            "SELECT job_id, plan_id, status, output_lines, markdown, play_json, updated_at, "
            "quote_integrity FROM jobs ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        return [self._record_from_row(row) for row in cursor.fetchall()]

    def save_line_mark(self, mark: LineMarkRecord) -> None:
        """Persist or update a review mark for one generated line."""
        self._conn.execute(
            "INSERT OR REPLACE INTO line_marks (job_id, line_index, note, created_at) "
            "VALUES (?, ?, ?, ?)",
            (mark.job_id, mark.line_index, mark.note, mark.created_at.isoformat()),
        )
        self._conn.commit()

    def delete_line_mark(self, job_id: str, line_index: int) -> None:
        """Remove a review mark for one generated line."""
        self._conn.execute(
            "DELETE FROM line_marks WHERE job_id = ? AND line_index = ?",
            (job_id, line_index),
        )
        self._conn.commit()

    def list_line_marks(self, job_id: str) -> List[LineMarkRecord]:
        """Return all review marks associated with a generation job."""
        cursor = self._conn.execute(
            "SELECT job_id, line_index, note, created_at FROM line_marks "
            "WHERE job_id = ? ORDER BY line_index",
            (job_id,),
        )
        return [
            LineMarkRecord(
                job_id=row[0],
                line_index=row[1],
                note=row[2],
                created_at=datetime.fromisoformat(row[3]),
            )
            for row in cursor.fetchall()
        ]

    def get_admin_config(self) -> AdminConfigRecord:
        """Return the saved admin configuration or defaults."""
        cursor = self._conn.execute(
            "SELECT model, temperature, beam_width, max_length, checkpoint_interval, "
            "use_critic, use_chooser, anchor_pressure, updated_at "
            "FROM admin_config WHERE config_id = 'default'"
        )
        row = cursor.fetchone()
        if row is None:
            return AdminConfigRecord()
        return AdminConfigRecord(
            model=row[0],
            temperature=row[1],
            beam_width=row[2],
            max_length=row[3],
            checkpoint_interval=row[4],
            use_critic=bool(row[5]),
            use_chooser=bool(row[6]),
            anchor_pressure=row[7],
            updated_at=datetime.fromisoformat(row[8]),
        )

    def save_admin_config(self, config: AdminConfigRecord) -> AdminConfigRecord:
        """Persist admin configuration edited through the frontend."""
        updated = AdminConfigRecord(
            model=config.model,
            temperature=config.temperature,
            beam_width=config.beam_width,
            max_length=config.max_length,
            checkpoint_interval=config.checkpoint_interval,
            use_critic=config.use_critic,
            use_chooser=config.use_chooser,
            anchor_pressure=config.anchor_pressure,
            updated_at=datetime.now(timezone.utc),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO admin_config "
            "(config_id, model, temperature, beam_width, max_length, checkpoint_interval, "
            "use_critic, use_chooser, anchor_pressure, updated_at) "
            "VALUES ('default', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                updated.model,
                updated.temperature,
                updated.beam_width,
                updated.max_length,
                updated.checkpoint_interval,
                int(updated.use_critic),
                int(updated.use_chooser),
                updated.anchor_pressure,
                updated.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return updated
