"""Mechanical quality metrics for a generated play.

M1 and M2 changed what the search produces. Without a ruler that is exactly
what it appears to be, the next question -- "is this better?" -- can only be
answered by reading and hoping.

Two rules shape every metric here, and both come from how this codebase has
failed before:

1. **Unmeasured is not zero.** Every metric that depends on chunk metadata
   reports how many quotes it could actually measure, and returns ``None`` for
   its average when that count is zero. A play scored through the JSONL
   resolver, or generated on the no-retrieval fallback path, carries no
   ``iambic_score`` at all; reporting a mean of 0.0 there would look like
   catastrophically bad verse rather than an absent measurement.
2. **Mechanical only.** Nothing here judges whether a line is good. Anchor
   coverage, span reuse, meter conformity, length, and source spread are all
   countable. The aesthetic judgment stays with the reader in the composer.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from statistics import mean, median
from typing import Dict, List, Optional, Sequence

from shpoet.learning.play_run import BeatRun, PlayRun
from shpoet.scoring.features_for_scoring import compute_anchor_hits


logger = logging.getLogger(__name__)


# Iambic pentameter is ten syllables; a line within this many either side still
# scans as pentameter to an ear (feminine endings, elided syllables).
PENTAMETER_SYLLABLES = 10
PENTAMETER_TOLERANCE = 2

# A critic report at or below this score is counted as a flag. The critic
# returns 0.0 both for genuinely bad windows and for unparseable responses, and
# both deserve a human look.
CRITIC_FLAG_SCORE = 0.5


@dataclass(frozen=True)
class Distribution:
    """Summary of a numeric metric, with the size of what it is summarising.

    ``measured`` is not decoration. A mean over three quotes and a mean over
    three hundred are different claims, and ``unmeasured`` says how much of the
    play the number does not speak for.
    """

    measured: int
    unmeasured: int
    mean: Optional[float] = None
    median: Optional[float] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    @property
    def coverage(self) -> Optional[float]:
        """Fraction of quotes this distribution actually measured."""

        total = self.measured + self.unmeasured
        if total == 0:
            return None
        return self.measured / total


def summarize(values: Sequence[float], unmeasured: int) -> Distribution:
    """Build a Distribution from measured values and a count of missing ones."""

    if not values:
        return Distribution(measured=0, unmeasured=unmeasured)
    return Distribution(
        measured=len(values),
        unmeasured=unmeasured,
        mean=float(mean(values)),
        median=float(median(values)),
        minimum=float(min(values)),
        maximum=float(max(values)),
    )


@dataclass(frozen=True)
class AnchorCoverage:
    """How many of the plan's anchor obligations the play actually met."""

    required_total: int
    required_met: int
    desired_total: int
    desired_met: int
    # Beat ids whose required anchors did not all appear in their lines.
    unmet_beats: List[str] = field(default_factory=list)
    # act number -> (met, total) for required anchors.
    required_by_act: Dict[str, List[int]] = field(default_factory=dict)

    @property
    def required_coverage(self) -> Optional[float]:
        """Fraction of required obligations met, or None when there were none.

        None rather than 1.0: a plan that asked for nothing has not proved the
        anchor machinery works, and a threshold check must be able to tell those
        two situations apart.
        """

        if self.required_total == 0:
            return None
        return self.required_met / self.required_total

    @property
    def desired_coverage(self) -> Optional[float]:
        """Fraction of desired obligations met, or None when there were none."""

        if self.desired_total == 0:
            return None
        return self.desired_met / self.desired_total


@dataclass(frozen=True)
class QuoteIntegrityMetrics:
    """The finished play's compliance with the no-reuse rule."""

    passed: bool
    violations: int
    checked: int
    unverifiable: int
    # Short descriptions of the first few violations, for the CLI summary.
    examples: List[str] = field(default_factory=list)

    @property
    def fully_verified(self) -> bool:
        """True when every quote had usable provenance.

        ``passed`` with a non-zero ``unverifiable`` means the check was partial:
        no violation was found among the quotes it could see.
        """

        return self.unverifiable == 0


