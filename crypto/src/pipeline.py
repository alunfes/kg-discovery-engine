"""End-to-end KG discovery pipeline.

Entry point: run_pipeline(config) → list[HypothesisCard]

Data flow:
  SyntheticGenerator
    → raw ticks (price, trade, funding, book)
    → StateExtractor (per asset)
      → MarketStateCollections
        → 5 KG builders (micro, cross_asset, execution, regime, pair)
          → Operators (align → union → compose → difference → rank)
            → Raw hypothesis candidates
              → Scorer
                → HypothesisCards
                  → Inventory
                    → JSON output
"""

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
from .eval.contradiction_metrics import (
    compute_contradiction_metrics,
    compute_conflict_adjusted_ranking,
)
from .eval.decision_tier import compute_decision_tiers
from .eval.confusion_matrix import compute_confusion_matrix
from .eval.generator import generate_hypotheses
from .eval.metrics import compute_branch_metrics
from .eval.persistence_tracker import compute_persistence_snapshot
from .eval.rerouter import compute_reroute_candidates, reroute_summary
from .eval.scorer import score_hypothesis
from .eval.uplift_ranker import compute_uplift_aware_ranking
from .eval.outcome_tracker import compute_watchlist_outcomes, compute_tier_recommendations
from .eval.monitoring_budget import build_allocation_table_from_outcomes
from .eval.watchlist_semantics import compute_watchlist_semantics
from .kg.chain_grammar import build_chain_grammar_kg
from .ingestion.synthetic import SyntheticDataset, SyntheticGenerator
=======
from .eval.generator import generate_hypotheses
from .eval.scorer import score_hypothesis
from .ingestion.synthetic import SyntheticGenerator
>>>>>>> claude/thirsty-heisenberg
=======
from .eval.generator import generate_hypotheses
from .eval.scorer import score_hypothesis
from .ingestion.synthetic import SyntheticGenerator
>>>>>>> claude/elated-lamarr
=======
from .eval.generator import generate_hypotheses
from .eval.metrics import compute_branch_metrics
from .eval.scorer import score_hypothesis
from .kg.chain_grammar import build_chain_grammar_kg
from .ingestion.synthetic import SyntheticGenerator
>>>>>>> claude/gracious-edison
from .inventory.store import HypothesisInventory
from .kg.base import KGraph
from .kg.cross_asset import build_cross_asset_kg
from .kg.execution import build_execution_kg
from .kg.microstructure import build_microstructure_kg
from .kg.pair import build_pair_kg
from .kg.regime import build_regime_kg
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
from .kg.temporal_guard import annotate_temporal_quality
=======
>>>>>>> claude/thirsty-heisenberg
=======
from .kg.temporal_guard import annotate_temporal_quality
>>>>>>> claude/elated-lamarr
=======
from .kg.temporal_guard import annotate_temporal_quality
>>>>>>> claude/gracious-edison
from .operators.ops import align, compose, difference, rank, union
from .states.extractor import extract_states


@dataclass
class PipelineConfig:
    """Configuration for one pipeline run.

    Why a dataclass not a plain dict: type safety and named access
    make the config self-documenting and IDE-friendly.
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD

    dataset: Optional pre-built SyntheticDataset. When provided, the
      synthetic generator step is skipped and this dataset is used instead.
      Used by Run 017 shadow deployment to inject real Hyperliquid data.
      None (default) → standard synthetic generation via SyntheticGenerator.
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
    """

    run_id: str
    seed: int = 42
    n_minutes: int = 60
    assets: Optional[list[str]] = None
    top_k: int = 10
    output_dir: str = "crypto/artifacts/runs"
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    dataset: Optional[SyntheticDataset] = None
    real_data_mode: bool = False  # Sprint R: activate real-data threshold presets
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison


def run_pipeline(config: PipelineConfig) -> list:
    """Execute the full KG discovery pipeline.

    Args:
        config: PipelineConfig controlling seed, duration, assets, output.

    Returns:
        List of HypothesisCard objects (also saved to output_dir).
    """
    random.seed(config.seed)

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    # 1. Data source: pre-built real dataset (Run 017 shadow) or synthetic.
    # Why conditional: Run 017 injects a real SyntheticDataset built from
    # Hyperliquid API data. All downstream code is unchanged — the same
    # extract_states() and KG builders consume both data sources identically.
    if config.dataset is not None:
        dataset = config.dataset
    else:
        generator = SyntheticGenerator(
            seed=config.seed,
            n_minutes=config.n_minutes,
            assets=config.assets,
        )
        dataset = generator.generate()
=======
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
    # 1. Synthetic data generation
    generator = SyntheticGenerator(
        seed=config.seed,
        n_minutes=config.n_minutes,
        assets=config.assets,
    )
    dataset = generator.generate()
