"""Tests for competition runner: post-processing, cycle grouping, weak filtering."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from crypto.src.kg.competition_runner import (
    CompetitionAnalysis,
    group_by_cycle_asset,
    run_competition_analysis,
    _raw_to_hypothesis,
    _WEAK_PLAUSIBILITY_THRESHOLD,
)
from crypto.src.kg.hypothesis import HypothesisNode


def _make_raw_card(card_id: str, claim: str, cycle: int = 0,
                   plausibility_prior: float = 0.7, **overrides) -> dict:
    base = {
        "card_id": card_id,
        "version": 1,
        "created_at": "2026-04-19T00:00:00Z",
        "title": claim[:40],
        "claim": claim,
        "mechanism": "test mechanism path",
        "evidence_nodes": ["n1", "n2"],
        "evidence_edges": ["e1"],
        "operator_trace": ["align", "compose"],
        "secrecy_level": "internal_watchlist",
        "validation_status": "untested",
        "scores": {
            "plausibility": plausibility_prior,
            "novelty": 0.5,
            "actionability": 0.7,
            "traceability": 0.8,
            "reproducibility": 0.5,
            "secrecy": 0.75,
        },
        "composite_score": 0.6,
        "run_id": "test_run",
        "kg_families": ["cross_asset"],
        "tags": ["correlation_break"],
        "actionability_note": None,
        "plausibility_prior": plausibility_prior,
        "_cycle": cycle,
    }
    base.update(overrides)
    return base


def _write_pipeline_out(tmpdir: str, cards_by_cycle: dict[int, list[dict]]) -> str:
    pipeline_out = os.path.join(tmpdir, "pipeline_out")
    for cycle, cards in cards_by_cycle.items():
        cycle_dir = os.path.join(pipeline_out, f"run_018_cycle_{cycle:03d}")
        os.makedirs(cycle_dir, exist_ok=True)
        with open(os.path.join(cycle_dir, "output_candidates.json"), "w") as f:
            json.dump(cards, f)
    return pipeline_out


class TestCycleAssetGrouping:
    def test_same_asset_different_cycles_separated(self):
        h1 = HypothesisNode(hypothesis_id="h1", claim="BTC test", family="cross_asset",
                            metadata={"asset": "BTC", "_cycle": 0})
        h2 = HypothesisNode(hypothesis_id="h2", claim="BTC test2", family="cross_asset",
                            metadata={"asset": "BTC", "_cycle": 1})
        groups = group_by_cycle_asset([h1, h2])
        assert "BTC:c000" in groups
        assert "BTC:c001" in groups
        assert len(groups) == 2

    def test_same_cycle_different_assets_separated(self):
        h1 = HypothesisNode(hypothesis_id="h1", claim="BTC", family="cross_asset",
                            metadata={"asset": "BTC", "_cycle": 0})
        h2 = HypothesisNode(hypothesis_id="h2", claim="ETH", family="cross_asset",
                            metadata={"asset": "ETH", "_cycle": 0})
        groups = group_by_cycle_asset([h1, h2])
        assert len(groups) == 2

    def test_same_asset_same_cycle_together(self):
        h1 = HypothesisNode(hypothesis_id="h1", claim="BTC a", family="cross_asset",
                            metadata={"asset": "BTC", "_cycle": 5})
        h2 = HypothesisNode(hypothesis_id="h2", claim="BTC b", family="cross_asset",
                            metadata={"asset": "BTC", "_cycle": 5})
        groups = group_by_cycle_asset([h1, h2])
        assert len(groups) == 1
        assert len(groups["BTC:c005"]) == 2


class TestWeakFiltering:
    def test_weak_card_filtered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [
                _make_raw_card("c1", "BTC strong correlation break", plausibility_prior=0.8),
                _make_raw_card("c2", "BTC weak correlation break", plausibility_prior=0.05,
                              evidence_nodes=[], evidence_edges=[], operator_trace=[]),
            ]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis = run_competition_analysis(pipeline_out, output_dir=os.path.join(tmpdir, "out"))
            assert analysis.n_filtered_weak == 1
            assert analysis.n_input_cards == 2

    def test_weak_candidates_saved_to_side_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [
                _make_raw_card("c1", "BTC strong", plausibility_prior=0.8),
                _make_raw_card("c2", "BTC weak", plausibility_prior=0.1),
            ]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            out_dir = os.path.join(tmpdir, "out")
            run_competition_analysis(pipeline_out, output_dir=out_dir)
            weak_path = os.path.join(out_dir, "weak_candidates.json")
            assert os.path.exists(weak_path)
            with open(weak_path) as f:
                weak = json.load(f)
            assert len(weak) == 1

    def test_all_weak_returns_empty_analysis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [
                _make_raw_card("c1", "BTC weak", plausibility_prior=0.1),
            ]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis = run_competition_analysis(pipeline_out)
            assert analysis.n_groups == 0


class TestRunCompetitionAnalysis:
    def test_end_to_end_with_cycle_grouping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {
                0: [_make_raw_card(f"c0_{i}", f"BTC correlation break pair {i}", cycle=0)
                    for i in range(3)],
                1: [_make_raw_card(f"c1_{i}", f"ETH correlation break pair {i}", cycle=1)
                    for i in range(3)],
            }
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis = run_competition_analysis(pipeline_out, group_fn="cycle_asset")
            assert analysis.n_groups >= 2
            for r in analysis.results:
                assert ":" in r.group_key

    def test_null_present_in_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [_make_raw_card("c1", "BTC break", cycle=0)]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis = run_competition_analysis(pipeline_out)
            all_families = set()
            for r in analysis.results:
                all_families.add(r.primary.family)
                for a in r.alternatives:
                    all_families.add(a.family)
            assert "null" in all_families

    def test_regime_decay_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [_make_raw_card("c1", "BTC break", cycle=0)]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis_cb = run_competition_analysis(pipeline_out, regime="correlation_break")
            analysis_rl = run_competition_analysis(pipeline_out, regime="resting_liquidity")
            # In resting_liquidity, cross_asset should be decayed
            if analysis_rl.results:
                r = analysis_rl.results[0]
                decayed = any(a.metadata.get("regime_decayed") for a in [r.primary] + r.alternatives)
                assert decayed

    def test_summary_table_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [_make_raw_card("c1", "BTC break", cycle=0)]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis = run_competition_analysis(pipeline_out)
            summary = analysis.summary_table()
            expected_keys = {"n_input_cards", "n_groups", "families_per_group_mean",
                             "null_win_pct", "confidence_median", "regime"}
            assert expected_keys.issubset(summary.keys())

    def test_output_files_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {0: [_make_raw_card("c1", "BTC break", cycle=0)]}
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            out_dir = os.path.join(tmpdir, "out")
            run_competition_analysis(pipeline_out, output_dir=out_dir)
            assert os.path.exists(os.path.join(out_dir, "competition_summary.json"))
            assert os.path.exists(os.path.join(out_dir, "competition_groups.json"))

    def test_groups_are_small_with_cycle_grouping(self):
        """Cycle-level grouping should produce small groups (not 200+ cards)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cards = {}
            for cy in range(10):
                cards[cy] = [_make_raw_card(f"c{cy}_{i}", f"BTC break pair {i}", cycle=cy)
                             for i in range(5)]
            pipeline_out = _write_pipeline_out(tmpdir, cards)
            analysis = run_competition_analysis(pipeline_out, group_fn="cycle_asset")
            for r in analysis.results:
                total = 1 + len(r.alternatives)
                assert total <= 15, f"Group {r.group_key} has {total} candidates, expected <= 15"