@dataclass(frozen=True)
class SourceDiversity:
    """How widely the play drew on the canon."""

    quotes: int
    distinct_plays: int
    distinct_source_lines: int
    unattributed: int
    # Fraction of quotes taken from the single most-used source play.
    top_play_share: Optional[float] = None
    top_plays: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHealth:
    """What the search had to do to produce this play."""

    beats: int
    beats_with_empty_pool: int
    beats_with_no_lines: int
    beats_relaxed_anchors: int
    dead_ends: int
    rollbacks: int
    checkpoints: int
    critic_calls: int
    critic_flags: int
    critic_mean_score: Optional[float] = None
    mean_pool_size: Optional[float] = None
    # False when no beat carried stats -- e.g. a play scored from an export.
    measured: bool = True


@dataclass(frozen=True)
class Scorecard:
    """The full mechanical assessment of one generated play."""

    label: str
    plan_id: str
    title: str
    generated_at: str
    line_count: int
    anchors: AnchorCoverage
    quote_integrity: QuoteIntegrityMetrics
    meter: Distribution
    line_length: Distribution
    lines_within_pentameter: Optional[float]
    diversity: SourceDiversity
    search: SearchHealth
    knobs: Dict[str, float] = field(default_factory=dict)
    config: Dict[str, object] = field(default_factory=dict)
    # False when chunks were resolved after the fact rather than held from the run.
    chunks_are_authoritative: bool = True

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable form for persistence under ``data/eval/``."""

        payload = asdict(self)
        # Derived properties are worth persisting: a stored scorecard is read by
        # eye as often as by code, and recomputing ratios by hand is error-prone.
        payload["anchors"]["required_coverage"] = self.anchors.required_coverage
        payload["anchors"]["desired_coverage"] = self.anchors.desired_coverage
        payload["quote_integrity"]["fully_verified"] = self.quote_integrity.fully_verified
        payload["meter"]["coverage"] = self.meter.coverage
        payload["line_length"]["coverage"] = self.line_length.coverage
        return payload

    def describe(self) -> str:
        """Return a multi-line human summary for the CLI."""

        lines = [
            f"Scorecard: {self.label}",
            f"  play           {self.title!r} ({self.line_count} lines, plan {self.plan_id})",
            f"  anchors        {_format_ratio(self.anchors.required_met, self.anchors.required_total)} required, "
            f"{_format_ratio(self.anchors.desired_met, self.anchors.desired_total)} desired",
            f"  integrity      {'PASS' if self.quote_integrity.passed else 'FAIL'} "
            f"({self.quote_integrity.violations} violations, "
            f"{self.quote_integrity.checked} checked, "
            f"{self.quote_integrity.unverifiable} unverifiable)",
            f"  meter          {_format_optional(self.meter.mean)} mean iambic_score "
            f"over {self.meter.measured} quotes ({self.meter.unmeasured} unmeasured)",
            f"  line length    {_format_optional(self.line_length.mean)} mean syllables, "
            f"{_format_optional(self.lines_within_pentameter, percent=True)} within "
            f"+/-{PENTAMETER_TOLERANCE} of {PENTAMETER_SYLLABLES}",
            f"  diversity      {self.diversity.distinct_plays} source plays, "
            f"{self.diversity.distinct_source_lines} source lines, "
            f"top share {_format_optional(self.diversity.top_play_share, percent=True)}",
        ]
        if self.search.measured:
            lines.append(
                f"  search         {self.search.dead_ends} dead ends, "
                f"{self.search.rollbacks} rollbacks, "
                f"{self.search.beats_relaxed_anchors}/{self.search.beats} beats relaxed, "
                f"{self.search.critic_flags}/{self.search.critic_calls} critic flags"
            )
        else:
            lines.append("  search         not measured (no per-beat stats on this run)")
        if not self.chunks_are_authoritative:
            lines.append(
                "  note           chunks were resolved from ids after the fact; "
                "metrics cover only the quotes that resolved"
            )
        return "\n".join(lines)


def _format_ratio(part: int, whole: int) -> str:
    """Format a met/total pair, marking an empty denominator as unmeasured."""

    if whole == 0:
        return "n/a"
    return f"{part}/{whole} ({part / whole:.0%})"


def _format_optional(value: Optional[float], percent: bool = False) -> str:
    """Format a value that may legitimately be unmeasured."""

    if value is None:
        return "n/a"
    return f"{value:.0%}" if percent else f"{value:.2f}"


def compute_anchor_coverage(beats: Sequence[BeatRun]) -> AnchorCoverage:
    """Count how many per-beat anchor obligations the generated lines satisfy.

    An anchor counts as met when it appears in the beat's own lines. Checking
    per beat rather than per play is the stricter and more useful reading: the
    plan places anchors deliberately, and an anchor that lands three scenes away
    from where it was asked for has not done the job the plan gave it.
    """

    required_total = 0
    required_met = 0
    desired_total = 0
    desired_met = 0
    unmet_beats: List[str] = []
    by_act: Dict[str, List[int]] = {}

    for beat in beats:
        if not beat.has_obligations:
            continue
        tokens = _tokens_for_beat(beat)
        hits = set(compute_anchor_hits(tokens, beat.required_anchors + beat.desired_anchors))

        beat_required_met = sum(1 for anchor in beat.required_anchors if anchor in hits)
        required_total += len(beat.required_anchors)
        required_met += beat_required_met
        desired_total += len(beat.desired_anchors)
        desired_met += sum(1 for anchor in beat.desired_anchors if anchor in hits)

        if beat_required_met < len(beat.required_anchors):
            unmet_beats.append(beat.beat_id)

        act_key = str(beat.act)
        tally = by_act.setdefault(act_key, [0, 0])
        tally[0] += beat_required_met
        tally[1] += len(beat.required_anchors)

    return AnchorCoverage(
        required_total=required_total,
        required_met=required_met,
        desired_total=desired_total,
        desired_met=desired_met,
        unmet_beats=unmet_beats,
        required_by_act=by_act,
    )


def _tokens_for_beat(beat: BeatRun) -> List[str]:
    """Collect the words a beat quoted, preferring indexed tokens over a split.

    Chunk ``tokens`` come from the indexer's own tokenizer, which keeps
    contractions and possessives whole ("'tis", "Neptune's"). Splitting the
    rendered text on whitespace would leave punctuation attached and quietly
    miss anchor hits, so it is only the fallback for chunkless beats.
    """

    tokens: List[str] = []
    for chunk in beat.chunks:
        chunk_tokens = chunk.get("tokens")
        if isinstance(chunk_tokens, list):
            tokens.extend(str(token) for token in chunk_tokens)
        else:
            tokens.extend(str(chunk.get("text", "")).split())

    if not beat.chunks:
        for line in beat.lines:
            tokens.extend(line.split())
    return tokens


def compute_quote_integrity(run: PlayRun) -> QuoteIntegrityMetrics:
    """Summarize the run's integrity report for the scorecard."""

    report = run.integrity
    return QuoteIntegrityMetrics(
        passed=report.passed,
        violations=len(report.violations),
        checked=report.checked,
        unverifiable=report.unverifiable,
        examples=[violation.describe() for violation in report.violations[:5]],
    )