<<<<<<< HEAD
<<<<<<< HEAD
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison

    assets = config.assets or ["HYPE", "ETH", "BTC", "SOL"]

    # 2. State extraction (per asset)
    collections = {}
    for asset in assets:
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        collections[asset] = extract_states(
            dataset, asset, config.run_id,
            real_data_mode=config.real_data_mode,
        )
=======
        collections[asset] = extract_states(dataset, asset, config.run_id)
>>>>>>> claude/thirsty-heisenberg
=======
        collections[asset] = extract_states(dataset, asset, config.run_id)
>>>>>>> claude/elated-lamarr
=======
        collections[asset] = extract_states(dataset, asset, config.run_id)
>>>>>>> claude/gracious-edison

    # 3. KG construction (per family)
    micro_kgs = {a: build_microstructure_kg(collections[a]) for a in assets}
    execution_kgs = {a: build_execution_kg(collections[a]) for a in assets}
    regime_kgs = {a: build_regime_kg(collections[a]) for a in assets}
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    cross_kg = build_cross_asset_kg(collections, dataset=dataset)
=======
    cross_kg = build_cross_asset_kg(collections)
>>>>>>> claude/thirsty-heisenberg
=======
    cross_kg = build_cross_asset_kg(collections, dataset=dataset)
>>>>>>> claude/elated-lamarr
=======
    cross_kg = build_cross_asset_kg(collections, dataset=dataset)
>>>>>>> claude/gracious-edison
    pair_kg = build_pair_kg(collections)

    # 4. Merge all per-asset micro KGs into one
    merged_micro = _merge_kgs(list(micro_kgs.values()), "microstructure_all")
    merged_exec = _merge_kgs(list(execution_kgs.values()), "execution_all")
    merged_regime = _merge_kgs(list(regime_kgs.values()), "regime_all")

    # 5. Operator chain: align → union → compose → difference → rank
    #    align: micro ↔ execution on "asset" attribute
    aligned_kg = align(merged_micro, merged_exec, "symbol")

    #    union: add cross-asset and pair families
    full_kg = union(union(union(aligned_kg, cross_kg), pair_kg), merged_regime)

    #    compose: surface transitive aggression_predicts_funding chains
    composed_kg = compose(full_kg, "aggression_predicts_funding")

    #    difference: find structure unique to the composed (vs aligned-only)
    novel_kg = difference(composed_kg, aligned_kg)

    #    Final working KG for hypothesis generation: full + novel
    working_kg = union(full_kg, novel_kg)

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/gracious-edison
    # E: Build chain grammar KG (E1 beta_reversion + E2 positioning_unwind nodes).
    # Must run on the working_kg so it can see all micro/cross_asset nodes.
    grammar_kg, suppression_log = build_chain_grammar_kg(working_kg, collections)
    working_kg = union(working_kg, grammar_kg)

<<<<<<< HEAD
    # Run 012: boundary-case detection (pre-adjudication warning for near-threshold
    # activations where regime signals contradict the expected outcome).
    # Stored in branch_metrics below so it travels with all other run artifacts.
    from .eval.boundary_detector import BoundaryDetector, record_to_dict, warning_to_dict
    _bd = BoundaryDetector()
    _boundary_records = _bd.detect_from_kg(grammar_kg, suppression_log, working_kg, collections)
    _boundary_warnings = _bd.generate_warnings(_boundary_records)

=======
>>>>>>> claude/gracious-edison
    # Count corr_break pairs for branch_activation_rate metric.
    n_corr_break_pairs = sum(
        1 for n in cross_kg.nodes.values()
        if n.node_type == "CorrelationNode" and n.attributes.get("is_break")
    )

<<<<<<< HEAD
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
    # B2: Annotate all edges with temporal_valid flag (in-place).
    # Edges where source.observable_time >= target.event_time get temporal_valid=False.
    # The scorer can use this to penalise look-ahead hypotheses.
    annotate_temporal_quality(working_kg)

<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
    # 6. Hypothesis generation
    inventory = HypothesisInventory()
    raw_candidates = generate_hypotheses(working_kg)

    # 7. Rank candidates (lightweight pre-filter before full scoring)
    def quick_score(raw: dict) -> float:
        return float(raw.get("plausibility_prior", 0.5))

    top_candidates = rank(raw_candidates, quick_score, top_k=config.top_k * 2)

    # 8. Score → HypothesisCard (with novelty computed against growing inventory)
    cards = []
    for raw in top_candidates[:config.top_k]:
        card = score_hypothesis(raw, working_kg, inventory, config.run_id)
        inventory.add(card)
        cards.append(card)

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/gracious-edison
    # 9. Persist outputs (includes branch_metrics.json)
    branch_metrics = compute_branch_metrics(
        cards, suppression_log, n_corr_break_pairs, top_k=config.top_k
    )
