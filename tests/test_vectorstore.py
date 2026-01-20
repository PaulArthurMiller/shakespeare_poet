"""Vector store build and query tests using stub embeddings."""

from pathlib import Path
from tempfile import mkdtemp
import gc
import json
import shutil
import time
import sys

from shpoet.vectorstore import ChromaStore


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


def _read_chunks(path: Path) -> list[dict[str, object]]:
    """Read chunk dictionaries from a JSONL file."""

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_and_query_index() -> None:
    """Ensure the vector store can build and return query results."""

    tmpdir = Path(mkdtemp())
    persist_dir = tmpdir / "chroma"
    store = None

    try:
        chunks_path = tmpdir / "line_chunks.jsonl"
        _write_chunks(chunks_path)

        store = ChromaStore(persist_dir)
        try:
            count = store.build_index(_read_chunks(chunks_path))
            assert count == 2

            results = store.query("question", n_results=1)
            assert results["ids"][0]
        finally:
            # Always close even if assertions fail
            store.close()
            store = None
            gc.collect()

    finally:
        try:
            shutil.rmtree(tmpdir)
        except PermissionError:
            if sys.platform.startswith("win"):
                pass
            else:
                raise

