"""Resolve the chunk ids stored on a generated play back into chunk dicts.

The generation path never needs this: it holds the chunk dictionaries it
selected, so ``check_used_chunks`` can validate the play directly.  An
*exported* play holds only ids.  ``data/output/*.json`` records each beat's
selections as ``line_ids`` -- which are in fact chunk ids -- and a bare id says
nothing about which source words it spent.  Without provenance, quote integrity
cannot be checked at all: every quote would come back ``unverifiable``, and a
report of zero violations would prove nothing.

Two backends recover that provenance, and the choice between them is a real
trade-off rather than a preference:

* ``JsonlChunkResolver`` reads ``data/processed/*_chunks.jsonl``.  Always
  available, needs no index, and carries the provenance triple
  (``line_id``, ``start_word_idx``, ``end_word_idx``) plus ``play``/``act``/
  ``scene``.  It carries **no Tier-2 metadata** -- ``iambic_score`` and
  ``syllable_count`` are computed at index time and live only inside Chroma
  (see BUILD-PLAN.md §2) -- so a scorecard built on this resolver can report
  quote integrity and source diversity but must report meter and line length as
  unmeasured.
* ``ChromaChunkResolver`` reads the index by id.  It embeds nothing, so it costs
  no API calls, and it returns the full Tier-2 metadata.

Neither resolver invents anything.  An id that cannot be found comes back
missing, and the caller is expected to surface that rather than skip it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

from shpoet.micro.candidate_pool import DEFAULT_COLLECTIONS, rehydrate_chunk
from shpoet.validation.quote_integrity import (
    IntegrityReport,
    QuoteUsage,
    check_quote_integrity,
    usage_from_chunk,
)
from shpoet.vectorstore.chroma_store import ChromaStore


logger = logging.getLogger(__name__)


# The processed chunk files, in the same order build_index.py indexes them.
PROCESSED_CHUNK_FILES: Sequence[str] = (
    "line_chunks.jsonl",
    "phrase_chunks.jsonl",
    "fragment_chunks.jsonl",
)


class ChunkResolver(Protocol):
    """Something that can turn chunk ids back into chunk dictionaries."""

    def resolve(self, chunk_ids: Sequence[str]) -> Dict[str, Dict[str, object]]:
        """Return a mapping of chunk_id -> chunk dict, omitting ids not found."""


class JsonlChunkResolver:
    """Resolve chunk ids by streaming the processed JSONL chunk files.

    Ids are looked up in a single pass per file rather than by loading the whole
    corpus into a dictionary: the three files hold ~447k chunks between them,
    while a play asks about a few hundred ids.  Resolved chunks are cached, so
    repeated calls only stream for ids not seen before.
    """

    def __init__(
        self,
        processed_dir: Path,
        chunk_files: Sequence[str] = PROCESSED_CHUNK_FILES,
    ) -> None:
        """Initialize the resolver against a processed corpus directory."""

        self._processed_dir = processed_dir
        self._chunk_files = list(chunk_files)
        self._cache: Dict[str, Dict[str, object]] = {}

    def resolve(self, chunk_ids: Sequence[str]) -> Dict[str, Dict[str, object]]:
        """Return chunk dicts for the requested ids, omitting any not found."""

        wanted = {chunk_id for chunk_id in chunk_ids if chunk_id}
        found = {
            chunk_id: self._cache[chunk_id]
            for chunk_id in wanted
            if chunk_id in self._cache
        }
        outstanding = wanted - found.keys()
        if not outstanding:
            return found

        for filename in self._chunk_files:
            if not outstanding:
                break
            path = self._processed_dir / filename
            if not path.exists():
                logger.warning("Processed chunk file missing, skipping: %s", path)
                continue
            for chunk in self._stream_matching(path, outstanding):
                chunk_id = str(chunk.get("chunk_id", ""))
                self._cache[chunk_id] = chunk
                found[chunk_id] = chunk
                outstanding.discard(chunk_id)

        if outstanding:
            logger.warning(
                "%d chunk ids were not found in %s (e.g. %s)",
                len(outstanding), self._processed_dir, sorted(outstanding)[:3],
            )
        return found

    def _stream_matching(
        self,
        path: Path,
        wanted: Iterable[str],
    ) -> List[Dict[str, object]]:
        """Read one JSONL file and return the chunks whose ids are wanted."""

        wanted_set = set(wanted)
        matches: List[Dict[str, object]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, raw in enumerate(handle, start=1):
                    if not raw.strip():
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        logger.error("Malformed JSON at %s:%d (%s)", path, line_number, exc)
                        continue
                    if str(chunk.get("chunk_id", "")) in wanted_set:
                        matches.append(chunk)
        except OSError as exc:
            logger.error("Could not read processed chunk file %s: %s", path, exc)
            return matches

        logger.debug("Resolved %d ids from %s", len(matches), path.name)
        return matches


class ChromaChunkResolver:
    """Resolve chunk ids against the Chroma index, Tier-2 metadata included.

    This is the resolver to prefer when the index exists: it is the only source
    of ``iambic_score``, ``syllable_count``, ``stress_pattern`` and the rest of
    the Tier-2 features, which the JSONL files do not carry.
    """

    def __init__(
        self,
        persist_dir: Path,
        collection_names: Sequence[str] = DEFAULT_COLLECTIONS,
    ) -> None:
        """Open the collections that will be searched for each id.

        Raises:
            FileNotFoundError: if the directory does not exist, or holds no
                collection with anything in it.
        """

        # Checked before touching chromadb because PersistentClient *creates*
        # the directory, and get_or_create_collection creates empty collections
        # inside it. Opening a path that does not exist would therefore succeed,
        # hand back a resolver that can resolve nothing, and report every quote
        # in the play as unverifiable -- a silent wrong answer where an error
        # belongs.
        if not persist_dir.exists():
            raise FileNotFoundError(
                f"No Chroma index directory at {persist_dir}. "
                f"Run `python -m shpoet.scripts.build_index` first, or use "
                f"JsonlChunkResolver against the processed corpus instead."
            )

        self._persist_dir = persist_dir
        self._stores: Dict[str, ChromaStore] = {}
        for name in collection_names:
            try:
                store = ChromaStore(persist_dir, collection_name=name)
            except Exception as exc:  # noqa: BLE001 - surfaced with context below
                logger.warning(
                    "Could not open collection '%s' in %s (%s); continuing without it",
                    name, persist_dir, exc,
                )
                continue

            # An empty collection is indistinguishable from a missing one for
            # resolution purposes, and keeping it would mask the difference.
            if store.count() == 0:
                logger.debug("Collection '%s' in %s is empty; skipping", name, persist_dir)
                store.close()
                continue
            self._stores[name] = store

        if not self._stores:
            raise FileNotFoundError(
                f"No populated Chroma collections found in {persist_dir}. "
                f"Run `python -m shpoet.scripts.build_index` first, or use "
                f"JsonlChunkResolver against the processed corpus instead."
            )

    def resolve(self, chunk_ids: Sequence[str]) -> Dict[str, Dict[str, object]]:
        """Return chunk dicts for the requested ids, omitting any not found."""

        outstanding = {chunk_id for chunk_id in chunk_ids if chunk_id}
        found: Dict[str, Dict[str, object]] = {}

        for name, store in self._stores.items():
            if not outstanding:
                break
            try:
                results = store.get_by_ids(sorted(outstanding))
            except Exception as exc:  # noqa: BLE001 - one bad collection is not fatal
                logger.error("Lookup failed against collection '%s': %s", name, exc)
                continue

            ids = results.get("ids") or []
            documents = results.get("documents") or []
            metadatas = results.get("metadatas") or []
            for position, chunk_id in enumerate(ids):
                chunk_id = str(chunk_id)
                document = str(documents[position]) if position < len(documents) else ""
                metadata = metadatas[position] if position < len(metadatas) else {}
                found[chunk_id] = rehydrate_chunk(chunk_id, document, metadata)
                outstanding.discard(chunk_id)

        if outstanding:
            logger.warning(
                "%d chunk ids were not found in %s (e.g. %s)",
                len(outstanding), self._persist_dir, sorted(outstanding)[:3],
            )
        return found

    def close(self) -> None:
        """Release the underlying Chroma clients."""

        for name, store in self._stores.items():
            try:
                store.close()
            except Exception as exc:  # noqa: BLE001 - close must not mask the real error
                logger.warning("Error closing collection '%s': %s", name, exc)
        self._stores.clear()

    def __enter__(self) -> "ChromaChunkResolver":
        """Support use as a context manager."""

        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the resolver on context exit."""

        self.close()


