"""Typed data contracts shared across Shakespearean Poet modules."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CharacterInput(BaseModel):
    """User-provided character definition used during planning."""

    name: str = Field(..., description="Display name for the character.")
    description: str = Field(..., description="Character summary and intent notes.")
    voice_traits: List[str] = Field(default_factory=list, description="Voice traits or diction notes.")


class SceneInput(BaseModel):
    """User-provided scene description for planning."""

    act: int = Field(..., description="Act number for the scene.")
    scene: int = Field(..., description="Scene number within the act.")
    setting: str = Field(..., description="Setting description for the scene.")
    summary: str = Field(..., description="High-level intent and situation.")
    participants: List[str] = Field(default_factory=list, description="Character names participating.")


class UserPlayInput(BaseModel):
    """User request payload used to seed planning artifacts."""

    title: str = Field(..., description="Working title for the play.")
    overview: str = Field(..., description="Narrative overview and emotional arc.")
    characters: List[CharacterInput] = Field(default_factory=list)
    scenes: List[SceneInput] = Field(default_factory=list)


class BeatObligation(BaseModel):
    """Anchor obligations tied to a specific beat in the plan."""

    beat_id: str = Field(..., description="Identifier for the beat.")
    required_anchors: List[str] = Field(default_factory=list, description="Anchors that must appear.")
    desired_anchors: List[str] = Field(default_factory=list, description="Anchors that are preferred.")


class AnchorPlan(BaseModel):
    """Anchor definition with recurrence and placement guidance."""

    anchor_term: str = Field(..., description="Primary lexical anchor term.")
    related_terms: List[str] = Field(default_factory=list, description="Related lexical family.")
    recurrence_rules: List[str] = Field(default_factory=list, description="Human-readable recurrence guidance.")
    placements: List[str] = Field(default_factory=list, description="Suggested beat placements.")


class AnchorRegistry(BaseModel):
    """Registry of anchors and their recurrence strategies."""

    primary_anchor: Optional[str] = Field(default=None, description="Primary anchor for the play.")
    anchors: List[AnchorPlan] = Field(default_factory=list)


class BeatPlan(BaseModel):
    """Single beat plan with expressive intent and obligations."""

    beat_id: str = Field(..., description="Unique beat identifier.")
    objective: str = Field(..., description="Expressive objective for the beat.")
    rhetorical_mode: str = Field(..., description="Primary rhetorical posture.")
    obligations: List[BeatObligation] = Field(default_factory=list)


class ScenePlan(BaseModel):
    """Planned scene structure containing beats."""

    scene_id: str = Field(..., description="Unique scene identifier.")
    act: int = Field(..., description="Act number for the scene.")
    scene: int = Field(..., description="Scene number within the act.")
    beats: List[BeatPlan] = Field(default_factory=list)


class ActPlan(BaseModel):
    """Planned act structure containing scenes."""

    act: int = Field(..., description="Act number.")
    scenes: List[ScenePlan] = Field(default_factory=list)


class PlayPlan(BaseModel):
    """Machine-readable plan output produced by the expander."""

    plan_id: str = Field(..., description="Unique plan identifier.")
    title: str = Field(..., description="Play title.")
    acts: List[ActPlan] = Field(default_factory=list)
    anchors: AnchorRegistry = Field(default_factory=AnchorRegistry)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlayDesignBrief(BaseModel):
    """User-friendly planning brief returned for approval."""

    plan_id: str = Field(..., description="Associated plan identifier.")
    markdown: str = Field(..., description="Rendered brief for user review.")
    anchors: AnchorRegistry = Field(default_factory=AnchorRegistry)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GuidanceProfile(BaseModel):
    """Runtime guidance emitted per beat for downstream modules."""

    beat_id: str = Field(..., description="Beat identifier for guidance.")
    anchor_targets: List[str] = Field(default_factory=list)
    constraints: Dict[str, float] = Field(default_factory=dict)
    priors: Dict[str, float] = Field(default_factory=dict)


class StateBundle(BaseModel):
    """Canonical runtime state snapshot used for signatures and guidance."""

    act: int = Field(..., description="Current act number.")
    scene: int = Field(..., description="Current scene number.")
    beat_id: str = Field(..., description="Current beat identifier.")
    speaker: Optional[str] = Field(default=None, description="Active speaker name.")
    characters_present: List[str] = Field(default_factory=list)
    anchors_seen: List[str] = Field(default_factory=list)


class CandidateScore(BaseModel):
    """Score breakdown for a candidate chunk or path."""

    candidate_id: str = Field(..., description="Candidate identifier.")
    total_score: float = Field(..., description="Aggregated score.")
    breakdown: Dict[str, float] = Field(default_factory=dict)


class CriticReport(BaseModel):
    """Structured critic evaluation report."""

    window_id: str = Field(..., description="Window identifier for critic report.")
    score: float = Field(..., description="Overall critic score.")
    notes: List[str] = Field(default_factory=list)
    recommendations: Dict[str, float] = Field(default_factory=dict)
