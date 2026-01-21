"""Optional LLM-powered chooser for high-entropy decisions."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from shpoet.common.types import GuidanceProfile
from shpoet.llm.client import LLMClient, LLMMessage, LLMRequest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChoiceOption:
    """Candidate option presented to the chooser."""

    option_id: str
    score: float
    preview: str


@dataclass(frozen=True)
class ChoiceDecision:
    """Chooser decision payload."""

    chosen_id: str
    notes: List[str]


class Chooser:
    """Toggleable chooser that can override deterministic selection."""

    def __init__(self, client: LLMClient, prompt_path: Path, enabled: bool = False) -> None:
        """Initialize the chooser with an LLM client and prompt template."""

        self._client = client
        self._prompt = prompt_path.read_text(encoding="utf-8")
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Return whether the chooser is enabled."""

        return self._enabled

    def choose(
        self,
        window_id: str,
        guidance: GuidanceProfile,
        options: List[ChoiceOption],
    ) -> ChoiceDecision:
        """Choose among candidate options, optionally using the LLM."""

        if not options:
            logger.warning("Chooser received no options for %s", window_id)
            return ChoiceDecision(chosen_id="", notes=["No options provided."])

        if not self._enabled:
            logger.info("Chooser disabled; selecting highest score for %s", window_id)
            best_option = max(options, key=lambda option: option.score)
            return ChoiceDecision(chosen_id=best_option.option_id, notes=["Chooser disabled."])

        payload = {
            "window_id": window_id,
            "beat_id": guidance.beat_id,
            "anchor_targets": guidance.anchor_targets,
            "options": [
                {
                    "id": option.option_id,
                    "score": option.score,
                    "preview": option.preview,
                }
                for option in options
            ],
        }
        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=self._prompt),
                LLMMessage(role="user", content=json.dumps(payload)),
            ],
            response_format="json",
            temperature=0.2,
            max_tokens=256,
        )
        response = self._client.generate(request)
        decision = self._parse_response(response.content, options)
        logger.info("Chooser selected %s for %s", decision.chosen_id, window_id)
        return decision

    def _parse_response(self, content: str, options: List[ChoiceOption]) -> ChoiceDecision:
        """Parse chooser JSON response with safe fallback to top score."""

        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Chooser response was not valid JSON")
            best_option = max(options, key=lambda option: option.score)
            return ChoiceDecision(
                chosen_id=best_option.option_id,
                notes=["Invalid JSON response; fallback to highest score."],
            )

        chosen_id = str(raw.get("chosen_id", ""))
        notes = [str(note) for note in raw.get("notes", [])]
        valid_ids = {option.option_id for option in options}
        if chosen_id not in valid_ids:
            best_option = max(options, key=lambda option: option.score)
            return ChoiceDecision(
                chosen_id=best_option.option_id,
                notes=notes + ["Invalid choice; fallback to highest score."],
            )

        return ChoiceDecision(chosen_id=chosen_id, notes=notes)