def compute_meter_conformity(chunks: Sequence[Dict[str, object]]) -> Distribution:
    """Summarize the iambic_score of the chunks the play selected.

    Absent metadata is counted as unmeasured, never as 0.0. ``iambic_score``
    exists only on chunks that came through the vector index; a run on the
    full-corpus fallback path has none, and the difference between "the verse
    does not scan" and "meter was never measured" is the whole reason M1
    existed.
    """

    values: List[float] = []
    unmeasured = 0
    for chunk in chunks:
        raw = chunk.get("iambic_score")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            values.append(float(raw))
        else:
            unmeasured += 1
    return summarize(values, unmeasured)


def compute_line_length(chunks: Sequence[Dict[str, object]]) -> Distribution:
    """Summarize the syllable counts of the chunks the play selected."""

    values: List[float] = []
    unmeasured = 0
    for chunk in chunks:
        raw = chunk.get("syllable_count")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
            values.append(float(raw))
        else:
            unmeasured += 1
    return summarize(values, unmeasured)


def compute_pentameter_share(chunks: Sequence[Dict[str, object]]) -> Optional[float]:
    """Return the share of measurable lines within tolerance of pentameter."""

    measurable = [
        float(chunk["syllable_count"])
        for chunk in chunks
        if isinstance(chunk.get("syllable_count"), (int, float))
        and not isinstance(chunk.get("syllable_count"), bool)
        and float(chunk["syllable_count"]) > 0
    ]
    if not measurable:
        return None
    within = sum(
        1
        for count in measurable
        if abs(count - PENTAMETER_SYLLABLES) <= PENTAMETER_TOLERANCE
    )
    return within / len(measurable)


