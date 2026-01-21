"""Tests for LLM critic and chooser helpers."""

from __future__ import annotations

from pathlib import Path

from shpoet.common.types import GuidanceProfile
from shpoet.llm.chooser import ChoiceOption, Chooser
from shpoet.llm.client import StubLLMClient
from shpoet.llm.critic import Critic
from shpoet.search.beam_search import BeamSearch


def test_critic_parses_stub_response() -> None:
    """Ensure the critic parses JSON responses from the LLM client."""

    client = StubLLMClient(
        {
            "score": 0.85,
            "notes": ["Solid anchor coverage."],
            "recommendations": {"anchor_presence": 0.2},
        }
    )
    critic = Critic(client=client, prompt_path=Path("src/shpoet/llm/prompts/critic_v1.txt"))
    guidance = GuidanceProfile(beat_id="beat-1", anchor_targets=["love"], constraints={}, priors={})

    report = critic.evaluate_window(
        window_id="window-1",
        guidance=guidance,
        window_text="Love is bright",
        anchors_seen=["love"],
    )

    assert report.score == 0.85
    assert report.notes == ["Solid anchor coverage."]
    assert report.recommendations == {"anchor_presence": 0.2}


def test_chooser_disabled_returns_highest_score() -> None:
    """Verify the chooser defaults to the highest score when disabled."""

    client = StubLLMClient({"chosen_id": ""})
    chooser = Chooser(
        client=client,
        prompt_path=Path("src/shpoet/llm/prompts/chooser_v1.txt"),
        enabled=False,
    )
    guidance = GuidanceProfile(beat_id="beat-1", anchor_targets=[], constraints={}, priors={})
    options = [
        ChoiceOption(option_id="c1", score=1.0, preview="One"),
        ChoiceOption(option_id="c2", score=2.0, preview="Two"),
    ]

    decision = chooser.choose(window_id="depth-1", guidance=guidance, options=options)

    assert decision.chosen_id == "c2"


def test_beam_search_collects_critic_reports_with_chooser() -> None:
    """Confirm beam search logs critic reports when provided a critic instance."""

    critic_client = StubLLMClient(
        {
            "score": 0.5,
            "notes": ["Ok."],
            "recommendations": {},
        }
    )
    chooser_client = StubLLMClient(
        {
            "chosen_id": "c2",
            "notes": ["Pick c2."],
        }
    )
    critic = Critic(client=critic_client, prompt_path=Path("src/shpoet/llm/prompts/critic_v1.txt"))
    chooser = Chooser(
        client=chooser_client,
        prompt_path=Path("src/shpoet/llm/prompts/chooser_v1.txt"),
        enabled=True,
    )
    chunks = [
        {
            "chunk_id": "c1",
            "text": "Love is bright",
            "tokens": ["Love", "is", "bright"],
            "token_count": 3,
        },
        {
            "chunk_id": "c2",
            "text": "The night grows",
            "tokens": ["The", "night", "grows"],
            "token_count": 3,
        },
    ]
    guidance = GuidanceProfile(
        beat_id="beat-1",
        anchor_targets=["love"],
        constraints={"required_anchor_count": 0.0},
        priors={"anchor_presence": 1.0, "length_preference": 0.0},
    )

    search = BeamSearch(chunks)
    result = search.run(
        guidance=guidance,
        beam_width=2,
        max_length=2,
        checkpoint_interval=1,
        critic=critic,
        chooser=chooser,
    )

    assert result.critic_reports
    assert result.critic_reports[0].window_id == "depth-1"