<<<<<<< HEAD

    # H1: Count soft-gated cards (border cases that fired due to soft activation)
    n_soft_gated = sum(1 for c in cards if "soft_gated" in c.tags)
    branch_metrics["h1_soft_gate"] = {
        "n_soft_gated_cards": n_soft_gated,
        "soft_gated_fraction": round(n_soft_gated / max(len(cards), 1), 4),
        "soft_gate_min": 0.30,
        "hard_gate_min": 0.50,
    }

    # G1: Compute per-card contradiction metrics and conflict-adjusted ranking.
    # cross_kg is kept in scope from step 3 so we can look up corr_break_score.
    contradiction_data = compute_contradiction_metrics(
        cards, suppression_log, cross_kg
    )
    meta_scores = {
        d["card_id"]: d["meta_score"]
        for d in branch_metrics.get("normalized_ranking", {}).get(
            "normalized_cards", []
        )
    }
    conflict_ranking = compute_conflict_adjusted_ranking(
        cards, contradiction_data, meta_scores, top_k=config.top_k
    )
    branch_metrics["g1_contradiction_metrics"] = contradiction_data
    branch_metrics["g1_conflict_adjusted_ranking"] = conflict_ranking

    # H2: Contradiction-driven rerouting
    reroutes = compute_reroute_candidates(
        cards, contradiction_data, suppression_log, top_k=config.top_k
    )
    branch_metrics["h2_reroute_candidates"] = reroutes
    branch_metrics["h2_reroute_summary"] = reroute_summary(reroutes, config.top_k)

    # H3: Uplift-aware ranking
    g3_pool = branch_metrics.get("matched_baseline_pool", {})
    uplift_ranking = compute_uplift_aware_ranking(
        cards, contradiction_data, meta_scores, g3_pool, top_k=config.top_k
    )
    branch_metrics["h3_uplift_ranking"] = uplift_ranking

    # I1: Decision tiering — assign tier to each hypothesis card
    i1_tiers = compute_decision_tiers(
        cards,
        contradiction_data,
        meta_scores,
        g3_pool,
        reroutes,
    )
    branch_metrics["i1_decision_tiers"] = i1_tiers

    # I2: Temporal persistence / promotion tracking (first run → no prior state)
    # Why no prior_state here: pipeline is single-run; cross-run state is
    # tracked by the caller or offline analysis tools.  The snapshot establishes
    # the run_007+ baseline for future diff comparisons.
    i2_persistence = compute_persistence_snapshot(
        run_id=config.run_id,
        cards=cards,
        tier_assignments=i1_tiers["tier_assignments"],
        reroute_candidates=reroutes,
        baseline_pool=g3_pool,
    )
    branch_metrics["i2_persistence"] = i2_persistence

    # I3: Grammar confusion matrix — from reroute records + suppression log
    i3_confusion = compute_confusion_matrix(reroutes, suppression_log, contradiction_data)
    branch_metrics["i3_confusion_matrix"] = i3_confusion

    # I4: Watchlist semantics — watch label per branch/tier
    i4_watchlist = compute_watchlist_semantics(
        i1_tiers["tier_assignments"],
        cards,
    )
    branch_metrics["i4_watchlist"] = i4_watchlist

    # I5: Outcome tracking — evaluate whether watchlist predictions materialized
    # within the synthetic outcome window (second half of simulation).
    # Uses observation midpoint = n_minutes // 2 as the card generation proxy.
    i5_outcomes = compute_watchlist_outcomes(
        run_id=config.run_id,
        watchlist_cards=i4_watchlist["watchlist_cards"],
        dataset=dataset,
        collections=collections,
        n_minutes=config.n_minutes,
    )
    i5_outcomes["threshold_recommendations"] = compute_tier_recommendations(
        i5_outcomes["tier_comparison"]
    )
    branch_metrics["i5_outcome_tracking"] = i5_outcomes

    # Run 015: monitoring budget allocation — value density per (tier, family) group
    # and 3-strategy budget simulation. Uses in-memory i5 outcome_records so no
    # CSV I/O is needed mid-run (see build_allocation_table_from_outcomes docstring).
    branch_metrics["run015_monitoring_budget"] = build_allocation_table_from_outcomes(
        i5_outcomes["outcome_records"]
    )

    # Run 012: attach boundary detection results to branch_metrics
    branch_metrics["run012_boundary_detection"] = {
        "records": [record_to_dict(r) for r in _boundary_records],
        "warnings": [warning_to_dict(w) for w in _boundary_warnings],
        "n_records": len(_boundary_records),
        "n_warnings": len(_boundary_warnings),
        "high_warnings": sum(1 for w in _boundary_warnings if w.warning_level == "high"),
    }

    _save_outputs(config, cards, inventory, branch_metrics)
=======
    # 9. Persist outputs
    _save_outputs(config, cards, inventory)
>>>>>>> claude/thirsty-heisenberg
=======
    # 9. Persist outputs
    _save_outputs(config, cards, inventory)
>>>>>>> claude/elated-lamarr
=======
    _save_outputs(config, cards, inventory, branch_metrics)
>>>>>>> claude/gracious-edison

    return cards