def compute_source_diversity(chunks: Sequence[Dict[str, object]]) -> SourceDiversity:
    """Measure how many distinct sources the play drew on.

    A play that quotes forty lines from one scene of Hamlet is a different
    artifact from one that quotes forty lines across twenty plays, and neither
    anchor coverage nor meter can tell them apart.
    """

    play_counts: Counter[str] = Counter()
    source_lines = set()
    unattributed = 0

    for chunk in chunks:
        play = chunk.get("play")
        if isinstance(play, str) and play.strip():
            play_counts[play.strip()] += 1
        else:
            unattributed += 1

        line_id = chunk.get("line_id")
        if isinstance(line_id, str) and line_id.strip():
            source_lines.add(line_id.strip())

    attributed = sum(play_counts.values())
    top_share = (play_counts.most_common(1)[0][1] / attributed) if attributed else None

    return SourceDiversity(
        quotes=len(chunks),
        distinct_plays=len(play_counts),
        distinct_source_lines=len(source_lines),
        unattributed=unattributed,
        top_play_share=top_share,
        top_plays=dict(play_counts.most_common(5)),
    )


def compute_search_health(beats: Sequence[BeatRun]) -> SearchHealth:
    """Aggregate the per-beat search telemetry into one view of the run."""

    stats = [beat.stats for beat in beats if beat.stats is not None]
    if not stats:
        return SearchHealth(
            beats=len(beats),
            beats_with_empty_pool=0,
            beats_with_no_lines=sum(1 for beat in beats if not beat.lines),
            beats_relaxed_anchors=0,
            dead_ends=0,
            rollbacks=0,
            checkpoints=0,
            critic_calls=0,
            critic_flags=0,
            measured=False,
        )

    critic_scores = [
        report.score for stat in stats for report in stat.critic_reports
    ]
    pool_sizes = [stat.pool_size for stat in stats if stat.pool_size > 0]

    return SearchHealth(
        beats=len(beats),
        beats_with_empty_pool=sum(1 for stat in stats if stat.pool_size == 0),
        beats_with_no_lines=sum(1 for stat in stats if stat.lines_produced == 0),
        beats_relaxed_anchors=sum(1 for stat in stats if stat.relaxed_anchors),
        dead_ends=sum(stat.dead_ends for stat in stats),
        rollbacks=sum(stat.rollbacks for stat in stats),
        checkpoints=sum(stat.checkpoints for stat in stats),
        critic_calls=len(critic_scores),
        critic_flags=sum(1 for score in critic_scores if score <= CRITIC_FLAG_SCORE),
        critic_mean_score=float(mean(critic_scores)) if critic_scores else None,
        mean_pool_size=float(mean(pool_sizes)) if pool_sizes else None,
        measured=True,
    )


def compute_scorecard(run: PlayRun, label: str = "unlabeled") -> Scorecard:
    """Compute every metric for one generated play.

    Args:
        run: The normalized play run to score.
        label: Names this run in the stored scorecard -- typically the scenario
            name plus the arm of an A/B ("mirror-soliloquy/knobs-on").

    Returns:
        A Scorecard that reports, for every metric, how much of the play it was
        able to measure.
    """

    chunks = run.all_chunks
    scorecard = Scorecard(
        label=label,
        plan_id=run.plan_id,
        title=run.title,
        generated_at=datetime.now(timezone.utc).isoformat(),
        line_count=run.line_count,
        anchors=compute_anchor_coverage(run.beats),
        quote_integrity=compute_quote_integrity(run),
        meter=compute_meter_conformity(chunks),
        line_length=compute_line_length(chunks),
        lines_within_pentameter=compute_pentameter_share(chunks),
        diversity=compute_source_diversity(chunks),
        search=compute_search_health(run.beats),
        knobs=asdict(run.knobs) if run.knobs is not None else {},
        config=dict(run.config),
        chunks_are_authoritative=run.chunks_are_authoritative,
    )
    logger.info("Scorecard computed for %s:\n%s", label, scorecard.describe())
    return scorecard
