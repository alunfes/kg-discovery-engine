"""Layer 4: Determinism tests.

Verifies that seed=42 produces identical top hypotheses across two
independent pipeline runs with the same configuration.

Why this matters: any time-dependent or unordered iteration that slips
in (e.g. dict insertion order, float precision differences) would cause
non-determinism that breaks reproducibility.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from crypto.src.pipeline import PipelineConfig, run_pipeline


def _run(seed: int = 42, n_minutes: int = 60, output_dir: str = "/tmp/det_test") -> list:
    cfg = PipelineConfig(
        run_id=f"det_run_{seed}",
        seed=seed,
        n_minutes=n_minutes,
        top_k=5,
        output_dir=output_dir,
    )
    return run_pipeline(cfg)


def test_same_seed_produces_same_top_hypothesis():
    """Running twice with seed=42 must yield the same #1 hypothesis title."""
    run1 = _run()
    run2 = _run()
    top1 = max(run1, key=lambda c: c.composite_score)
    top2 = max(run2, key=lambda c: c.composite_score)
    assert top1.title == top2.title, (
        f"Non-determinism detected:\n  run1: {top1.title}\n  run2: {top2.title}"
    )


def test_same_seed_produces_same_composite_scores():
    """All composite scores must be identical across two identical runs."""
    run1 = sorted(_run(), key=lambda c: c.title)
    run2 = sorted(_run(), key=lambda c: c.title)
    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2):
        assert c1.title == c2.title
        assert c1.composite_score == c2.composite_score


def test_different_seeds_produce_different_results():
    """Different seeds should yield at least one different hypothesis title."""
    run42 = {c.title for c in _run(seed=42)}
    run99 = {c.title for c in _run(seed=99)}
    # They may overlap partially, but shouldn't be identical sets
    assert run42 != run99 or len(run42) == 0, (
        "Two different seeds produced identical hypothesis sets — check RNG wiring"
    )


def test_hypothesis_titles_are_strings():
    """All hypothesis titles must be non-empty strings."""
    for card in _run():
        assert isinstance(card.title, str) and len(card.title) > 0


def test_hypothesis_composite_scores_in_range():
    """Composite scores must be in [0, 1]."""
    for card in _run():
        assert 0.0 <= card.composite_score <= 1.0, (
            f"Score out of range: {card.composite_score} for '{card.title}'"
        )