def iter_play_quotes(
    play_json: Mapping[str, object],
) -> List[Tuple[str, str, str]]:
    """Walk an exported play and yield (beat_id, chunk_id, text) in play order.

    Note the field name: the export calls these ``line_ids``, but they are chunk
    ids -- a phrase or fragment chunk is not a whole line.  The naming predates
    the phrase and fragment chunkers.
    """

    quotes: List[Tuple[str, str, str]] = []
    acts = play_json.get("acts")
    if not isinstance(acts, list):
        logger.warning("Exported play has no 'acts' list; nothing to validate")
        return quotes

    for act in acts:
        if not isinstance(act, Mapping):
            continue
        for scene in act.get("scenes") or []:
            if not isinstance(scene, Mapping):
                continue
            for beat in scene.get("beats") or []:
                if not isinstance(beat, Mapping):
                    continue
                beat_id = str(beat.get("beat_id", ""))
                chunk_ids = beat.get("line_ids") or []
                lines = beat.get("lines") or []
                for position, chunk_id in enumerate(chunk_ids):
                    text = str(lines[position]) if position < len(lines) else ""
                    quotes.append((beat_id, str(chunk_id), text))
    return quotes


def usages_from_play_json(
    play_json: Mapping[str, object],
    resolver: ChunkResolver,
) -> List[QuoteUsage]:
    """Resolve an exported play's chunk ids into QuoteUsage records.

    An id the resolver cannot find still produces a QuoteUsage -- with no span,
    so it is counted as unverifiable.  Dropping it instead would let a play
    whose corpus has drifted out from under it report a clean bill of health.
    """

    quotes = iter_play_quotes(play_json)
    resolved = resolver.resolve([chunk_id for _, chunk_id, _ in quotes])

    usages: List[QuoteUsage] = []
    unresolved = 0
    for beat_id, chunk_id, exported_text in quotes:
        chunk = resolved.get(chunk_id)
        if chunk is None:
            unresolved += 1
            usages.append(
                QuoteUsage(beat_id=beat_id, chunk_id=chunk_id, text=exported_text, span=None)
            )
            continue
        usages.append(usage_from_chunk(beat_id, chunk))

    logger.info(
        "Resolved %d/%d quotes from exported play (%d unresolved)",
        len(quotes) - unresolved, len(quotes), unresolved,
    )
    return usages