<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
def run_oi_ablation(config: PipelineConfig) -> dict:
    """G2: Run three OI ablation variants and compare branch metrics.

    Variants:
      full                  — standard pipeline (no modification)
      no_OI_features        — oi_states zeroed before chain grammar build
      OI_only_downweighted  — oi_states state_score scaled by 0.5

    Purpose: determine whether OI is an essential structural signal or
    merely a ranking backbone.  If no_OI_features metrics resemble full,
    OI is not load-bearing; if metrics diverge, OI is essential.

    Returns:
        Dict with per-variant branch metrics and a diff summary.
    """
    import dataclasses
    from copy import deepcopy
    from .schema.market_state import OIState

    random.seed(config.seed)
    generator = SyntheticGenerator(
        seed=config.seed,
        n_minutes=config.n_minutes,
        assets=config.assets,
    )
    dataset = generator.generate()
    assets = config.assets or ["HYPE", "ETH", "BTC", "SOL"]
    base_collections = {
        a: extract_states(dataset, a, config.run_id) for a in assets
    }

    def _strip_oi(colls: dict) -> dict:
        """Return collections with oi_states replaced by empty list."""
        result = {}
        for asset, coll in colls.items():
            c = deepcopy(coll)
            c.oi_states = []
            result[asset] = c
        return result

    def _downweight_oi(colls: dict, weight: float) -> dict:
        """Return collections with OIState.state_score scaled by weight."""
        result = {}
        for asset, coll in colls.items():
            c = deepcopy(coll)
            c.oi_states = [
                dataclasses.replace(s, state_score=round(s.state_score * weight, 4))
                for s in c.oi_states
            ]
            result[asset] = c
        return result

    def _run_variant(colls: dict, label: str) -> dict:
        random.seed(config.seed)
        micro_kgs = {a: build_microstructure_kg(colls[a]) for a in assets}
        exec_kgs = {a: build_execution_kg(colls[a]) for a in assets}
        regime_kgs = {a: build_regime_kg(colls[a]) for a in assets}
        cross_kg = build_cross_asset_kg(colls, dataset=dataset)
        pair_kg = build_pair_kg(colls)
        merged_micro = _merge_kgs(list(micro_kgs.values()), "microstructure_all")
        merged_exec = _merge_kgs(list(exec_kgs.values()), "execution_all")
        merged_regime = _merge_kgs(list(regime_kgs.values()), "regime_all")
        aligned = align(merged_micro, merged_exec, "symbol")
        full = union(union(union(aligned, cross_kg), pair_kg), merged_regime)
        composed = compose(full, "aggression_predicts_funding")
        novel = difference(composed, aligned)
        working = union(full, novel)
        grammar_kg, supp_log = build_chain_grammar_kg(working, colls)
        working = union(working, grammar_kg)
        annotate_temporal_quality(working)
        inv = HypothesisInventory()
        raw = generate_hypotheses(working)

        def _qs(r: dict) -> float:
            return float(r.get("plausibility_prior", 0.5))

        top = rank(raw, _qs, top_k=config.top_k * 2)
        cards = []
        for r in top[:config.top_k]:
            card = score_hypothesis(r, working, inv, config.run_id)
            inv.add(card)
            cards.append(card)
        n_pairs = sum(
            1 for n in cross_kg.nodes.values()
            if n.node_type == "CorrelationNode" and n.attributes.get("is_break")
        )
        metrics = compute_branch_metrics(cards, supp_log, n_pairs, config.top_k)
        return {
            "variant": label,
            "branch_entropy": metrics["branch_entropy"],
            "top_k_branch_share": metrics["top_k_branch_share"],
            "mean_score_by_branch": metrics["mean_score_by_branch"],
            "branch_distribution": metrics["branch_distribution"],
            "total_cards": metrics["total_cards"],
        }

    full_result = _run_variant(base_collections, "full")
    no_oi_result = _run_variant(_strip_oi(base_collections), "no_OI_features")
    dw_result = _run_variant(
        _downweight_oi(base_collections, 0.5), "OI_only_downweighted"
    )

    return {
        "full": full_result,
        "no_OI_features": no_oi_result,
        "OI_only_downweighted": dw_result,
        "entropy_diff_no_oi": round(
            no_oi_result["branch_entropy"] - full_result["branch_entropy"], 4
        ),
        "entropy_diff_downweighted": round(
            dw_result["branch_entropy"] - full_result["branch_entropy"], 4
        ),
    }


=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
def _merge_kgs(kgs: list[KGraph], family_name: str) -> KGraph:
    """Merge a list of KGs via successive union operations."""
    if not kgs:
        return KGraph(family=family_name)
    result = kgs[0]
    for kg in kgs[1:]:
        result = union(result, kg)
    result.family = family_name
    return result


