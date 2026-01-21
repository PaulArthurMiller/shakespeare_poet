"""LLM client adapter abstractions."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class LLMMessage(BaseModel):
    """Single message payload for chat-style LLM requests."""

    role: str = Field(..., description="Role for the message (system/user/assistant).")
    content: str = Field(..., description="Message content for the LLM.")


class LLMRequest(BaseModel):
    """Structured request payload for an LLM call."""

    messages: List[LLMMessage] = Field(default_factory=list)
    model: Optional[str] = Field(default=None, description="Optional model identifier.")
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=512)
    response_format: Optional[str] = Field(default=None, description="Optional response format hint.")


class LLMResponse(BaseModel):
    """Structured response payload from an LLM call."""

    content: str = Field(..., description="Raw text content returned by the model.")
    raw: Dict[str, object] = Field(default_factory=dict, description="Optional raw provider payload.")


class LLMClient(Protocol):
    """Protocol for LLM clients used by critic/chooser modules."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for a structured LLM request."""


@dataclass
class StubLLMClient:
    """Deterministic stub LLM client for tests and offline runs."""

    canned_response: Dict[str, object]

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return a canned JSON response for the provided request."""

        logger.debug("Stub LLM invoked with %s messages", len(request.messages))
        content = json.dumps(self.canned_response)
        return LLMResponse(content=content, raw={"stub": True})
