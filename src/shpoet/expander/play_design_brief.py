"""Render human-readable play design briefs."""

from __future__ import annotations

from typing import List

from shpoet.common.types import AnchorRegistry, PlayPlan, UserPlayInput


def render_brief(
    user_input: UserPlayInput,
    plan: PlayPlan,
    anchors: AnchorRegistry,
) -> str:
    """Render a markdown brief summarizing the plan and anchor strategy."""

    lines: List[str] = []
    lines.append(f"# Play Design Brief: {user_input.title}")
    lines.append("")
    lines.append("## Overview")
    lines.append(user_input.overview)
    lines.append("")
    lines.append("## Characters")
    for character in user_input.characters:
        voice = ", ".join(character.voice_traits) if character.voice_traits else "(none)"
        lines.append(f"- **{character.name}**: {character.description} (voice: {voice})")
    lines.append("")
    lines.append("## Anchor Strategy")
    if anchors.primary_anchor:
        lines.append(f"- Primary anchor: **{anchors.primary_anchor}**")
    for anchor in anchors.anchors:
        related = ", ".join(anchor.related_terms) if anchor.related_terms else "(none)"
        lines.append(f"- Anchor term: **{anchor.anchor_term}**")
        lines.append(f"  - Related terms: {related}")
        for rule in anchor.recurrence_rules:
            lines.append(f"  - Rule: {rule}")
    lines.append("")
    lines.append("## Acts and Scenes")
    for act in plan.acts:
        lines.append(f"### Act {act.act}")
        for scene in act.scenes:
            lines.append(f"- Scene {scene.scene_id} ({len(scene.beats)} beats)")
    lines.append("")
    return "\n".join(lines)