def _save_outputs(
    config: PipelineConfig,
    cards: list,
    inventory: HypothesisInventory,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/gracious-edison
    branch_metrics: dict,
) -> None:
    """Write run config, hypothesis cards, branch metrics, and review memo."""
    run_dir = os.path.join(config.output_dir, f"{config.run_id}")
<<<<<<< HEAD
=======
=======
>>>>>>> claude/elated-lamarr
) -> None:
    """Write run config, hypothesis cards, and review memo to output_dir."""
    run_dir = os.path.join(
        config.output_dir,
        f"{config.run_id}",
    )
<<<<<<< HEAD
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
    os.makedirs(run_dir, exist_ok=True)

    # run_config.json
    run_config = {
        "run_id": config.run_id,
        "seed": config.seed,
        "n_minutes": config.n_minutes,
        "assets": config.assets or ["HYPE", "ETH", "BTC", "SOL"],
        "top_k": config.top_k,
        "created_at": datetime.now(timezone.utc).isoformat(),
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
        "sprint": "J",
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
        "sprint": "E",
>>>>>>> claude/gracious-edison
    }
    with open(os.path.join(run_dir, "run_config.json"), "w") as f:
        json.dump(run_config, f, indent=2)

    # output_candidates.json
    inventory.save(os.path.join(run_dir, "output_candidates.json"))

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    # branch_metrics.json — E3 + H1/H2/H3 + I1/I2/I3/I4
    with open(os.path.join(run_dir, "branch_metrics.json"), "w") as f:
        json.dump(branch_metrics, f, indent=2)

    # h2_reroute_candidates.json
    with open(os.path.join(run_dir, "h2_reroute_candidates.json"), "w") as f:
        json.dump(branch_metrics.get("h2_reroute_candidates", []), f, indent=2)

    # h3_uplift_ranking.json
    with open(os.path.join(run_dir, "h3_uplift_ranking.json"), "w") as f:
        json.dump(branch_metrics.get("h3_uplift_ranking", {}), f, indent=2)

    # i1_decision_tiers.json
    with open(os.path.join(run_dir, "i1_decision_tiers.json"), "w") as f:
        json.dump(branch_metrics.get("i1_decision_tiers", {}), f, indent=2)

    # i4_watchlist.json
    with open(os.path.join(run_dir, "i4_watchlist.json"), "w") as f:
        json.dump(branch_metrics.get("i4_watchlist", {}), f, indent=2)

    # i5_outcome_tracking.json + watchlist_outcomes.csv (Run 013)
    i5 = branch_metrics.get("i5_outcome_tracking", {})
    if i5:
        with open(os.path.join(run_dir, "i5_outcome_tracking.json"), "w") as f:
            json.dump(i5, f, indent=2)
        _write_outcomes_csv(i5, os.path.join(run_dir, "watchlist_outcomes.csv"))

=======
    # branch_metrics.json — E3
    with open(os.path.join(run_dir, "branch_metrics.json"), "w") as f:
        json.dump(branch_metrics, f, indent=2)

>>>>>>> claude/gracious-edison
    # review_memo.md
    _write_review_memo(run_dir, config, cards, branch_metrics)


