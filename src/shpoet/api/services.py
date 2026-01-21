"""Service layer for plan approval and play generation."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from shpoet.common.types import PlayPlan, UserPlayInput
from shpoet.expander.expander import expand_play_input
from shpoet.macro.guidance import GuidanceEmitter
from shpoet.micro.corpus_store import CorpusStore
from shpoet.scoring.features_for_scoring import compute_anchor_hits
from shpoet.search.beam_search import BeamSearch

from shpoet.api.models import GenerationConfig
from shpoet.api.state import GenerationRecord, JobStore, PlanRecord, PlanStore


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedBeat:
    """Generated output for a single beat."""

    beat_id: str
    line_ids: List[str]
    lines: List[str]


@dataclass(frozen=True)
class GeneratedPlay:
    """Generated play output artifacts."""

    output_lines: List[str]
    beat_outputs: List[GeneratedBeat]
    markdown: str
    play_json: Dict[str, object]


def create_plan(user_input: UserPlayInput, plan_store: PlanStore) -> PlanRecord:
    """Expand user input into a plan and store it."""

    brief, plan = expand_play_input(user_input)
    record = PlanRecord(user_input=user_input, brief=brief, plan=plan, approved=False)
    plan_store.save(record)
    logger.info("Stored plan %s", plan.plan_id)
    return record


def approve_plan(
    plan_id: str,
    plan_store: PlanStore,
    regenerate: bool,
) -> PlanRecord:
    """Approve a plan, optionally regenerating it from stored user input."""

    record = plan_store.get(plan_id)
    if record is None:
        raise KeyError(f"Plan not found: {plan_id}")

    if regenerate:
        logger.info("Regenerating plan %s", plan_id)
        brief, plan = expand_play_input(record.user_input)
        record = PlanRecord(user_input=record.user_input, brief=brief, plan=plan, approved=False)
        plan_store.save(record)

    record.approved = True
    plan_store.save(record)
    logger.info("Plan %s approved", record.plan.plan_id)
    return record


def generate_play(
    plan_id: str,
    plan_store: PlanStore,
    job_store: JobStore,
    corpus_store: CorpusStore,
    config: GenerationConfig,
) -> GenerationRecord:
    """Generate a play from an approved plan and store the job output."""

    plan_record = plan_store.get(plan_id)
    if plan_record is None:
        raise KeyError(f"Plan not found: {plan_id}")
    if not plan_record.approved:
        raise ValueError(f"Plan not approved: {plan_id}")

    chunks = corpus_store.list_chunks()
    if not chunks:
        corpus_store.load()
        chunks = corpus_store.list_chunks()

    generated = _generate_play_from_plan(plan_record.plan, chunks, config)
    job_id = str(uuid.uuid4())
    record = GenerationRecord(
        job_id=job_id,
        plan_id=plan_record.plan.plan_id,
        status="completed",
        output_lines=generated.output_lines,
        markdown=generated.markdown,
        play_json=generated.play_json,
        updated_at=datetime.now(timezone.utc),
    )
    job_store.save(record)
    logger.info("Generation job %s completed for plan %s", job_id, plan_id)
    return record


def _generate_play_from_plan(
    plan: PlayPlan,
    chunks: List[Dict[str, object]],
    config: GenerationConfig,
) -> GeneratedPlay:
    """Generate play output for the provided plan using beam search."""

    guidance_emitter = GuidanceEmitter(plan.anchors)
    used_ids: set[str] = set()
    anchors_seen: List[str] = []
    beat_outputs: List[GeneratedBeat] = []
    output_lines: List[str] = []

    for act in plan.acts:
        for scene in act.scenes:
            for beat in scene.beats:
                available_chunks = [
                    chunk for chunk in chunks if str(chunk.get("chunk_id")) not in used_ids
                ]
                guidance = guidance_emitter.guidance_for_beat(beat)
                logger.info(
                    "Generating beat %s with %s available chunks",
                    beat.beat_id,
                    len(available_chunks),
                )
                search = BeamSearch(available_chunks)
                result = search.run(
                    guidance=guidance,
                    beam_width=config.beam_width,
                    max_length=config.max_length,
                    checkpoint_interval=config.checkpoint_interval,
                    initial_anchors=anchors_seen,
                )
                if not result.best_path:
                    logger.warning(
                        "No candidates found for beat %s; retrying without required anchors",
                        beat.beat_id,
                    )
                    relaxed_constraints = dict(guidance.constraints)
                    relaxed_constraints["required_anchor_count"] = 0.0
                    relaxed_guidance = guidance.model_copy(update={"constraints": relaxed_constraints})
                    result = search.run(
                        guidance=relaxed_guidance,
                        beam_width=config.beam_width,
                        max_length=config.max_length,
                        checkpoint_interval=config.checkpoint_interval,
                        initial_anchors=anchors_seen,
                    )

                beat_lines, beat_line_ids = _render_lines_from_chunks(result.best_path, available_chunks)
                output_lines.extend(beat_lines)
                used_ids.update(beat_line_ids)
                anchors_seen.extend(
                    _extract_anchor_hits_for_lines(available_chunks, beat_line_ids, guidance.anchor_targets)
                )
                beat_outputs.append(
                    GeneratedBeat(beat_id=beat.beat_id, line_ids=beat_line_ids, lines=beat_lines)
                )

    markdown = _render_markdown(plan, beat_outputs)
    play_json = _render_play_json(plan, beat_outputs)
    return GeneratedPlay(
        output_lines=output_lines,
        beat_outputs=beat_outputs,
        markdown=markdown,
        play_json=play_json,
    )


def _render_lines_from_chunks(
    line_ids: List[str],
    chunks: List[Dict[str, object]],
) -> Tuple[List[str], List[str]]:
    """Render line text for selected chunk identifiers."""

    chunk_map = {str(chunk.get("chunk_id")): chunk for chunk in chunks}
    lines: List[str] = []
    resolved_ids: List[str] = []
    for line_id in line_ids:
        chunk = chunk_map.get(line_id)
        if not chunk:
            continue
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        lines.append(text)
        resolved_ids.append(line_id)
    return lines, resolved_ids


def _extract_anchor_hits_for_lines(
    chunks: List[Dict[str, object]],
    line_ids: List[str],
    anchor_targets: List[str],
) -> List[str]:
    """Extract anchor hits from generated line identifiers."""

    chunk_map = {str(chunk.get("chunk_id")): chunk for chunk in chunks}
    anchor_hits: List[str] = []
    for line_id in line_ids:
        chunk = chunk_map.get(line_id)
        if not chunk:
            continue
        tokens = chunk.get("tokens")
        if isinstance(tokens, list):
            hits = compute_anchor_hits(tokens, anchor_targets)
        else:
            text = str(chunk.get("text", ""))
            hits = compute_anchor_hits(text.split(), anchor_targets)
        anchor_hits.extend(hits)
    return anchor_hits


def _render_markdown(plan: PlayPlan, beat_outputs: List[GeneratedBeat]) -> str:
    """Render markdown for a generated play."""

    lines: List[str] = [f"# {plan.title}", ""]
    beat_map = {beat.beat_id: beat for beat in beat_outputs}

    for act in plan.acts:
        lines.append(f"## Act {act.act}")
        for scene in act.scenes:
            lines.append(f"### Scene {scene.scene}")
            for beat in scene.beats:
                beat_output = beat_map.get(beat.beat_id)
                lines.append(f"#### Beat {beat.beat_id}")
                if beat_output:
                    for line in beat_output.lines:
                        lines.append(f"> {line}")
                lines.append("")
    return "\n".join(lines).strip() + "\n"


def _render_play_json(plan: PlayPlan, beat_outputs: List[GeneratedBeat]) -> Dict[str, object]:
    """Render JSON for a generated play."""

    beat_map = {beat.beat_id: beat for beat in beat_outputs}
    acts_payload: List[Dict[str, object]] = []

    for act in plan.acts:
        scenes_payload: List[Dict[str, object]] = []
        for scene in act.scenes:
            beats_payload: List[Dict[str, object]] = []
            for beat in scene.beats:
                beat_output = beat_map.get(beat.beat_id)
                beats_payload.append(
                    {
                        "beat_id": beat.beat_id,
                        "line_ids": list(beat_output.line_ids) if beat_output else [],
                        "lines": list(beat_output.lines) if beat_output else [],
                    }
                )
            scenes_payload.append(
                {
                    "scene_id": scene.scene_id,
                    "scene": scene.scene,
                    "beats": beats_payload,
                }
            )
        acts_payload.append({"act": act.act, "scenes": scenes_payload})

    return {
        "plan_id": plan.plan_id,
        "title": plan.title,
        "acts": acts_payload,
    }
