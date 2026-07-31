"""Fixed scenarios run end to end and judged against explicit thresholds.

This module used to be worse than absent. ``run_scenario`` logged a warning and
returned ``passed=True`` unconditionally, so a green suite was evidence of
nothing at all -- and it looked exactly like a suite that was checking something.
Everything here is a replacement, not an extension.

What it does now: expand a fixed scenario into a plan, generate it against the
real corpus, compute a scorecard (``learning/metrics.py``), and compare that
scorecard to thresholds the scenario declares. A threshold that cannot be
evaluated because the underlying metric was never measured is a **failure**, not
a pass -- that is the rule that would have caught the original placeholder, and
it is the rule that catches a silently-empty candidate pool or a Tier-2 field
that stopped arriving.

Usage::

    python -m shpoet.learning.replay_suite                 # all scenarios
    python -m shpoet.learning.replay_suite --no-critic     # no Anthropic calls
    python -m shpoet.learning.replay_suite --ab            # knobs off vs. on
    python -m shpoet.learning.replay_suite --scenario mirror-soliloquy

Exit code is non-zero when any scenario fails.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from shpoet.api.models import GenerationConfig
from shpoet.api.services import generate_play_from_plan
from shpoet.common.types import CharacterInput, SceneInput, UserPlayInput
from shpoet.config.settings import get_settings
from shpoet.expander.expander import expand_play_input
from shpoet.learning.eval_store import save_scorecard
from shpoet.learning.metrics import Scorecard, compute_scorecard
from shpoet.learning.play_run import play_run_from_generation
from shpoet.llm.chooser import Chooser
from shpoet.llm.critic import Critic
from shpoet.llm.factory import create_critic_and_chooser, create_llm_client
from shpoet.macro.guidance import GuidanceKnobs
from shpoet.micro.candidate_pool import CandidatePool
from shpoet.micro.corpus_store import CorpusStore


logger = logging.getLogger(__name__)


# The two arms of an A/B run. "off" reproduces pre-M1 scoring exactly, which is
# what makes it a control rather than just a second configuration.
ARM_KNOBS_OFF = "knobs-off"
ARM_KNOBS_ON = "knobs-on"


@dataclass(frozen=True)
class ScenarioThresholds:
    """What a scorecard must show for its scenario to pass.

    Every threshold left as ``None`` is simply not checked. A threshold that *is*
    set but whose metric came back unmeasured fails: an assertion that cannot be
    evaluated has not been satisfied, and treating it as a pass is how the
    placeholder version of this module stayed green for months.
    """

    max_integrity_violations: int = 0
    # Unverifiable quotes mean the integrity check was partial. Allowed to be
    # non-zero only where provenance is genuinely expected to be missing.
    max_unverifiable_quotes: int = 0
    min_lines: int = 1
    min_required_anchor_coverage: Optional[float] = None
    min_mean_iambic_score: Optional[float] = None
    min_distinct_source_plays: Optional[int] = None
    # Assert Tier-2 metadata actually arrived. Retrieval is the only path that
    # carries it, and its absence is silent everywhere else.
    require_measured_meter: bool = False


@dataclass(frozen=True)
class ReplayScenario:
    """A fixed input that should keep producing acceptable output over time."""

    name: str
    description: str
    tags: List[str]
    user_input: UserPlayInput
    config: GenerationConfig = field(default_factory=GenerationConfig)
    thresholds: ScenarioThresholds = field(default_factory=ScenarioThresholds)


@dataclass(frozen=True)
class ReplayResult:
    """The outcome of running one scenario in one arm."""

    scenario_name: str
    arm: str
    passed: bool
    failures: List[str]
    scorecard: Optional[Scorecard] = None
    scorecard_path: Optional[Path] = None
    error: str = ""

    def describe(self) -> str:
        """Return a one-line verdict suitable for the CLI summary."""

        state = "PASS" if self.passed else "FAIL"
        detail = self.error or "; ".join(self.failures) or "all thresholds met"
        return f"[{state}] {self.scenario_name} ({self.arm}): {detail}"


@dataclass
class GenerationInputs:
    """The corpus, retrieval, and LLM handles a scenario generates against.

    Built once and shared across scenarios and arms: opening the three Chroma
    collections costs about five seconds, and an A/B run would otherwise pay it
    twice for no reason.
    """

    chunks: List[Dict[str, object]] = field(default_factory=list)
    candidate_pool: Optional[CandidatePool] = None
    critic: Optional[Critic] = None
    chooser: Optional[Chooser] = None

    def close(self) -> None:
        """Release the retrieval handles."""

        if self.candidate_pool is not None:
            self.candidate_pool.close()
            self.candidate_pool = None


def _mirror_soliloquy_input() -> UserPlayInput:
    """The reference scenario: one speaker, two reflective beats.

    Deliberately narrow. A scenario that varies many things at once cannot
    attribute a regression to any of them, and this one exercises the whole
    chain -- retrieval, meter constraint, anchor obligations, span locking --
    across two beats, which is the minimum that proves the play-level reuse lock
    carries between beats rather than resetting.

    The two beats are in two *acts*, one scene each, and that is a workaround
    rather than a design choice.  ``plan_anchors`` attaches an obligation to the
    first beat of each act while ``validate_play_plan`` requires *every* beat to
    carry one, so any act with more than one scene fails planning outright.  See
    PROGRESS.md 2026-07-31 -- it blocks M4's five-act runs and needs a decision
    about where anchors belong before it can be fixed.
    """

    return UserPlayInput(
        title="The Ashen Mirror",
        overview=(
            "A ruler confronts a mirror that remembers every broken oath, and "
            "must decide whether to look away."
        ),
        characters=[
            CharacterInput(
                name="Cassia",
                description="A cautious sovereign testing prophecy against memory.",
                voice_traits=["measured", "wary"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A dim hall with a tarnished mirror.",
                summary="Cassia sees old vows shimmer across the glass.",
                participants=["Cassia"],
            ),
            SceneInput(
                act=2,
                scene=1,
                setting="The same hall, one candle fewer.",
                summary="Cassia weighs the crown against the oath that bought it.",
                participants=["Cassia"],
            ),
        ],
    )


def _quarrel_input() -> UserPlayInput:
    """A second scenario with two speakers, to keep anchor placement honest.

    The expander currently emits one beat per scene with a hardcoded rhetorical
    mode, so this differs from the soliloquy mainly in its anchor vocabulary and
    scene count. That is a real limit on what the suite can distinguish today;
    it is recorded here rather than papered over.
    """

    return UserPlayInput(
        title="Two Crowns, One Table",
        overview="Two claimants argue an inheritance neither can prove.",
        characters=[
            CharacterInput(
                name="Aldric",
                description="The elder claimant, certain and loud.",
                voice_traits=["blunt", "impatient"],
            ),
            CharacterInput(
                name="Mireth",
                description="The younger claimant, patient and exact.",
                voice_traits=["precise", "cold"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A council table strewn with contested deeds.",
                summary="Aldric demands the seal; Mireth demands the proof.",
                participants=["Aldric", "Mireth"],
            ),
        ],
    )


def build_default_scenarios() -> List[ReplayScenario]:
    """Return the fixed scenarios the suite runs by default."""

    # Critic off by default: the suite is meant to be run often, and every
    # checkpoint is a paid Anthropic call. The CLI can turn it back on.
    base_config = GenerationConfig(
        beam_width=3,
        max_length=4,
        checkpoint_interval=2,
        use_critic=False,
        use_chooser=False,
    )

    return [
        ReplayScenario(
            name="mirror-soliloquy",
            description="One speaker, two reflective scenes against the full corpus.",
            tags=["anchors", "meter", "reuse"],
            user_input=_mirror_soliloquy_input(),
            config=base_config,
            thresholds=ScenarioThresholds(
                max_integrity_violations=0,
                max_unverifiable_quotes=0,
                min_lines=2,
                min_mean_iambic_score=0.3,
                min_distinct_source_plays=2,
                require_measured_meter=True,
            ),
        ),
        ReplayScenario(
            name="two-claimants",
            description="Two speakers, one contested scene.",
            tags=["anchors", "reuse"],
            user_input=_quarrel_input(),
            config=base_config,
            thresholds=ScenarioThresholds(
                max_integrity_violations=0,
                max_unverifiable_quotes=0,
                min_lines=1,
                require_measured_meter=True,
            ),
        ),
    ]


def evaluate_scorecard(
    scorecard: Scorecard,
    thresholds: ScenarioThresholds,
) -> List[str]:
    """Compare a scorecard to its thresholds and return the failures.

    Returns:
        A list of human-readable failure descriptions; empty means the scenario
        passed. Each entry names the metric, what was required, and what was
        seen, so a failing run does not need a debugger to interpret.
    """

    failures: List[str] = []

    if scorecard.quote_integrity.violations > thresholds.max_integrity_violations:
        failures.append(
            f"quote integrity: {scorecard.quote_integrity.violations} violations "
            f"(max {thresholds.max_integrity_violations}); "
            f"first: {scorecard.quote_integrity.examples[:1]}"
        )

    if scorecard.quote_integrity.unverifiable > thresholds.max_unverifiable_quotes:
        failures.append(
            f"quote integrity: {scorecard.quote_integrity.unverifiable} quotes had no "
            f"source span (max {thresholds.max_unverifiable_quotes}); the no-reuse "
            f"rule was only checked on the rest"
        )

    if scorecard.line_count < thresholds.min_lines:
        failures.append(
            f"output: {scorecard.line_count} lines (min {thresholds.min_lines})"
        )

    if thresholds.min_required_anchor_coverage is not None:
        coverage = scorecard.anchors.required_coverage
        if coverage is None:
            failures.append(
                "anchor coverage: required but unmeasured -- the plan carried no "
                "anchor obligations, so nothing was proved"
            )
        elif coverage < thresholds.min_required_anchor_coverage:
            failures.append(
                f"anchor coverage: {coverage:.0%} "
                f"(min {thresholds.min_required_anchor_coverage:.0%})"
            )

    if thresholds.require_measured_meter and scorecard.meter.measured == 0:
        failures.append(
            "meter: no quote carried an iambic_score. Tier-2 metadata is computed "
            "at index time and arrives only via retrieval, so this means the run "
            "fell back to the full corpus or the index lost its metadata"
        )

    if thresholds.min_mean_iambic_score is not None:
        if scorecard.meter.mean is None:
            failures.append(
                "meter: a minimum iambic_score was required but none was measured"
            )
        elif scorecard.meter.mean < thresholds.min_mean_iambic_score:
            failures.append(
                f"meter: mean iambic_score {scorecard.meter.mean:.2f} "
                f"(min {thresholds.min_mean_iambic_score:.2f})"
            )

    if thresholds.min_distinct_source_plays is not None:
        distinct = scorecard.diversity.distinct_plays
        if distinct < thresholds.min_distinct_source_plays:
            failures.append(
                f"source diversity: {distinct} distinct plays "
                f"(min {thresholds.min_distinct_source_plays})"
            )

    return failures


def run_scenario(
    scenario: ReplayScenario,
    inputs: GenerationInputs,
    knobs: Optional[GuidanceKnobs] = None,
    arm: str = ARM_KNOBS_ON,
    eval_dir: Optional[Path] = None,
) -> ReplayResult:
    """Generate one scenario, score it, and judge it against its thresholds.

    Args:
        scenario: The fixed scenario to run.
        inputs: Corpus, retrieval, and LLM handles to generate against.
        knobs: Artistic knob settings; ``GuidanceKnobs.all_off()`` for a control arm.
        arm: Names this run in the stored scorecard.
        eval_dir: Where to persist the scorecard. Not written when None.

    Returns:
        A ReplayResult. A generation that raises is caught and returned as a
        failed result rather than aborting the rest of the suite -- one broken
        scenario should not hide the state of the others.
    """

    label = f"{scenario.name}/{arm}"
    logger.info("Running replay scenario %s", label)

    try:
        _, plan = expand_play_input(scenario.user_input)
        generated = generate_play_from_plan(
            plan=plan,
            chunks=inputs.chunks,
            config=scenario.config,
            critic=inputs.critic if scenario.config.use_critic else None,
            chooser=inputs.chooser if scenario.config.use_chooser else None,
            candidate_pool=inputs.candidate_pool,
            knobs=knobs,
        )
    except (ValueError, KeyError, FileNotFoundError, OSError) as exc:
        logger.exception("Scenario %s failed to generate", label)
        return ReplayResult(
            scenario_name=scenario.name,
            arm=arm,
            passed=False,
            failures=[],
            error=f"generation raised {type(exc).__name__}: {exc}",
        )

    run = play_run_from_generation(
        plan=plan,
        generated=generated,
        knobs=knobs,
        config=scenario.config.model_dump(),
    )
    scorecard = compute_scorecard(run, label=label)
    failures = evaluate_scorecard(scorecard, scenario.thresholds)

    scorecard_path: Optional[Path] = None
    if eval_dir is not None:
        try:
            scorecard_path = save_scorecard(scorecard, eval_dir)
        except OSError as exc:
            # A scorecard that cannot be written is a lost measurement, not a
            # failed scenario; the verdict itself is already computed.
            logger.error("Could not persist scorecard %s: %s", label, exc)

    return ReplayResult(
        scenario_name=scenario.name,
        arm=arm,
        passed=not failures,
        failures=failures,
        scorecard=scorecard,
        scorecard_path=scorecard_path,
    )


def run_replay_suite(
    scenarios: Optional[Sequence[ReplayScenario]] = None,
    inputs: Optional[GenerationInputs] = None,
    eval_dir: Optional[Path] = None,
    ab: bool = False,
) -> List[ReplayResult]:
    """Run every scenario and return one result per scenario per arm.

    Args:
        scenarios: Scenarios to run; defaults to ``build_default_scenarios()``.
        inputs: Generation handles; built from settings when omitted.
        eval_dir: Where to persist scorecards. Not written when None.
        ab: When True, run each scenario twice -- once with the knobs off (the
            pre-M1 control) and once with the configured knobs -- so the two
            scorecards are directly comparable.

    Returns:
        Results in run order. The caller decides what to do with failures; this
        function does not raise on them.
    """

    selected = list(scenarios) if scenarios is not None else build_default_scenarios()
    owns_inputs = inputs is None
    active_inputs = inputs if inputs is not None else build_generation_inputs()

    arms: List[Tuple[str, Optional[GuidanceKnobs]]] = (
        [(ARM_KNOBS_OFF, GuidanceKnobs.all_off()), (ARM_KNOBS_ON, GuidanceKnobs.from_settings())]
        if ab
        else [(ARM_KNOBS_ON, None)]
    )

    results: List[ReplayResult] = []
    try:
        for scenario in selected:
            for arm, knobs in arms:
                results.append(
                    run_scenario(
                        scenario=scenario,
                        inputs=active_inputs,
                        knobs=knobs,
                        arm=arm,
                        eval_dir=eval_dir,
                    )
                )
    finally:
        if owns_inputs:
            active_inputs.close()

    passed_count = sum(1 for result in results if result.passed)
    logger.info("Replay suite completed: %s/%s passed", passed_count, len(results))
    return results


def build_generation_inputs(use_critic: bool = False) -> GenerationInputs:
    """Open the corpus, the retrieval pool, and (optionally) the LLM handles.

    Retrieval is what carries Tier-2 metadata into scoring, so its absence is
    logged loudly rather than quietly degrading into a run whose meter metrics
    are all unmeasured.
    """

    settings = get_settings()
    inputs = GenerationInputs()

    if settings.retrieval_pool_size > 0:
        try:
            inputs.candidate_pool = CandidatePool(
                persist_dir=settings.chroma_dir,
                embedding_dimensions=settings.embedding_dimensions,
                pool_size=settings.retrieval_pool_size,
            )
        except (FileNotFoundError, ValueError) as exc:
            logger.error(
                "No usable candidate pool (%s). Falling back to the full processed "
                "corpus, which carries no Tier-2 metadata -- meter metrics will be "
                "unmeasured and any scenario requiring them will fail. Run "
                "`python -m shpoet.scripts.build_index` to fix this.",
                exc,
            )

    if inputs.candidate_pool is None:
        corpus = CorpusStore(settings.processed_dir)
        corpus.load()
        inputs.chunks = corpus.list_chunks()

    if use_critic:
        client = create_llm_client(settings.anthropic_api_key, settings.llm_model)
        inputs.critic, inputs.chooser = create_critic_and_chooser(
            client, use_chooser=settings.use_chooser
        )
        if inputs.critic is None:
            logger.warning("Critic requested but ANTHROPIC_API_KEY is not set; running without it")

    return inputs


def _apply_critic_choice(
    scenarios: Sequence[ReplayScenario],
    use_critic: bool,
) -> List[ReplayScenario]:
    """Return scenarios with their critic flag forced to the CLI's choice."""

    adjusted: List[ReplayScenario] = []
    for scenario in scenarios:
        config = scenario.config.model_copy(update={"use_critic": use_critic})
        adjusted.append(
            ReplayScenario(
                name=scenario.name,
                description=scenario.description,
                tags=list(scenario.tags),
                user_input=scenario.user_input,
                config=config,
                thresholds=scenario.thresholds,
            )
        )
    return adjusted


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the replay suite."""

    parser = argparse.ArgumentParser(
        description="Run fixed generation scenarios and score the results.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="Run only the named scenario. Repeatable.",
    )
    parser.add_argument(
        "--critic",
        action="store_true",
        help="Enable the Anthropic critic at checkpoints. Costs money per run.",
    )
    parser.add_argument(
        "--no-critic",
        action="store_true",
        help="Force the critic off (the default) for fast, free iteration.",
    )
    parser.add_argument(
        "--ab",
        action="store_true",
        help="Run each scenario twice: knobs off (pre-M1 control) then knobs on.",
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=None,
        help="Directory for scorecards (default: SHPOET_EVAL_DIR, else data/eval).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the replay suite as a CLI entry point.

    Returns:
        0 when every scenario passed, 1 otherwise. Non-zero is the contract the
        suite exists to provide: a seeded regression must be able to fail a build.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = _build_arg_parser().parse_args(argv)

    use_critic = args.critic and not args.no_critic
    eval_dir = args.eval_dir if args.eval_dir is not None else get_settings().eval_dir

    scenarios = build_default_scenarios()
    if args.scenario:
        wanted = set(args.scenario)
        scenarios = [scenario for scenario in scenarios if scenario.name in wanted]
        missing = wanted - {scenario.name for scenario in scenarios}
        if missing:
            print(f"Unknown scenario(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    scenarios = _apply_critic_choice(scenarios, use_critic)

    inputs = build_generation_inputs(use_critic=use_critic)
    try:
        results = run_replay_suite(
            scenarios=scenarios, inputs=inputs, eval_dir=eval_dir, ab=args.ab
        )
    finally:
        inputs.close()

    print()
    for result in results:
        if result.scorecard is not None:
            print(result.scorecard.describe())
            if result.scorecard_path is not None:
                print(f"  written to     {result.scorecard_path}")
        print(result.describe())
        print()

    failed = [result for result in results if not result.passed]
    print(f"{len(results) - len(failed)}/{len(results)} scenario runs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