<<<<<<< HEAD
def _write_outcomes_csv(i5: dict, csv_path: str) -> None:
    """Write i5_outcome_tracking outcome records to a CSV file.

    Args:
        i5: i5_outcome_tracking dict from branch_metrics.
        csv_path: Absolute path for the output CSV file.
    """
    import csv as _csv
    records = i5.get("outcome_records", [])
    if not records:
        return
    fieldnames = [
        "card_id", "title", "branch", "decision_tier", "watch_label",
        "composite_score", "assets_mentioned", "expected_events",
        "outcome_result", "time_to_outcome_min", "half_life_min",
        "half_life_remaining_min", "outcome_type_match", "matched_event",
        "outcome_detail",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = _csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = dict(r)
            row["assets_mentioned"] = "|".join(row.get("assets_mentioned") or [])
            row["expected_events"] = "|".join(row.get("expected_events") or [])
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _g1_memo_lines(branch_metrics: dict) -> list[str]:
    """G1 section for review memo: conflict-adjusted ranking summary."""
    cr = branch_metrics.get("g1_conflict_adjusted_ranking", {})
    summary = cr.get("summary", {})
    shifted = cr.get("conflict_shifted_examples", [])
    lines = [
        "",
        "## G1: Conflict-Adjusted Ranking",
        "",
        f"- mean_abs_conflict_vs_raw_diff: {summary.get('mean_abs_conflict_vs_raw_diff', 'N/A')}",
        f"- max_conflict_vs_raw_diff: {summary.get('max_conflict_vs_raw_diff', 'N/A')}",
        f"- n_top_k_changed_by_conflict: {summary.get('n_top_k_changed_by_conflict', 'N/A')}",
        "- Top contradiction-shifted examples (fell most in conflict ranking):",
    ] + [
        f"  - [{d.get('branch','?')}] {d.get('title','')[:50]} "
        f"raw_rank={d.get('raw_rank')} → conflict_rank={d.get('conflict_rank')} "
        f"(Δ={d.get('rank_diff_conflict_vs_raw',0)}, "
        f"severity={d.get('contradiction_severity',0):.2f})"
        for d in shifted
    ]
    return lines


def _g3_memo_lines(branch_metrics: dict) -> list[str]:
    """G3 section for review memo: matched baseline pool summary."""
    pool = branch_metrics.get("matched_baseline_pool", {})
    top = pool.get("top_uplift", [])
    mean_uplift = pool.get("mean_uplift_by_branch", {})
    lines = [
        "",
        "## G3: Matched Baseline Pool",
        "",
        f"- n_matched: {pool.get('n_matched', 0)}",
        f"- n_pair_matched: {pool.get('n_pair_matched', 0)}",
        f"- global_baseline_score: {pool.get('global_baseline_score', 'N/A')}",
        f"- mean_uplift_by_branch: {mean_uplift}",
        "- top_uplift (complexity-adjusted):",
    ] + [
        f"  - [{d.get('branch','?')}] {d.get('title','')[:50]} "
        f"uplift={d.get('complexity_adjusted_uplift',0):.4f} "
        f"conf={d.get('uplift_confidence','?')}"
        for d in top
    ]
    return lines




def _h2_memo_lines(branch_metrics: dict) -> list[str]:
    """H2 section for review memo: reroute candidate summary."""
    summary = branch_metrics.get("h2_reroute_summary", {})
    tops = summary.get("top_reroutes", [])
    lines = [
        "",
        "## H2: Contradiction-Driven Rerouting",
        "",
        f"- n_rerouted: {summary.get('n_rerouted', 0)}",
        f"- branch_distribution: {summary.get('branch_distribution', {})}",
        f"- mean_delta: {summary.get('mean_delta', 0.0):.4f}",
        "- top_reroutes:",
    ] + [
        f"  - [{r.get('original_branch','?')}→{r.get('reroute_candidate_branch','?')}] "
        f"{r.get('original_title','')[:50]} "
        f"orig={r.get('original_score',0):.3f} → rerouted={r.get('rerouted_score',0):.3f} "
        f"(Δ={r.get('original_branch_vs_rerouted_score',0):+.3f}) "
        f"conf={r.get('reroute_confidence',0):.2f}"
        for r in tops
    ]
    return lines


def _h3_memo_lines(branch_metrics: dict) -> list[str]:
    """H3 section for review memo: uplift-aware ranking summary."""
    ur = branch_metrics.get("h3_uplift_ranking", {})
    summary = ur.get("uplift_aware_summary", {})
    rescued = ur.get("rescued_hypotheses", [])
    demoted = ur.get("demoted_hypotheses", [])
    top5 = ur.get("uplift_ranked_cards", [])[:5]
    lines = [
        "",
        "## H3: Uplift-Aware Ranking",
        "",
        f"- n_rescued (into top-k): {summary.get('n_rescued', 0)}",
        f"- n_demoted (out of top-k): {summary.get('n_demoted', 0)}",
        f"- n_top_k_changed: {summary.get('n_top_k_changed', 0)}",
        f"- mean_uplift_aware_score: {summary.get('mean_ua_score', 0.0):.4f}",
        "- Top-5 uplift-aware cards:",
    ] + [
        f"  {i+1}. [{d.get('branch','?')}] {d.get('title','')[:50]} "
        f"ua={d.get('uplift_aware_score',0):.4f} raw={d.get('raw_score',0):.3f} "
        f"rank_Δ={d.get('rank_delta',0):+d}"
        for i, d in enumerate(top5)
    ] + [
        "- Rescued (raw low, uplift high):",
    ] + [
        f"  - {r.get('title','')[:50]} ua={r.get('uplift_aware_score',0):.4f}"
        for r in rescued
    ] + [
        "- Demoted (raw high, uplift low):",
    ] + [
        f"  - {d.get('title','')[:50]} ua={d.get('uplift_aware_score',0):.4f}"
        for d in demoted
    ]
    return lines

def _i1_memo_lines(branch_metrics: dict) -> list[str]:
    """I1 section for review memo: decision tier summary."""
    tiers = branch_metrics.get("i1_decision_tiers", {})
    counts = tiers.get("tier_counts", {})
    pct = tiers.get("tier_distribution_pct", {})
    top_aw = tiers.get("actionable_watch_top", [])
    rejected = tiers.get("reject_conflicted_examples", [])
    borderline = tiers.get("monitor_borderline_cases", [])
    lines = [
        "",
        "## I1: Decision Tiers",
        "",
        "- Tier counts:",
    ] + [
        f"  - {t}: {c} ({pct.get(t, 0):.1%})"
        for t, c in sorted(counts.items(), key=lambda x: -x[1])
    ] + [
        "- actionable_watch top cards:",
    ] + [
        f"  - [{a.get('branch','?')}] {a.get('title','')[:60]} score={a.get('composite_score',0):.3f}"
        for a in top_aw
    ] + [
        "- reject_conflicted examples:",
    ] + [
        f"  - [{a.get('branch','?')}] {a.get('title','')[:55]} severity={a.get('contradiction_severity',0):.2f}"
        for a in rejected
    ] + [
        "- monitor_borderline cases:",
    ] + [
        f"  - [{a.get('branch','?')}] {a.get('title','')[:55]} soft_gated={a.get('is_soft_gated')}"
        for a in borderline
    ]
    return lines


def _i2_memo_lines(branch_metrics: dict) -> list[str]:
    """I2 section for review memo: persistence tracking summary."""
    p = branch_metrics.get("i2_persistence", {})
    summary = p.get("summary", {})
    top_fam = p.get("top_persistent_families", [])
    promotions = p.get("promotions", [])
    lines = [
        "",
        "## I2: Persistence Tracking",
        "",
        f"- n_families: {summary.get('n_families', 0)}",
        f"- n_persistent_ge2_runs: {summary.get('n_persistent_ge2_runs', 0)}",
        f"- n_soft_gated_to_active: {summary.get('n_soft_gated_to_active', 0)}",
        f"- n_primary_to_rerouted: {summary.get('n_primary_to_rerouted', 0)}",
        f"- promotions this run: {len(promotions)}",
        "- top persistent families:",
    ] + [
        f"  - {f.get('family_id','?')} consec={f.get('consecutive_top_k_count',0)} "
        f"ema={f.get('persistence_score',0):.3f} tier={f.get('last_tier','?')}"
        for f in top_fam
    ]
    return lines


def _i3_memo_lines(branch_metrics: dict) -> list[str]:
    """I3 section for review memo: grammar confusion matrix summary."""
    cm = branch_metrics.get("i3_confusion_matrix", {})
    br = cm.get("branch_reroute_matrix", {})
    dominant = cm.get("dominant_confusion_pairs", [])
    interp = cm.get("interpretation", [])
    lines = [
        "",
        "## I3: Grammar Confusion Matrix",
        "",
        "- branch_reroute_matrix:",
    ]
    for orig, dests in sorted(br.items()):
        for dest, cnt in sorted(dests.items(), key=lambda x: -x[1]):
            lines.append(f"  - {orig} → {dest}: {cnt}")
    lines += ["- dominant confusion pairs:"] + [
        f"  - {d.get('from','?')} → {d.get('to','?')}: {d.get('count',0)}"
        for d in dominant
    ] + ["- interpretation:"] + [f"  {s}" for s in interp]
    return lines


def _i4_memo_lines(branch_metrics: dict) -> list[str]:
    """I4 section for review memo: watchlist semantics summary."""
    ws = branch_metrics.get("i4_watchlist", {})
    label_counts = ws.get("label_counts", {})
    urgency_counts = ws.get("urgency_counts", {})
    high_urgency = ws.get("high_urgency_labels", [])
    lines = [
        "",
        "## I4: Watchlist Semantics",
        "",
        "- Watch label counts:",
    ] + [
        f"  - {lbl}: {cnt}"
        for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1])
    ] + [
        "- Urgency counts:",
    ] + [
        f"  - {u}: {c}"
        for u, c in sorted(urgency_counts.items())
    ] + [
        "- High-urgency (actionable_watch) cards:",
    ] + [
        f"  - [{w.get('branch','?')}] {w.get('title','')[:55]} "
        f"label={w.get('watch_label','?')}"
        for w in high_urgency
    ]
    return lines
