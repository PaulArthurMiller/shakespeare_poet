"""Shared pytest fixtures for the shpoet test suite."""

from __future__ import annotations

import pytest

from shpoet.config.settings import reset_settings
from shpoet.vectorstore.embeddings import reset_embedder


@pytest.fixture(autouse=True)
def _force_stub_embedder(monkeypatch: pytest.MonkeyPatch):
    """Force the deterministic stub embedder for every test by default.

    `.env` configures a real embedding provider and API key for actual runs.
    Without this override, any test that builds a ChromaStore would call the
    real OpenAI/Voyage API — spending money and requiring network access just
    to run the test suite. Tests that need to exercise real-provider logic
    can still override SHPOET_EMBEDDING_PROVIDER themselves within the test.
    """

    monkeypatch.setenv("SHPOET_EMBEDDING_PROVIDER", "stub")
    reset_settings()
    reset_embedder()
    yield
    reset_settings()
    reset_embedder()
