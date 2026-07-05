"""Anthropic Messages API client implementing the LLMClient protocol."""

from __future__ import annotations

import logging
from typing import Any, Dict

from shpoet.llm.client import LLMRequest, LLMResponse


logger = logging.getLogger(__name__)


class AnthropicLLMClient:
    """LLM client backed by the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a request to the Anthropic API and return a structured response."""
        system_content = ""
        user_messages = []
        for msg in request.messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        kwargs: Dict[str, Any] = {
            "model": request.model or self._model,
            "messages": user_messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_content:
            kwargs["system"] = system_content

        logger.debug("Calling Anthropic API with model %s", kwargs["model"])
        response = self._client.messages.create(**kwargs)
        content = response.content[0].text
        return LLMResponse(
            content=content,
            raw={"model": response.model, "usage": dict(response.usage)},
        )