=======
    # review_memo.md
    _write_review_memo(run_dir, config, cards)
>>>>>>> claude/thirsty-heisenberg
=======
    # review_memo.md
    _write_review_memo(run_dir, config, cards)
>>>>>>> claude/elated-lamarr


=======
>>>>>>> claude/gracious-edison
def _write_review_memo(
    run_dir: str,
    config: PipelineConfig,
    cards: list,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
    branch_metrics: dict,
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
    branch_metrics: dict,
>>>>>>> claude/gracious-edison
) -> None:
    """Generate a human-readable review memo for the run."""
    from .schema.task_status import SecrecyLevel, ValidationStatus

    n_weakly = sum(
        1 for c in cards
        if c.validation_status == ValidationStatus.WEAKLY_SUPPORTED
    )
    n_private = sum(
        1 for c in cards
        if c.secrecy_level == SecrecyLevel.PRIVATE_ALPHA
    )
    n_internal = sum(
        1 for c in cards
        if c.secrecy_level == SecrecyLevel.INTERNAL_WATCHLIST
    )
    scores = [c.composite_score for c in cards]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/gracious-edison
    dist = branch_metrics.get("branch_distribution", {})
    entropy = branch_metrics.get("branch_entropy", 0.0)
    suppression = branch_metrics.get("branch_suppression_reason", {})
    top_share = branch_metrics.get("top_k_branch_share", {})

