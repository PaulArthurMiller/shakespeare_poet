"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shpoet.api.models import (
    AdminConfig,
    ExportResponse,
    GenerateRequest,
    GenerateResponse,
    GenerateStatusResponse,
    GenerationLibraryResponse,
    GenerationSummary,
    LineMark,
    LineMarksResponse,
    PlanApprovalRequest,
    PlanApprovalResponse,
    PlanRequest,
    PlanResponse,
)
from shpoet.api.services import approve_plan, create_plan, generate_play
from shpoet.api.state import AdminConfigRecord, JobStore, LineMarkRecord, PlanStore
from shpoet.llm.factory import create_critic_and_chooser, create_llm_client
from shpoet.micro.candidate_pool import CandidatePool
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


def _build_candidate_pool(settings: Any) -> CandidatePool | None:
    """Open the retrieval pool, or return None to fall back to the full corpus.

    Startup must survive a missing or unbuilt index -- a fresh clone has no
    Chroma directory, and the API should still serve /health and the planning
    endpoints rather than crash on import.
    """

    if settings.retrieval_pool_size <= 0:
        logger.warning("Retrieval disabled (SHPOET_RETRIEVAL_POOL_SIZE=0); using full corpus")
        return None

    try:
        pool = CandidatePool(
            persist_dir=settings.chroma_dir,
            embedding_dimensions=settings.embedding_dimensions,
            pool_size=settings.retrieval_pool_size,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.warning(
            "Candidate retrieval unavailable (%s); falling back to the full processed corpus. "
            "Run `python -m shpoet.scripts.build_index` to enable retrieval.",
            exc,
        )
        return None

    logger.info("Candidate retrieval enabled from %s", settings.chroma_dir)
    return pool


def create_app() -> FastAPI:
    """Create the FastAPI application with configured routes."""

    settings = get_settings()
    configure_logging(settings.log_config_path)

    app = FastAPI(title=settings.app_name)
    app.state.plan_store = PlanStore(settings.db_path)
    app.state.job_store = JobStore(settings.db_path)
    app.state.corpus_store = CorpusStore(settings.processed_dir)
    app.state.candidate_pool = _build_candidate_pool(settings)

    llm_client = create_llm_client(settings.anthropic_api_key, settings.llm_model)
    app.state.critic, app.state.chooser = create_critic_and_chooser(
        llm_client, use_chooser=settings.use_chooser
    )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def frontend_home() -> FileResponse:
        """Serve the play setup page as the frontend entry point."""

        return FileResponse(static_dir / "index.html")

    @app.get("/composer", include_in_schema=False)
    def composer_page() -> FileResponse:
        """Serve the composition viewer page."""

        return FileResponse(static_dir / "composer.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page() -> FileResponse:
        """Serve the admin configuration page."""

        return FileResponse(static_dir / "admin.html")

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
                output_dir=settings.output_dir,
                critic=app.state.critic,
                chooser=app.state.chooser,
                candidate_pool=app.state.candidate_pool,
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



    @app.get("/generations", response_model=GenerationLibraryResponse)
    def list_generations(limit: int = 50) -> GenerationLibraryResponse:
        """Return saved generations for the composer file picker."""

        records = app.state.job_store.list_recent(limit)
        summaries: list[GenerationSummary] = []
        for record in records:
            title = str(record.play_json.get("title") or record.job_id)
            summaries.append(
                GenerationSummary(
                    job_id=record.job_id,
                    plan_id=record.plan_id,
                    status=record.status,
                    line_count=len(record.output_lines),
                    title=title,
                    file_name=f"{record.job_id}.json",
                    updated_at=record.updated_at,
                )
            )
        return GenerationLibraryResponse(generations=summaries)

    @app.get("/generate/{job_id}/marks", response_model=LineMarksResponse)
    def get_line_marks(job_id: str) -> LineMarksResponse:
        """Return saved review marks for a generated play."""

        if app.state.job_store.get(job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        marks = [
            LineMark(line_index=mark.line_index, note=mark.note, created_at=mark.created_at)
            for mark in app.state.job_store.list_line_marks(job_id)
        ]
        return LineMarksResponse(job_id=job_id, marks=marks)

    @app.put("/generate/{job_id}/marks", response_model=LineMarksResponse)
    def save_line_mark(job_id: str, payload: LineMark) -> LineMarksResponse:
        """Create or update a review mark for a generated line."""

        record = app.state.job_store.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if payload.line_index >= len(record.output_lines):
            raise HTTPException(status_code=400, detail="Line index is outside generated output")
        app.state.job_store.save_line_mark(
            LineMarkRecord(job_id=job_id, line_index=payload.line_index, note=payload.note)
        )
        return get_line_marks(job_id)

    @app.delete("/generate/{job_id}/marks/{line_index}", response_model=LineMarksResponse)
    def delete_line_mark(job_id: str, line_index: int) -> LineMarksResponse:
        """Delete a review mark from a generated line."""

        if app.state.job_store.get(job_id) is None:
            raise HTTPException(status_code=404, detail="Job not found")
        app.state.job_store.delete_line_mark(job_id, line_index)
        return get_line_marks(job_id)

    @app.get("/admin/config", response_model=AdminConfig)
    def get_admin_config() -> AdminConfig:
        """Return saved model and search configuration."""

        config = app.state.job_store.get_admin_config()
        return AdminConfig(**config.__dict__)

    @app.put("/admin/config", response_model=AdminConfig)
    def save_admin_config(payload: AdminConfig) -> AdminConfig:
        """Persist model and search configuration from the admin page."""

        config = app.state.job_store.save_admin_config(AdminConfigRecord(**payload.model_dump(exclude={"updated_at"})))
        return AdminConfig(**config.__dict__)

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
