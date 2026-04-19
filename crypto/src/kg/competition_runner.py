"""Offline competition post-processing runner.

Reads pipeline artifacts, applies hypothesis competition pipeline, and saves results.
Does NOT modify the live shadow runtime.

Usage:
    from crypto.src.kg.competition_runner import run_competition_analysis
    results = run_competition_analysis("path/to/pipeline_out", regime="correlation_break")
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..eval.scorer import _score_plausibility, _score_actionability
from ..kg.base import KGraph, KGNode
from ..schema.hypothesis_card import HypothesisCard, ScoreBundle
from ..schema.task_status import SecrecyLevel, ValidationStatus
from .hypothesis import HypothesisNode
from .hypothesis_builder import card_to_hypothesis
from .hypothesis_competition import (
    CompetitionResult,
    apply_regime_decay,
    compete_all,
)
from .hypothesis_diversifier import diversify

logger = logging.getLogger(__name__)

_WEAK_PLAUSIBILITY_THRESHOLD = 0.40


@dataclass
class CompetitionAnalysis:
    """Full analysis output for one pipeline run."""

    n_input_cards: int = 0
    n_filtered_weak: int = 0
    n_hypotheses_after_diversify: int = 0
    n_groups: int = 0
    results: list[CompetitionResult] = field(default_factory=list)
    regime_used: str = ""
    group_fn_used: str = ""

    def summary_table(self) -> dict:
        if not self.results:
            return {}
        families_per_group = [
            len({r.primary.family} | {a.family for a in r.alternatives})
            for r in self.results
        ]
        null_wins = sum(1 for r in self.results if r.primary.family == "null")
        confidences = [r.confidence for r in self.results]
        decayed = sum(
            1 for r in self.results
            if any(a.metadata.get("regime_decayed") for a in [r.primary] + r.alternatives)
        )
        import statistics
        return {
            "n_input_cards": self.n_input_cards,
            "n_filtered_weak": self.n_filtered_weak,
            "n_groups": self.n_groups,
            "families_per_group_mean": round(statistics.mean(families_per_group), 2),
            "null_win_pct": round(null_wins / max(len(self.results), 1) * 100, 1),
            "confidence_median": round(statistics.median(confidences), 4),
            "confidence_p25": round(sorted(confidences)[len(confidences) // 4], 4) if len(confidences) > 3 else 0,
            "regime_decayed_pct": round(decayed / max(len(self.results), 1) * 100, 1),
            "regime": self.regime_used,
        }


def _load_cards_from_pipeline_out(pipeline_out_dir: str) -> list[dict]:
    """Load all output_candidates.json across cycle directories."""
    cards: list[dict] = []
    if not os.path.isdir(pipeline_out_dir):
        return cards
    for cycle_dir in sorted(os.listdir(pipeline_out_dir)):
        cand_path = os.path.join(pipeline_out_dir, cycle_dir, "output_candidates.json")
        if not os.path.isfile(cand_path):
            continue
        with open(cand_path, encoding="utf-8") as f:
            cycle_cards = json.load(f)
        cycle_num = int(cycle_dir.split("_")[-1]) if "_" in cycle_dir else 0
        for c in cycle_cards:
            c["_cycle"] = cycle_num
        cards.extend(cycle_cards)
    return cards


def _signal_strength_bonus(card_dict: dict) -> float:
    """Compute per-card signal strength bonus from structured fields.

    Uses signal_rho and signal_break_score fields if available (preferred),
    falls back to claim text extraction for backward compatibility.
    """
    rho = card_dict.get("signal_rho")
    bs = card_dict.get("signal_break_score")

    if rho is None and bs is None:
        import re
        claim = card_dict.get("claim", "")
        rho_m = re.search(r"rho=(-?[0-9]+\.[0-9]+)", claim)
        if rho_m:
            try:
                rho = float(rho_m.group(1))
            except ValueError:
                pass
        bs_m = re.search(r"break_score=([0-9]+\.[0-9]+)", claim)
        if bs_m:
            try:
                bs = float(bs_m.group(1))
            except ValueError:
                pass

    bonus = 0.0
    if rho is not None:
        bonus += min(0.15, abs(rho) * 0.5)
    if bs is not None:
        bonus += min(0.15, bs * 0.15)
    return bonus


def _raw_to_hypothesis(raw: dict, idx: int) -> Optional[HypothesisNode]:
    """Convert raw card dict to HypothesisNode with de-saturated scores + signal bonus."""
    mock_kg = KGraph(family="mock")
    mock_kg.add_node(KGNode("feas", "FeasibilityNode", {"feasible": True, "frac_expensive": 0.15}))

    raw["scores"]["plausibility"] = _score_plausibility(raw)
    raw["scores"]["actionability"] = _score_actionability(raw, mock_kg)

    scores = ScoreBundle(**{k: v for k, v in raw["scores"].items() if k != "WEIGHTS"})
    card = HypothesisCard(
        card_id=raw["card_id"], version=raw["version"], created_at=raw["created_at"],
        title=raw["title"], claim=raw["claim"], mechanism=raw.get("mechanism", ""),
        evidence_nodes=raw.get("evidence_nodes", []),
        evidence_edges=raw.get("evidence_edges", []),
        operator_trace=raw.get("operator_trace", []),
        secrecy_level=SecrecyLevel(raw.get("secrecy_level", "shareable_structure")),
        validation_status=ValidationStatus(raw.get("validation_status", "untested")),
        scores=scores, composite_score=scores.composite(),
        run_id=raw.get("run_id", ""), kg_families=raw.get("kg_families", []),
        tags=raw.get("tags", []), actionability_note=raw.get("actionability_note"),
    )
    h = card_to_hypothesis(card, timestamp_ms=1713500000000 + idx * 100)

    for tok in ["BTC", "ETH", "HYPE", "SOL"]:
        if tok in h.claim.upper():
            h.metadata["asset"] = tok
            break

    h.metadata["_cycle"] = raw.get("_cycle", 0)

    # Apply signal-specific bonus from structured fields (or fallback to text parsing)
    signal_bonus = _signal_strength_bonus(raw)
    h.evidence_strength = min(1.0, h.evidence_strength + signal_bonus)
    return h


def group_by_cycle_asset(
    hypotheses: list[HypothesisNode],
) -> dict[str, list[HypothesisNode]]:
    """Group by (asset, cycle) — the recommended granular grouping."""
    groups: defaultdict[str, list[HypothesisNode]] = defaultdict(list)
    for h in hypotheses:
        asset = h.metadata.get("asset", "unknown")
        cycle = h.metadata.get("_cycle", 0)
        key = f"{asset}:c{cycle:03d}"
        groups[key].append(h)
    return dict(groups)


def run_competition_analysis(
    pipeline_out_dir: str,
    regime: str = "correlation_break",
    group_fn: str = "cycle_asset",
    weak_threshold: float = _WEAK_PLAUSIBILITY_THRESHOLD,
    output_dir: Optional[str] = None,
) -> CompetitionAnalysis:
    """Run full offline competition analysis on pipeline artifacts.

    Args:
        pipeline_out_dir: path to pipeline_out/ directory
        regime: current market regime for decay
        group_fn: "cycle_asset" (recommended) or "asset" or "scope"
        weak_threshold: plausibility below this → filtered to weak log
        output_dir: if set, save results JSON here
    """
    cards_raw = _load_cards_from_pipeline_out(pipeline_out_dir)
    analysis = CompetitionAnalysis(n_input_cards=len(cards_raw), regime_used=regime, group_fn_used=group_fn)

    if not cards_raw:
        logger.warning("No cards found in %s", pipeline_out_dir)
        return analysis

    # Convert + filter weak
    hypotheses: list[HypothesisNode] = []
    weak: list[dict] = []
    for i, raw in enumerate(cards_raw):
        plaus = _score_plausibility(raw)
        if plaus < weak_threshold:
            weak.append(raw)
            continue
        h = _raw_to_hypothesis(raw, i)
        if h:
            hypotheses.append(h)

    analysis.n_filtered_weak = len(weak)
    logger.info("Cards: %d total, %d weak-filtered, %d hypotheses", len(cards_raw), len(weak), len(hypotheses))

    # Diversify
    diversified = diversify(hypotheses, min_families=4)
    analysis.n_hypotheses_after_diversify = len(diversified)

    # Regime decay
    apply_regime_decay(diversified, regime)

    # Compete
    if group_fn == "cycle_asset":
        from .hypothesis_competition import arbitrate
        groups = group_by_cycle_asset(diversified)
        results: list[CompetitionResult] = []
        for key, group in sorted(groups.items()):
            r = arbitrate(group, group_key=key, regime=regime)
            if r:
                results.append(r)
    else:
        results = compete_all(diversified, group_fn=group_fn, regime=regime)

    analysis.results = results
    analysis.n_groups = len(results)

    # Save if output_dir specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        summary = analysis.summary_table()
        with open(os.path.join(output_dir, "competition_summary.json"), "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        per_group = [r.to_dict() for r in results]
        with open(os.path.join(output_dir, "competition_groups.json"), "w") as f:
            json.dump(per_group, f, indent=2, ensure_ascii=False)

        if weak:
            with open(os.path.join(output_dir, "weak_candidates.json"), "w") as f:
                json.dump(weak, f, indent=2, ensure_ascii=False)

        logger.info("Competition results saved to %s", output_dir)

    return analysis
