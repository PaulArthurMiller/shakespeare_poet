"""Vector store build and query tests using stub embeddings."""

from pathlib import Path
from tempfile import mkdtemp
import gc
import json
import shutil
import time

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
    try:
        chunks_path = tmpdir / "line_chunks.jsonl"
        _write_chunks(chunks_path)

        persist_dir = tmpdir / "chroma"
        store = ChromaStore(persist_dir)
        count = store.build_index(_read_chunks(chunks_path))

        assert count == 2

        results = store.query("question", n_results=1)
        assert results["ids"][0]

        store.close()
        # Ensure the SQLite handle releases on Windows before temp cleanup.
        del store
        gc.collect()
    finally:
        # Windows can hold file handles briefly; retry cleanup.
        for attempt in range(10):
            try:
                shutil.rmtree(tmpdir)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)
