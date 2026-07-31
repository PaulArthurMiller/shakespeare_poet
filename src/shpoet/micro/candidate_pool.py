"""Per-beat candidate retrieval from the vector store.

Generation previously scored the entire corpus on every search step: it read
``line_chunks.jsonl`` straight off disk and asked the transition engine to walk
all ~112k chunks per beam, per depth.  That was slow, it never touched the
phrase or fragment collections, and -- most importantly -- the chunks it walked
carried none of the Tier-1/Tier-2 metadata the artistic constraints need, since
those features are computed at *index* time and live only inside Chroma.

This module narrows the field before search begins.  For each beat it asks
Chroma for the chunks semantically closest to that beat's intent, then
rehydrates the results into the chunk dictionaries the search, constraint, and
scoring layers already expect -- including ``stress_pattern``, ``rhyme_class``,
``iambic_score``, and ``emotion_valence``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

from shpoet.common.types import BeatPlan
from shpoet.features.tier1_raw import tokenize
from shpoet.micro.reuse_lock import ReuseLock
from shpoet.vectorstore.chroma_store import ChromaStore


logger = logging.getLogger(__name__)


# Ordered by granularity: whole lines first, then the smaller "puzzle pieces".
# All three are queried for every beat so the search can mix scales freely.
DEFAULT_COLLECTIONS: Sequence[str] = ("shpoet_lines", "shpoet_phrases", "shpoet_fragments")

# Metadata values that were JSON-encoded on the way in (Chroma only stores
# scalars). Decoded on the way out so callers see the original shape.
_JSON_ENCODED_KEYS = frozenset({"punctuation", "phonemes", "pos_tags"})


@dataclass(frozen=True)
class PoolResult:
    """A retrieved candidate pool plus the counts needed to debug a thin pool."""

    chunks: List[Dict[str, object]]
    query_text: str
    requested: int
    retrieved: int
    excluded: int
    duplicates: int = 0

    @property
    def size(self) -> int:
        """Number of usable candidates in the pool."""

        return len(self.chunks)


def normalize_for_dedupe(text: str) -> str:
    """Reduce chunk text to the words it quotes, for cross-collection dedupe.

    The three collections cut overlapping text out of the same lines, so the
    pool routinely retrieves ``..._line101`` and ``..._line101_p0`` -- identical
    words differing only by trailing punctuation and capitalisation.  Both would
    occupy pool slots, and (before span-based locking) both could be selected.

    Tokenizing with the indexer's own tokenizer keeps this in step with how
    ``tokens`` was derived at index time rather than inventing a second rule.
    """

    return " ".join(tokenize(text)).lower()


def build_beat_query(beat: BeatPlan, anchor_targets: Iterable[str]) -> str:
    """Compose the semantic query text for a beat.

    Combines the beat's expressive objective, its rhetorical posture, and the
    anchor vocabulary it is obliged to hit. Anchors are included because they
    are the strongest signal of what the beat is actually *about* -- the
    objective alone tends to retrieve generic material.
    """

    parts: List[str] = []
    if beat.objective:
        parts.append(beat.objective)
    if beat.rhetorical_mode:
        parts.append(beat.rhetorical_mode)

    anchors = [anchor for anchor in anchor_targets if anchor]
    if anchors:
        parts.append(" ".join(anchors))

    query = ". ".join(part.strip() for part in parts if part.strip())
    return query or beat.beat_id


def _decode_metadata_value(key: str, value: object) -> object:
    """Restore a metadata value that was JSON-encoded for storage."""

    if key not in _JSON_ENCODED_KEYS or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # Not everything in these keys is guaranteed to round-trip; keeping the
        # raw string is better than dropping the field.
        logger.debug("Could not JSON-decode metadata key %s", key)
        return value


def rehydrate_chunk(
    chunk_id: str,
    document: str,
    metadata: Optional[Dict[str, object]],
) -> Dict[str, object]:
    """Rebuild a search-ready chunk dict from a Chroma result row.

    ``text`` is stored as the Chroma document and ``tokens`` is dropped from
    metadata (it is not a scalar), so both are restored here. Everything else
    comes back from metadata untouched apart from JSON decoding.
    """

    chunk: Dict[str, object] = {}
    for key, value in (metadata or {}).items():
        chunk[key] = _decode_metadata_value(key, value)

    chunk["chunk_id"] = chunk_id
    chunk["text"] = document
    chunk["tokens"] = tokenize(document)
    return chunk


class CandidatePool:
    """Retrieve and cache per-beat candidate chunks from the Chroma index.

    One store handle is opened per collection and reused across beats: opening
    a ``PersistentClient`` per query would dominate generation time.
    """

    def __init__(
        self,
        persist_dir: Path,
        collection_names: Sequence[str] = DEFAULT_COLLECTIONS,
        embedding_dimensions: int = 8,
        pool_size: int = 800,
        over_fetch: float = 2.0,
    ) -> None:
        """Open the collections that will be queried for every beat.

        Args:
            persist_dir: Directory holding the persisted Chroma collections.
            collection_names: Collections to query and merge per beat.
            embedding_dimensions: Must match the dimensions the index was built
                with; a mismatch produces meaningless neighbours rather than an
                error, so it is threaded through from settings.
            pool_size: Target number of usable candidates per beat, summed
                across collections.
            over_fetch: Multiplier applied when asking Chroma, to leave headroom
                for candidates that get dropped as already-used.
        """

        if pool_size <= 0:
            raise ValueError(f"pool_size must be positive, got {pool_size}")
        if over_fetch < 1.0:
            raise ValueError(f"over_fetch must be >= 1.0, got {over_fetch}")

        self._persist_dir = persist_dir
        self._collection_names = list(collection_names)
        self._embedding_dimensions = embedding_dimensions
        self._pool_size = pool_size
        self._over_fetch = over_fetch
        self._stores: Dict[str, ChromaStore] = {}

        for name in self._collection_names:
            try:
                self._stores[name] = ChromaStore(persist_dir, collection_name=name)
            except Exception as exc:  # noqa: BLE001 - surfaced with context below
                # A missing collection should degrade the pool, not kill the run:
                # a corpus built before the phrase/fragment chunkers existed will
                # legitimately only have shpoet_lines.
                logger.warning(
                    "Could not open collection '%s' in %s (%s); continuing without it",
                    name, persist_dir, exc,
                )

        if not self._stores:
            raise FileNotFoundError(
                f"No usable Chroma collections found in {persist_dir}. "
                f"Run `python -m shpoet.scripts.build_index` first."
            )

        self._verify_dimensions()

        logger.info(
            "CandidatePool ready: collections=%s pool_size=%d dims=%d",
            list(self._stores), self._pool_size, self._embedding_dimensions,
        )

    def _verify_dimensions(self) -> None:
        """Fail fast when the configured dimensions do not match the index.

        A mismatch is not recoverable and not obvious from the symptoms: every
        query raises inside Chroma, each beat logs an error and falls back to an
        empty pool, and the run finishes "successfully" with an empty play.
        Better to refuse to start and say which setting is wrong.
        """

        for name, store in self._stores.items():
            stored = store.embedding_dimension()
            if stored is None:
                # Empty collection, or a Chroma build that will not report it.
                logger.debug("No stored vectors to check dimensions against in '%s'", name)
                continue
            if stored != self._embedding_dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch for collection '{name}': the index holds "
                    f"{stored}-dim vectors but SHPOET_EMBEDDING_DIMENSIONS is "
                    f"{self._embedding_dimensions}. Set the dimensions to {stored} (and make "
                    f"sure SHPOET_EMBEDDING_PROVIDER/MODEL match the ones used to build the "
                    f"index), or rebuild with `python -m shpoet.scripts.build_index`."
                )

    def for_beat(
        self,
        beat: BeatPlan,
        anchor_targets: Iterable[str],
        reuse_lock: Optional[ReuseLock] = None,
    ) -> PoolResult:
        """Retrieve the candidate pool for a single beat.

        Args:
            beat: The beat being generated; supplies the semantic query.
            anchor_targets: Anchor vocabulary for this beat, folded into the query.
            reuse_lock: The play-level lock holding everything already quoted.
                Candidates whose source words it covers are dropped here so the
                no-reuse rule does not silently eat the pool inside the search
                loop -- and so the pool is not padded with chunks that are cut
                from lines the play has already spent.

        Returns:
            A PoolResult holding search-ready chunk dicts, deduped by chunk id
            and by normalized text, deterministically ordered by
            (distance, chunk_id).
        """

        query_text = build_beat_query(beat, anchor_targets)

        # Split the budget across collections, with headroom for exclusions.
        per_collection = max(1, self._pool_size // len(self._stores))
        n_results = int(per_collection * self._over_fetch)

        scored: List[tuple[float, str, Dict[str, object]]] = []
        seen_ids: Set[str] = set()
        # Normalized text -> index into `scored`, so a later, closer duplicate
        # can replace an earlier one instead of both taking a slot.
        seen_texts: Dict[str, int] = {}
        retrieved = 0
        excluded_hits = 0
        duplicate_hits = 0

        for name, store in self._stores.items():
            try:
                results = store.query(
                    query_text,
                    n_results=n_results,
                    embedding_dimensions=self._embedding_dimensions,
                )
            except Exception as exc:  # noqa: BLE001 - one bad collection must not abort the beat
                logger.error(
                    "Query failed against collection '%s' for beat %s: %s",
                    name, beat.beat_id, exc,
                )
                continue

            ids = (results.get("ids") or [[]])[0]
            documents = (results.get("documents") or [[]])[0]
            metadatas = (results.get("metadatas") or [[]])[0]
            distances = (results.get("distances") or [[]])[0]
            retrieved += len(ids)

            for position, chunk_id in enumerate(ids):
                chunk_id = str(chunk_id)
                if chunk_id in seen_ids:
                    continue

                document = str(documents[position]) if position < len(documents) else ""
                if not document.strip():
                    continue
                metadata = metadatas[position] if position < len(metadatas) else {}
                # Absent distances (some Chroma configurations omit them) sort
                # last rather than crashing the beat.
                distance = float(distances[position]) if position < len(distances) else float("inf")

                chunk = rehydrate_chunk(chunk_id, document, metadata)
                if reuse_lock is not None and reuse_lock.is_used(chunk):
                    excluded_hits += 1
                    continue

                seen_ids.add(chunk_id)
                row = (distance, chunk_id, chunk)

                normalized = normalize_for_dedupe(document)
                existing = seen_texts.get(normalized)
                if existing is None:
                    seen_texts[normalized] = len(scored)
                    scored.append(row)
                    continue

                # Same words already in the pool: keep whichever is closer to the
                # query, breaking ties on chunk_id so the choice is reproducible.
                duplicate_hits += 1
                incumbent = scored[existing]
                if (row[0], row[1]) < (incumbent[0], incumbent[1]):
                    scored[existing] = row

        # chunk_id breaks distance ties so the pool -- and therefore generation --
        # is reproducible across runs.
        scored.sort(key=lambda row: (row[0], row[1]))
        chunks = [row[2] for row in scored[: self._pool_size]]

        if not chunks:
            logger.warning(
                "Empty candidate pool for beat %s (retrieved=%d, excluded=%d, "
                "duplicates=%d, query=%r)",
                beat.beat_id, retrieved, excluded_hits, duplicate_hits, query_text,
            )
        else:
            logger.info(
                "Beat %s pool: %d candidates from %d retrieved "
                "(%d excluded as used, %d duplicate texts collapsed)",
                beat.beat_id, len(chunks), retrieved, excluded_hits, duplicate_hits,
            )

        return PoolResult(
            chunks=chunks,
            query_text=query_text,
            requested=self._pool_size,
            retrieved=retrieved,
            excluded=excluded_hits,
            duplicates=duplicate_hits,
        )

    def close(self) -> None:
        """Release the underlying Chroma clients."""

        for name, store in self._stores.items():
            try:
                store.close()
            except Exception as exc:  # noqa: BLE001 - close must not mask the real error
                logger.warning("Error closing collection '%s': %s", name, exc)
        self._stores.clear()

    def __enter__(self) -> "CandidatePool":
        """Support use as a context manager."""

        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the pool on context exit."""

        self.close()
