"""API request/response models for plan and generation workflows."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from shpoet.common.types import PlayDesignBrief, PlayPlan, UserPlayInput


class PlanRequest(BaseModel):
    """Request payload for plan generation."""

    request_id: str = Field(..., description="Client-provided request identifier.")
    user_input: UserPlayInput = Field(..., description="User play input payload.")


class PlanResponse(BaseModel):
    """Response payload for plan generation."""

    request_id: str = Field(..., description="Echoed request identifier.")
    plan_id: str = Field(..., description="Generated plan identifier.")
    brief: PlayDesignBrief = Field(..., description="Rendered play design brief.")
    plan: PlayPlan = Field(..., description="Structured play plan JSON.")


class PlanApprovalRequest(BaseModel):
    """Request payload for approving or regenerating a plan."""

    request_id: str = Field(..., description="Client-provided request identifier.")
    approve: bool = Field(default=True, description="Flag indicating approval state.")
    regenerate: bool = Field(default=False, description="Whether to regenerate the plan before approval.")


class PlanApprovalResponse(BaseModel):
    """Response payload for plan approval."""

    request_id: str = Field(..., description="Echoed request identifier.")
    plan_id: str = Field(..., description="Approved plan identifier.")
    approved: bool = Field(..., description="Whether the plan is approved.")
    brief: PlayDesignBrief = Field(..., description="Updated play design brief.")
    plan: PlayPlan = Field(..., description="Updated play plan JSON.")


class GenerationConfig(BaseModel):
    """Configuration options for the generation job."""

    beam_width: int = Field(default=3, description="Beam width for search.")
    max_length: int = Field(default=3, description="Maximum lines per beat.")
    checkpoint_interval: int = Field(default=2, description="Checkpoint interval for critic calls.")
    use_critic: bool = Field(default=True, description="Enable LLM critic at checkpoints (requires ANTHROPIC_API_KEY).")
    use_chooser: bool = Field(default=False, description="Enable LLM chooser for tie-breaking (requires ANTHROPIC_API_KEY).")


class GenerateRequest(BaseModel):
    """Request payload to start a generation job."""

    request_id: str = Field(..., description="Client-provided request identifier.")
    plan_id: str = Field(..., description="Approved plan identifier.")
    config: GenerationConfig = Field(default_factory=GenerationConfig)


class GenerateResponse(BaseModel):
    """Response payload for starting a generation job."""

    request_id: str = Field(..., description="Echoed request identifier.")
    job_id: str = Field(..., description="Generation job identifier.")
    plan_id: str = Field(..., description="Associated plan identifier.")
    status: str = Field(..., description="Current generation status.")
    output_lines: List[str] = Field(default_factory=list)


class GenerateStatusResponse(BaseModel):
    """Response payload for checking generation status."""

    request_id: Optional[str] = Field(default=None, description="Optional request identifier.")
    job_id: str = Field(..., description="Generation job identifier.")
    plan_id: str = Field(..., description="Associated plan identifier.")
    status: str = Field(..., description="Current generation status.")
    output_lines: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(..., description="Last update timestamp.")


class ExportResponse(BaseModel):
    """Response payload for exporting a generated play."""

    request_id: Optional[str] = Field(default=None, description="Optional request identifier.")
    job_id: str = Field(..., description="Generation job identifier.")
    plan_id: str = Field(..., description="Associated plan identifier.")
    markdown: str = Field(..., description="Markdown export of the play.")
    play_json: dict = Field(..., description="JSON export of the play.")


class GenerationSummary(BaseModel):
    """Summary of a saved generation for the composer library."""

    job_id: str = Field(..., description="Generation job identifier.")
    plan_id: str = Field(..., description="Associated plan identifier.")
    status: str = Field(..., description="Generation status.")
    line_count: int = Field(..., description="Number of generated lines.")
    title: str = Field(default="Untitled generation", description="Best-effort generated title.")
    file_name: str = Field(..., description="Stable export-style file name.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class GenerationLibraryResponse(BaseModel):
    """Response containing saved generations for the composer picker."""

    generations: List[GenerationSummary] = Field(default_factory=list)


class LineMark(BaseModel):
    """Review mark attached to a generated line."""

    line_index: int = Field(..., ge=0, description="Zero-based generated line index.")
    note: str = Field(default="", description="Optional note explaining why the line is marked.")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp supplied by the server.")


class LineMarksResponse(BaseModel):
    """Response containing review marks for a generation."""

    job_id: str = Field(..., description="Generation job identifier.")
    marks: List[LineMark] = Field(default_factory=list)


class AdminConfig(BaseModel):
    """Editable frontend-facing generation and model configuration."""

    model: str = Field(default="claude-3-5-sonnet-20241022")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    beam_width: int = Field(default=3, ge=1, le=25)
    max_length: int = Field(default=3, ge=1, le=50)
    checkpoint_interval: int = Field(default=2, ge=1, le=50)
    use_critic: bool = Field(default=True)
    use_chooser: bool = Field(default=False)
    anchor_pressure: float = Field(default=1.0, ge=0.0, le=5.0)
    updated_at: Optional[datetime] = Field(default=None)
