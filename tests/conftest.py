"""Shared pytest fixtures for the shpoet test suite."""

from __future__ import annotations

import pytest

from shpoet.config.settings import reset_settings
from shpoet.vectorstore.embeddings import reset_embedder


@pytest.fixture(autouse=True)
def _force_stub_embedder(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    """Isolate every test from real embedding providers and real project data.

    `.env` configures a real embedding provider and API key for actual runs.
    Without this override, any test that builds a ChromaStore would call the
    real OpenAI/Voyage API — spending money and requiring network access just
    to run the test suite. Tests that need to exercise real-provider logic
    can still override SHPOET_EMBEDDING_PROVIDER themselves within the test.

    The same applies to on-disk state. The API app now opens a CandidatePool
    from `settings.chroma_dir` at startup, and the real `data/chroma` holds
    3072-dim vectors while the stub embedder produces 8-dim ones — so without
    redirecting the path, every API test would either hit a dimension mismatch
    or query the production index. `SHPOET_OUTPUT_DIR` is redirected for the
    same reason: the API flow test was previously writing generated plays into
    the real `data/output`.
    """

    isolated = tmp_path_factory.mktemp("shpoet_isolated")

    monkeypatch.setenv("SHPOET_EMBEDDING_PROVIDER", "stub")
    monkeypatch.setenv("SHPOET_CHROMA_DIR", str(isolated / "chroma"))
    monkeypatch.setenv("SHPOET_OUTPUT_DIR", str(isolated / "output"))
    reset_settings()
    reset_embedder()
    yield
    reset_settings()
    reset_embedder()