def check_exported_play(
    play_json: Mapping[str, object],
    resolver: ChunkResolver,
) -> IntegrityReport:
    """Validate quote integrity for a play loaded from ``data/output/``.

    The counterpart to ``check_used_chunks`` for plays the current process did
    not generate.  A non-zero ``unverifiable`` count on the returned report
    means the check was partial, not that the play was clean.
    """

    return check_quote_integrity(usages_from_play_json(play_json, resolver))


def load_play_json(path: Path) -> Dict[str, object]:
    """Read an exported play JSON file from disk.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the file is not a JSON object.
    """

    if not path.exists():
        raise FileNotFoundError(f"Exported play not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"Exported play is not a JSON object: {path}")
    return payload


def build_resolver(
    processed_dir: Path,
    chroma_dir: Optional[Path] = None,
) -> ChunkResolver:
    """Return the best available resolver, preferring the Tier-2-carrying index.

    Falls back to the processed JSONL files when there is no usable index. The
    fallback is real but lossy -- see this module's docstring -- so the choice is
    logged rather than made silently.
    """

    if chroma_dir is not None:
        try:
            resolver = ChromaChunkResolver(chroma_dir)
        except FileNotFoundError as exc:
            logger.warning(
                "No Chroma index at %s (%s); resolving from %s instead. "
                "Tier-2 metadata will be absent, so meter and line-length "
                "metrics cannot be measured.",
                chroma_dir, exc, processed_dir,
            )
        else:
            logger.info("Resolving chunk ids from the Chroma index at %s", chroma_dir)
            return resolver

    logger.info("Resolving chunk ids from the processed corpus at %s", processed_dir)
    return JsonlChunkResolver(processed_dir)
