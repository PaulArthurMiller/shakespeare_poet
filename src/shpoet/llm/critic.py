"""LLM-driven critic for evaluating generation windows."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

from shpoet.common.types import CriticReport, GuidanceProfile
from shpoet.llm.client import LLMClient, LLMMessage, LLMRequest


logger = logging.getLogger(__name__)


class Critic:
    """Structured critic that evaluates windows during generation."""

    def __init__(self, client: LLMClient, prompt_path: Path) -> None:
        """Initialize the critic with an LLM client and prompt template."""

        self._client = client
        self._prompt = prompt_path.read_text(encoding="utf-8")

    def evaluate_window(
        self,
        window_id: str,
        guidance: GuidanceProfile,
        window_text: str,
        anchors_seen: List[str],
    ) -> CriticReport:
        """Evaluate a window of generated text and return a structured report."""

        if not window_text.strip():
            logger.warning("Critic received empty window text for %s", window_id)
            return CriticReport(
                window_id=window_id,
                score=0.0,
                notes=["Empty window provided to critic."],
                recommendations={},
            )

        payload = {
            "window_id": window_id,
            "beat_id": guidance.beat_id,
            "anchor_targets": guidance.anchor_targets,
            "anchors_seen": anchors_seen,
            "text": window_text,
        }
        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=self._prompt),
                LLMMessage(role="user", content=json.dumps(payload)),
            ],
            response_format="json",
            temperature=0.0,
            max_tokens=512,
        )
        response = self._client.generate(request)
        report = self._parse_response(window_id, response.content)
        logger.info(
            "Critic report for %s: score=%s notes=%s",
            window_id,
            report.score,
            report.notes,
        )
        return report

    def _parse_response(self, window_id: str, content: str) -> CriticReport:
        """Parse the LLM response into a CriticReport with fallbacks."""

        try:
            raw: Dict[str, object] = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Critic response was not valid JSON for %s", window_id)
            return CriticReport(
                window_id=window_id,
                score=0.0,
                notes=["Invalid JSON from critic."],
                recommendations={},
            )

        score = float(raw.get("score", 0.0))
        notes = [str(note) for note in raw.get("notes", [])]
        recommendations = {
            str(key): float(value)
            for key, value in (raw.get("recommendations") or {}).items()
        }
        return CriticReport(
            window_id=window_id,
            score=score,
            notes=notes,
            recommendations=recommendations,
        )
