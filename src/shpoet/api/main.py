"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException

from shpoet.api.models import (
    ExportResponse,
    GenerateRequest,
    GenerateResponse,
    GenerateStatusResponse,
    PlanApprovalRequest,
    PlanApprovalResponse,
    PlanRequest,
    PlanResponse,
)
from shpoet.api.services import approve_plan, create_plan, generate_play
from shpoet.api.state import JobStore, PlanStore
from shpoet.micro.corpus_store import CorpusStore

from shpoet.config.settings import get_settings


logger = logging.getLogger(__name__)


def configure_logging(config_path: Path) -> None:
    """Configure logging using a YAML configuration file."""

    if not config_path.exists():
        logging.basicConfig(level=logging.INFO)
        logger.warning("Logging config not found at %s; using basicConfig", config_path)
        return

    with config_path.open("r", encoding="utf-8") as file_handle:
        config_data: dict[str, Any] = yaml.safe_load(file_handle)

    logging.config.dictConfig(config_data)


def create_app() -> FastAPI:
    """Create the FastAPI application with configured routes."""

    settings = get_settings()
    configure_logging(settings.log_config_path)

    app = FastAPI(title=settings.app_name)
    app.state.plan_store = PlanStore()
    app.state.job_store = JobStore()
    app.state.corpus_store = CorpusStore(settings.processed_dir)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        """Return a simple health check payload."""

        return {"status": "ok"}

    @app.post("/plan", response_model=PlanResponse)
    def plan_endpoint(payload: PlanRequest) -> PlanResponse:
        """Generate a play plan from user input."""

        logger.info("Request %s creating plan", payload.request_id)
        record = create_plan(payload.user_input, app.state.plan_store)
        return PlanResponse(
            request_id=payload.request_id,
            plan_id=record.plan.plan_id,
            brief=record.brief,
            plan=record.plan,
        )

    @app.post("/plan/{plan_id}/approve", response_model=PlanApprovalResponse)
    def approve_plan_endpoint(plan_id: str, payload: PlanApprovalRequest) -> PlanApprovalResponse:
        """Approve or regenerate a previously generated plan."""

        logger.info("Request %s approving plan %s", payload.request_id, plan_id)
        if not payload.approve:
            raise HTTPException(status_code=400, detail="Plan approval rejected by request")
        try:
            record = approve_plan(plan_id, app.state.plan_store, payload.regenerate)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return PlanApprovalResponse(
            request_id=payload.request_id,
            plan_id=record.plan.plan_id,
            approved=record.approved,
            brief=record.brief,
            plan=record.plan,
        )

    @app.post("/generate", response_model=GenerateResponse)
    def generate_endpoint(payload: GenerateRequest) -> GenerateResponse:
        """Start a generation job for an approved plan."""

        logger.info("Request %s generating plan %s", payload.request_id, payload.plan_id)
        try:
            record = generate_play(
                payload.plan_id,
                app.state.plan_store,
                app.state.job_store,
                app.state.corpus_store,
                payload.config,
            )
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return GenerateResponse(
            request_id=payload.request_id,
            job_id=record.job_id,
            plan_id=record.plan_id,
            status=record.status,
            output_lines=record.output_lines,
        )

    @app.get("/generate/{job_id}", response_model=GenerateStatusResponse)
    def generate_status(job_id: str, request_id: str | None = None) -> GenerateStatusResponse:
        """Return status for a generation job."""

        logger.info("Request %s fetching job %s", request_id, job_id)
        record = app.state.job_store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return GenerateStatusResponse(
            request_id=request_id,
            job_id=record.job_id,
            plan_id=record.plan_id,
            status=record.status,
            output_lines=record.output_lines,
            updated_at=record.updated_at,
        )

    @app.get("/export/{job_id}", response_model=ExportResponse)
    def export_job(job_id: str, request_id: str | None = None) -> ExportResponse:
        """Export a generated play in markdown and JSON formats."""

        logger.info("Request %s exporting job %s", request_id, job_id)
        record = app.state.job_store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return ExportResponse(
            request_id=request_id,
            job_id=record.job_id,
            plan_id=record.plan_id,
            markdown=record.markdown,
            play_json=record.play_json,
        )

    return app


app = create_app()