<<<<<<< HEAD
    # F1 calibration
    calibration = branch_metrics.get("branch_calibration", {})
    # F2 normalization diff summary
    norm_ranking = branch_metrics.get("normalized_ranking", {})
    norm_diff = norm_ranking.get("ranking_diff_summary", {})
    # F3 taxonomy
    suppression_taxonomy = {
        k: v for k, v in suppression.items()
        if k in ("structural_absence", "failed_followthrough",
                 "contradictory_evidence", "no_trigger", "missing_accumulation")
    }
    # F4 regime
    regime = branch_metrics.get("regime_stratified", {})
    # F5 baseline uplift
    uplift = branch_metrics.get("baseline_uplift", {})
    top_uplift = uplift.get("top_uplift", [])
    mean_uplift = uplift.get("mean_uplift_by_branch", {})

=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
    lines = [
        f"# Review Memo — {config.run_id}",
        "",
        f"**Date:** {datetime.now(timezone.utc).date()}",
        f"**Seed:** {config.seed}",
        f"**Duration:** {config.n_minutes} minutes synthetic data",
        f"**Assets:** {', '.join(config.assets or ['HYPE', 'ETH', 'BTC', 'SOL'])}",
        "",
        "## Summary",
        "",
        f"- Total hypothesis cards: {len(cards)}",
        f"- Weakly supported (composite ≥ 0.60): {n_weakly}",
        f"- Private alpha: {n_private}",
        f"- Internal watchlist: {n_internal}",
        f"- Average composite score: {avg_score:.3f}",
        f"- Best composite score: {max_score:.3f}",
        "",
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/gracious-edison
        "## Branch Diversity (E3)",
        "",
        f"- **branch_entropy:** {entropy:.4f} bits",
        f"- **branch_distribution:** {dist}",
        f"- **top_k_branch_share:** {top_share}",
        "- **branch_suppression_reason:**",
    ] + [f"  - {r}: {c}" for r, c in suppression.items()] + [
        "",
<<<<<<< HEAD
        "## F1: Branch Calibration",
        "",
    ] + [
        f"- **{b}**: count={s['count']}, mean={s['mean_score']}, "
        f"median={s['median_score']}, p90={s['p90_score']}, "
        f"count_norm_top_k={s['count_normalized_top_k_share']}, "
        f"ev_slope={s['evidence_count_vs_score_slope']}, "
        f"arch_advantage={s['score_architecture_advantage']}"
        for b, s in calibration.items()
    ] + [
        "",
        "## F2: Cross-Branch Normalization",
        "",
        f"- mean_abs_rank_diff: {norm_diff.get('mean_abs_diff', 'N/A')}",
        f"- max_rank_diff: {norm_diff.get('max_diff', 'N/A')}",
        f"- n_cards_changed_top_k: {norm_diff.get('n_cards_changed_top_k', 'N/A')}",
        "",
        "## F3: Negative Evidence Taxonomy",
        "",
    ] + [f"  - {r}: {c}" for r, c in suppression_taxonomy.items()] + [
        "",
        "## F4: Regime-Stratified",
        "",
    ] + [
        f"- **{bucket}**: n={d['n_cards']}, dominant={d['dominant_branch']}, "
        f"mean_score={d['mean_score']}, top_k_share={d['top_k_share']}"
        for bucket, d in sorted(regime.items())
    ] + [
        "",
        "## F5: Baseline Uplift",
        "",
        f"- n_matched: {uplift.get('n_matched', 0)}",
        f"- mean_uplift_by_branch: {mean_uplift}",
        "- top_uplift hypotheses:",
    ] + [
        f"  - [{d.get('branch', '?')}] {d.get('title', '')[:60]} "
        f"adj_uplift={d.get('complexity_penalty_adjusted_uplift', 0):.4f}"
        for d in top_uplift
    ] + _g1_memo_lines(branch_metrics) + _g3_memo_lines(branch_metrics) + _h2_memo_lines(branch_metrics) + _h3_memo_lines(branch_metrics) + _i1_memo_lines(branch_metrics) + _i2_memo_lines(branch_metrics) + _i3_memo_lines(branch_metrics) + _i4_memo_lines(branch_metrics) + [
        "",
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
        "## Top Hypotheses",
        "",
    ]
    for i, card in enumerate(
        sorted(cards, key=lambda c: c.composite_score, reverse=True)[:5], 1
    ):
        lines += [
            f"### {i}. {card.title}",
            f"**Composite:** {card.composite_score:.3f} | "
            f"**Secrecy:** {card.secrecy_level.value} | "
            f"**Status:** {card.validation_status.value}",
            "",
            f"> {card.claim}",
            "",
            f"*Mechanism:* {card.mechanism}",
            "",
            f"*Operator trace:* {' → '.join(card.operator_trace)}",
            "",
        ]

    with open(os.path.join(run_dir, "review_memo.md"), "w") as f:
        f.write("\n".join(lines))
