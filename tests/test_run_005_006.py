"""Tests for Run 005/006: cohens_d, testability heuristic, budget control, fair comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.eval.scorer import (
    EvaluationRubric,
    _ABSTRACT_RELATIONS,
    _MEASURABLE_RELATIONS,
    _score_testability_heuristic,
    cohens_d,
    evaluate,
    score_category,
)
from src.kg.models import HypothesisCandidate, KGEdge, KGNode, KnowledgeGraph
from src.kg.toy_data import build_bio_chem_bridge_kg, build_biology_kg, build_chemistry_kg
from src.pipeline.operators import align, compose, difference, union
from src.pipeline.run_experiment import (
    _effect_size_label,
    _score_stats,
    run_005_fair_comparison,
    run_006_h3_evaluator_quality,
)


# ---------------------------------------------------------------------------
# cohens_d
# ---------------------------------------------------------------------------

class TestCohensD:
    def test_identical_groups_returns_zero(self):
        a = [0.7, 0.7, 0.7, 0.7]
        b = [0.7, 0.7, 0.7, 0.7]
        assert cohens_d(a, b) == 0.0

    def test_positive_when_a_higher(self):
        a = [0.8, 0.85, 0.82, 0.79, 0.83]
        b = [0.60, 0.65, 0.62, 0.59, 0.63]
        d = cohens_d(a, b)
        assert d > 0, "Cohen's d should be positive when group_a has higher mean"

    def test_negative_when_b_higher(self):
        a = [0.60, 0.62, 0.61]
        b = [0.80, 0.82, 0.81]
        d = cohens_d(a, b)
        assert d < 0

    def test_small_sample_returns_zero(self):
        assert cohens_d([0.7], [0.8]) == 0.0

    def test_empty_returns_zero(self):
        assert cohens_d([], [0.7, 0.8]) == 0.0
        assert cohens_d([0.7, 0.8], []) == 0.0

    def test_large_effect(self):
        # Groups with genuine variance and large separation
        a = [0.95, 0.90, 0.92, 0.91, 0.93, 0.94, 0.96, 0.90, 0.91, 0.92]
        b = [0.10, 0.12, 0.11, 0.13, 0.10, 0.11, 0.12, 0.10, 0.11, 0.10]
        d = cohens_d(a, b)
        assert d > 0.8, f"Expected large effect, got {d}"

    def test_zero_variance_returns_zero(self):
        # Both constant but different — pooled_std = 0, so returns 0.0 by convention
        assert cohens_d([1.0] * 5, [0.0] * 5) == 0.0

    def test_symmetry_magnitude(self):
        a = [0.8, 0.82, 0.81, 0.79, 0.80]
        b = [0.60, 0.62, 0.61, 0.59, 0.60]
        assert abs(cohens_d(a, b) + cohens_d(b, a)) < 1e-9


# ---------------------------------------------------------------------------
# score_category
# ---------------------------------------------------------------------------

class TestScoreCategory:
    def test_known_restatement(self):
        assert score_category(0.85) == "known_restatement"
        assert score_category(1.0) == "known_restatement"

    def test_promising(self):
        assert score_category(0.60) == "promising"
        assert score_category(0.75) == "promising"
        assert score_category(0.84) == "promising"

    def test_weak_speculative(self):
        assert score_category(0.40) == "weak_speculative"
        assert score_category(0.55) == "weak_speculative"

    def test_contradicted(self):
        assert score_category(0.0) == "contradicted"
        assert score_category(0.39) == "contradicted"


# ---------------------------------------------------------------------------
# _effect_size_label
# ---------------------------------------------------------------------------

class TestEffectSizeLabel:
    def test_negligible(self):
        assert _effect_size_label(0.0) == "negligible"
        assert _effect_size_label(0.1) == "negligible"

    def test_small(self):
        assert _effect_size_label(0.2) == "small"
        assert _effect_size_label(0.4) == "small"

    def test_medium(self):
        assert _effect_size_label(0.5) == "medium"
        assert _effect_size_label(0.7) == "medium"

    def test_large(self):
        assert _effect_size_label(0.8) == "large"
        assert _effect_size_label(2.0) == "large"


# ---------------------------------------------------------------------------
# Testability heuristic
# ---------------------------------------------------------------------------

def _make_candidate(provenance: list[str], subj_id: str = "bio:A", obj_id: str = "bio:B") -> HypothesisCandidate:
    return HypothesisCandidate(
        id="T001",
        subject_id=subj_id,
        relation="transitively_related_to",
        object_id=obj_id,
        description="test",
        provenance=provenance,
        operator="compose",
        source_kg_name="test",
    )


def _make_kg_with_nodes(*node_ids: str) -> KnowledgeGraph:
    kg = KnowledgeGraph(name="test")
    for nid in node_ids:
        domain = nid.split(":")[0] if ":" in nid else "unknown"
        kg.add_node(KGNode(nid, nid, domain))
    return kg


class TestTestabilityHeuristic:
    def test_all_measurable_concrete_nodes(self):
        prov = ["bio:A", "inhibits", "bio:B", "activates", "bio:C"]
        cand = _make_candidate(prov, "bio:A", "bio:C")
        kg = _make_kg_with_nodes("bio:A", "bio:B", "bio:C")
        score = _score_testability_heuristic(cand, kg)
        assert score == 0.9, f"Expected 0.9 (all measurable + concrete), got {score}"

    def test_all_abstract_concrete_nodes(self):
        prov = ["bio:A", "relates_to", "bio:B", "associated_with", "bio:C"]
        cand = _make_candidate(prov, "bio:A", "bio:C")
        kg = _make_kg_with_nodes("bio:A", "bio:B", "bio:C")
        score = _score_testability_heuristic(cand, kg)
        assert score == 0.5, f"Expected 0.5 (all abstract + concrete bonus), got {score}"

    def test_all_abstract_bridge_nodes(self):
        prov = ["bridge:A", "relates_to", "bridge:B"]
        cand = _make_candidate(prov, "bridge:A", "bridge:B")
        kg = _make_kg_with_nodes("bridge:A", "bridge:B")
        score = _score_testability_heuristic(cand, kg)
        assert score == 0.4, f"Expected 0.4 (all abstract, no concrete bonus), got {score}"

    def test_majority_measurable(self):
        prov = ["bio:A", "inhibits", "bio:B", "relates_to", "bio:C"]
        cand = _make_candidate(prov, "bio:A", "bio:C")
        kg = _make_kg_with_nodes("bio:A", "bio:B", "bio:C")
        score = _score_testability_heuristic(cand, kg)
        # 1 measurable / 2 total = 0.5 ratio → satisfies ">= 0.5" → base=0.7 + concrete=0.8
        assert score == 0.8

    def test_no_provenance_returns_half(self):
        cand = _make_candidate([], "bio:A", "bio:B")
        kg = _make_kg_with_nodes("bio:A", "bio:B")
        score = _score_testability_heuristic(cand, kg)
        assert score == 0.5

    def test_score_range(self):
        """Heuristic must stay within 0.4–0.9."""
        import random
        rng = random.Random(42)
        relations = list(_MEASURABLE_RELATIONS) + list(_ABSTRACT_RELATIONS)
        for _ in range(50):
            chosen = [rng.choice(relations) for _ in range(rng.randint(1, 4))]
            prov = ["bio:A"]
            for r in chosen:
                prov += [r, "bio:B"]
            cand = _make_candidate(prov, "bio:A", "bio:B")
            kg = _make_kg_with_nodes("bio:A", "bio:B")
            s = _score_testability_heuristic(cand, kg)
            assert 0.4 <= s <= 0.9, f"Out of range: {s} (relations={chosen})"


# ---------------------------------------------------------------------------
# EvaluationRubric flags
# ---------------------------------------------------------------------------

class TestRubricFlags:
    def test_cross_domain_bonus_true_gives_higher_novelty(self):
        """With bonus=True, cross-domain cand should score higher novelty."""
        bridge_kg = build_bio_chem_bridge_kg()
        candidates = compose(bridge_kg)
        rubric_with = EvaluationRubric(cross_domain_novelty_bonus=True)
        rubric_without = EvaluationRubric(cross_domain_novelty_bonus=False)
        scored_with = evaluate(candidates, bridge_kg, rubric_with)
        scored_without = evaluate(candidates, bridge_kg, rubric_without)
        mean_with = sum(s.novelty for s in scored_with) / max(len(scored_with), 1)
        mean_without = sum(s.novelty for s in scored_without) / max(len(scored_without), 1)
        assert mean_with >= mean_without, "Bonus=True should not lower novelty"

    def test_testability_heuristic_varies(self):
        """Heuristic testability should not always return 0.6."""
        bridge_kg = build_bio_chem_bridge_kg()
        candidates = compose(bridge_kg)
        rubric = EvaluationRubric(testability_heuristic=True)
        scored = evaluate(candidates, bridge_kg, rubric)
        testability_values = {s.testability for s in scored}
        # Should have at least 2 distinct values (vs constant 0.6)
        assert len(testability_values) > 1, (
            f"Expected varied testability, got only {testability_values}"
        )

    def test_default_rubric_backward_compatible(self):
        """Default rubric must behave exactly as before Run 006."""
        bio_kg = build_biology_kg()
        candidates = compose(bio_kg)
        rubric = EvaluationRubric()
        scored = evaluate(candidates, bio_kg, rubric)
        # All testability scores must be 0.6 under default
        for s in scored:
            assert s.testability == 0.6, f"Expected 0.6, got {s.testability}"


# ---------------------------------------------------------------------------
# Budget control (_score_stats)
# ---------------------------------------------------------------------------

class TestScoreStats:
    def test_empty_returns_n_zero(self):
        assert _score_stats([]) == {"n": 0}

    def test_stats_correctness(self):
        bio_kg = build_biology_kg()
        candidates = compose(bio_kg)
        rubric = EvaluationRubric()
        scored = evaluate(candidates, bio_kg, rubric)
        stats = _score_stats(scored)
        assert stats["n"] == len(scored)
        assert 0.0 <= stats["min_total"] <= stats["max_total"] <= 1.0
        assert stats["min_total"] <= stats["mean_total"] <= stats["max_total"]
        assert "category_distribution" in stats
        assert "promising_ratio" in stats

    def test_promising_ratio_in_range(self):
        bio_kg = build_biology_kg()
        scored = evaluate(compose(bio_kg), bio_kg, EvaluationRubric())
        stats = _score_stats(scored)
        assert 0.0 <= stats["promising_ratio"] <= 1.0


# ---------------------------------------------------------------------------
# run_005_fair_comparison
# ---------------------------------------------------------------------------

class TestRun005:
    def test_returns_expected_keys(self):
        result = run_005_fair_comparison()
        for key in ("run", "budget_n", "c1_stats", "c2_stats", "cohens_d",
                    "effect_size_label", "h1_verdict"):
            assert key in result, f"Missing key: {key}"

    def test_budget_n_positive(self):
        result = run_005_fair_comparison()
        assert result["budget_n"] > 0

    def test_budget_n_equals_min_of_totals(self):
        result = run_005_fair_comparison()
        assert result["budget_n"] == min(
            result["c1_total_candidates"],
            result["c2_total_candidates"],
        )

    def test_stats_n_equals_budget(self):
        result = run_005_fair_comparison()
        assert result["c1_stats"]["n"] == result["budget_n"]
        assert result["c2_stats"]["n"] == result["budget_n"]

    def test_h1_verdict_has_required_keys(self):
        result = run_005_fair_comparison()
        h1 = result["h1_verdict"]
        assert "pass" in h1
        assert "cohens_d" in h1
        assert "effect_size_label" in h1

    def test_cohens_d_is_float(self):
        result = run_005_fair_comparison()
        assert isinstance(result["cohens_d"], float)


# ---------------------------------------------------------------------------
# run_006_h3_evaluator_quality
# ---------------------------------------------------------------------------

class TestRun006:
    def test_returns_expected_keys(self):
        result = run_006_h3_evaluator_quality()
        for key in ("run", "h3_standard_scorer", "h3_no_bonus", "h3_verdict",
                    "testability_distribution", "score_discrimination"):
            assert key in result, f"Missing key: {key}"

    def test_testability_std_not_zero_in_r6(self):
        """Heuristic scorer must produce non-zero testability std."""
        result = run_006_h3_evaluator_quality()
        assert result["testability_distribution"]["r6_std"] > 0.0

    def test_standard_testability_std_is_zero(self):
        """Standard scorer produces constant testability → std = 0."""
        result = run_006_h3_evaluator_quality()
        assert result["testability_distribution"]["standard_std"] == 0.0

    def test_h3_no_bonus_ratio_is_float(self):
        result = run_006_h3_evaluator_quality()
        assert isinstance(result["h3_no_bonus"]["ratio"], float)

    def test_cross_domain_inherently_superior_key_present(self):
        result = run_006_h3_evaluator_quality()
        assert "cross_domain_inherently_superior" in result["h3_verdict"]
