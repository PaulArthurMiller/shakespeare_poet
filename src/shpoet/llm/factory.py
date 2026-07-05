"""Factory functions to create LLM clients, critics, and choosers from settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

from shpoet.llm.client import LLMClient
from shpoet.llm.critic import Critic
from shpoet.llm.chooser import Chooser


logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def create_llm_client(api_key: str, model: str) -> Optional[LLMClient]:
    """Return an AnthropicLLMClient if an API key is provided, else None."""
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set; LLM critic/chooser disabled")
        return None
    from shpoet.llm.anthropic_client import AnthropicLLMClient
    client = AnthropicLLMClient(api_key=api_key, model=model)
    logger.info("Anthropic LLM client created with model %s", model)
    return client


def create_critic_and_chooser(
    client: Optional[LLMClient],
    use_chooser: bool = False,
) -> Tuple[Optional[Critic], Optional[Chooser]]:
    """Return a (Critic, Chooser) pair wired to the given client, or (None, None)."""
    if client is None:
        return None, None
    critic = Critic(client=client, prompt_path=_PROMPTS_DIR / "critic_v1.txt")
    chooser = Chooser(
        client=client,
        prompt_path=_PROMPTS_DIR / "chooser_v1.txt",
        enabled=use_chooser,
    )
    return critic, chooser
