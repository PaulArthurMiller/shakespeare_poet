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
