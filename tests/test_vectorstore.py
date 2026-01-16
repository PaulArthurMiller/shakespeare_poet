"""Vector store build and query tests using stub embeddings."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json

from shpoet.vectorstore.build_index import build_index
from shpoet.vectorstore.query import query_index


def _write_chunks(path: Path) -> None:
    """Write a minimal chunk JSONL file for vectorstore tests."""

    chunks = [
        {
            "chunk_id": "line_1",
            "text": "To be, or not to be.",
            "line_id": "line_1",
            "play": "Hamlet",
            "act": 1,
            "scene": 1,
            "line_in_scene": 1,
            "word_index": "0,1,2,3,4,5",
        },
        {
            "chunk_id": "line_2",
            "text": "The lady doth protest too much, methinks.",
            "line_id": "line_2",
            "play": "Hamlet",
            "act": 1,
            "scene": 1,
            "line_in_scene": 2,
            "word_index": "0,1,2,3,4,5",
        },
    ]

    path.write_text("\n".join([json.dumps(chunk) for chunk in chunks]) + "\n", encoding="utf-8")


def test_build_and_query_index() -> None:
    """Ensure the vector store can build and return query results."""

    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        chunks_path = tmp_path / "line_chunks.jsonl"
        _write_chunks(chunks_path)

        persist_dir = tmp_path / "chroma"
        count = build_index(chunks_path=chunks_path, persist_dir=persist_dir)

        assert count == 2

        results = query_index("question", persist_dir=persist_dir, n_results=1)
        assert results["ids"][0]
