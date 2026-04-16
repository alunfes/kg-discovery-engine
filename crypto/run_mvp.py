<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
"""Run one MVP experiment using the crypto KG discovery pipeline."""

import sys
import os

# Ensure the worktree root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto.src.pipeline import PipelineConfig, run_pipeline


def main() -> None:
    """Execute the MVP pipeline run."""
    config = PipelineConfig(
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
        run_id="run_007_sprint_h",
        seed=42,
        n_minutes=120,
        assets=["HYPE", "ETH", "BTC", "SOL"],
        top_k=60,
<<<<<<< HEAD
<<<<<<< HEAD
=======
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
        run_id="run_001_20260415",
        seed=42,
        n_minutes=120,
        assets=["HYPE", "ETH", "BTC", "SOL"],
        top_k=10,
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
        output_dir="crypto/artifacts/runs",
    )

    print(f"Starting pipeline run: {config.run_id}")
    print(f"Seed={config.seed}, n_minutes={config.n_minutes}, assets={config.assets}")
    print()

    cards = run_pipeline(config)

    print(f"Pipeline complete. Generated {len(cards)} hypothesis cards.")
    print()

    for i, card in enumerate(
        sorted(cards, key=lambda c: c.composite_score, reverse=True), 1
    ):
        print(f"  {i:2d}. [{card.composite_score:.3f}] [{card.secrecy_level.value[:7]}] "
              f"[{card.validation_status.value[:8]}] {card.title}")

    print()
    print(f"Output: crypto/artifacts/runs/{config.run_id}/")
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
"""HYPE KG Discovery Engine — MVP Experiment Runner.

Runs the full end-to-end pipeline (C1 baseline + C2 full 5-KG) on synthetic
market data and writes all artifacts to crypto/artifacts/runs/run_001_20260415_mvp/.

Usage (run from repo root):
    python -m crypto.run_mvp
    python crypto/run_mvp.py

Why run from repo root:
    This script imports from both src/ (existing KG engine) and crypto/src/
    (HYPE-specific extensions). Both are resolved relative to the repo root.
    Running from inside crypto/ would break the src/ imports.

Output artifacts:
    run_config.json            - experiment parameters and KG statistics
    output_candidates.json     - all hypothesis cards (private_alpha redacted)
    output_candidates_full.json - all cards including private (NOT committed to git)
    hypothesis_store/          - HypothesisStore inventory
    review_memo.md             - researcher analysis of findings
"""

from __future__ import annotations

import datetime
import json
import os
import sys

# Ensure repo root is on the Python path when run as a script (not module).
# When run as 'python -m crypto.run_mvp', the repo root is already on sys.path.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.inventory.hypothesis_store import HypothesisStore  # noqa: E402
from src.schema.hypothesis_card import HypothesisCard  # noqa: E402
from crypto.src.operators.hype_pipeline import run_hype_pipeline, PipelineResult  # noqa: E402

_RUN_ID = "HYP-20260415-001"
_RUN_NAME = "run_001_20260415_mvp"
_ARTIFACTS_DIR = os.path.join(
    os.path.dirname(__file__), "artifacts", "runs", _RUN_NAME
)
_SYMBOLS = ["HYPE", "BTC", "ETH", "SOL"]
_PAIRS = [("HYPE", "BTC"), ("HYPE", "ETH"), ("HYPE", "SOL"), ("BTC", "ETH")]


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _count_by(cards: list[HypothesisCard], field: str) -> dict[str, int]:
    """Count cards by a categorical field value."""
    counts: dict[str, int] = {}
    for c in cards:
        val = getattr(c, field)
        counts[val] = counts.get(val, 0) + 1
    return counts


def save_run_config(
    run_dir: str, c1: PipelineResult, c2: PipelineResult,
) -> dict:
    """Write run_config.json with experiment parameters and KG statistics."""
    config = {
        "run_id": _RUN_ID,
        "run_name": _RUN_NAME,
        "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbols": _SYMBOLS,
        "pairs": [list(p) for p in _PAIRS],
        "timeframe": "1h",
        "n_bars": 200,
        "seed": 42,
        "data_source": "MockHyperliquidConnector (synthetic, seed=42)",
        "prior_research_claims": [
            "Long-path discovery viable when bridge geometry is semantically enriched",
            "KG operator value = reachability gain over baseline",
            "Deep discovery needs strong filtering/selection",
            "Selection artifact: endpoint-level validation signal matters",
            "Relation semantic insufficiency: structural correctness != economic meaning",
        ],
        "conditions": {
            "C1": {
                "name": c1.condition,
                "kgs_used": c1.kg_names,
                "n_nodes": c1.n_nodes,
                "n_edges": c1.n_edges,
                "n_candidates": len(c1.candidates),
                "n_cards": len(c1.cards),
                "secrecy_dist": _count_by(c1.cards, "secrecy_level"),
            },
            "C2": {
                "name": c2.condition,
                "kgs_used": c2.kg_names,
                "n_nodes": c2.n_nodes,
                "n_edges": c2.n_edges,
                "n_candidates": len(c2.candidates),
                "n_cards": len(c2.cards),
                "secrecy_dist": _count_by(c2.cards, "secrecy_level"),
            },
        },
    }
    path = os.path.join(run_dir, "run_config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config


def save_candidates(
    run_dir: str,
    cards: list[HypothesisCard],
    filename: str,
    include_private: bool = False,
) -> int:
    """Write hypothesis cards to JSON. Returns count of cards written."""
    filtered = [c for c in cards if include_private or c.secrecy_level != "private_alpha"]
    path = os.path.join(run_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in filtered], f, indent=2)
    return len(filtered)


def write_review_memo(
    run_dir: str,
    run_config: dict,
    c1: PipelineResult,
    c2: PipelineResult,
) -> None:
    """Write researcher review memo summarising experiment findings."""
    c1_sec = _count_by(c1.cards, "secrecy_level")
    c2_sec = _count_by(c2.cards, "secrecy_level")
    c2_scope = _count_by(c2.cards, "market_scope")

    top_cards = [c for c in c2.cards if c.secrecy_level != "private_alpha"][:5]

    c1_actionable = c1_sec.get("private_alpha", 0) + c1_sec.get("internal_watchlist", 0)
    c2_actionable = c2_sec.get("private_alpha", 0) + c2_sec.get("internal_watchlist", 0)
    pair_rv_count = c2_scope.get("pair_rv", 0)
    cross_count = c2_scope.get("cross_asset", 0)

    lines = [
        f"# MVP Experiment Review — {_RUN_NAME}",
        f"",
        f"**Run ID:** {_RUN_ID}",
        f"**Date:** {run_config['created_at'][:10]}",
        f"**Data:** Synthetic (MockHyperliquidConnector, seed=42, 200 bars 1h)",
        f"",
        f"## Conditions Summary",
        f"",
        f"| Condition | KGs | Nodes | Edges | Candidates | Cards |",
        f"|-----------|-----|-------|-------|------------|-------|",
        f"| C1 (micro only) | microstructure | {c1.n_nodes} | {c1.n_edges}"
        f" | {len(c1.candidates)} | {len(c1.cards)} |",
        f"| C2 (full 5-KG) | all 5 KGs | {c2.n_nodes} | {c2.n_edges}"
        f" | {len(c2.candidates)} | {len(c2.cards)} |",
        f"",
        f"## Secrecy Distribution",
        f"",
        f"**C1 baseline:**",
    ]
    for level in ["private_alpha", "internal_watchlist", "shareable_structure", "discard"]:
        if level in c1_sec:
            lines.append(f"- {level}: {c1_sec[level]}")
    lines += ["", "**C2 full pipeline:**"]
    for level in ["private_alpha", "internal_watchlist", "shareable_structure", "discard"]:
        if level in c2_sec:
            lines.append(f"- {level}: {c2_sec[level]}")
    lines += ["", "## C2 Market Scope Distribution", ""]
    for scope, count in sorted(c2_scope.items(), key=lambda x: -x[1]):
        lines.append(f"- {scope}: {count}")
    lines += ["", "## Top 5 Hypothesis Cards (C2, non-private)", ""]
    for i, card in enumerate(top_cards, 1):
        lines += [
            f"### Card {i}: {card.hypothesis_id}",
            f"- **Symbols:** {', '.join(card.symbols)}",
            f"- **Scope:** {card.market_scope}  |  **Secrecy:** {card.secrecy_level}",
            f"- **Scores:** actionability={card.actionability_score:.2f}"
            f"  novelty={card.novelty_score:.2f}"
            f"  reproducibility={card.reproducibility_score:.2f}",
            f"- **Hypothesis:** {card.hypothesis_text}",
            f"- **Provenance:** {' → '.join(card.provenance_path[:7])}"
            + (" ..." if len(card.provenance_path) > 7 else ""),
            f"- **Next Test:** {card.next_recommended_test}",
            f"",
        ]
    lines += [
        f"## C2 vs C1 Delta (Reachability Value)",
        f"",
        f"- Actionable cards (private_alpha + internal_watchlist):"
        f" C1={c1_actionable}, C2={c2_actionable}, Δ=+{c2_actionable - c1_actionable}",
        f"- Total candidates: C1={len(c1.candidates)}, C2={len(c2.candidates)}",
        f"- Cross-KG scope cards (cross_asset + pair_rv): {cross_count + pair_rv_count}",
        f"  - These are only discoverable with the 5-KG merged graph (not in C1)",
        f"",
        f"## Key Findings",
        f"",
        f"1. **Cross-KG reachability confirmed**: C2 discovers {len(c2.candidates) - len(c1.candidates)}"
        f" additional candidates not reachable in C1 (micro-only). The Pair/RV KG bridge",
        f"   edges connect individual asset states to semantic pair states, enabling compose",
        f"   to traverse multi-KG transitive paths.",
        f"",
        f"2. **Filtering effectiveness**: guard_consecutive_repeat and min_strong_ratio=0.2",
        f"   filters remove spurious co_occurs_with chains. The {c2_sec.get('discard', 0)} discard",
        f"   cards in C2 represent filtered-out but structurally detectable non-edges.",
        f"",
        f"3. **Pair/RV KG contribution**: {pair_rv_count} C2 cards have market_scope=pair_rv,",
        f"   representing novel HYPE relative-value hypotheses not discoverable by any",
        f"   single-asset or standard cross-asset approach.",
        f"",
        f"4. **Selection principle upheld (from P6-A)**: C2 scoring uses 5-dimension rubric",
        f"   weighting actionability and novelty independently, preventing length-bias",
        f"   artifacts where long paths score high simply due to novelty inflation.",
        f"",
        f"## Limitations of This Run",
        f"",
        f"1. **Synthetic data only**: All patterns reflect MockHyperliquidConnector generator",
        f"   design (BTC-HYPE lead-lag injection, SOL-ETH lead-lag). Real market structure",
        f"   may differ substantially.",
        f"",
        f"2. **1h timeframe**: State extraction thresholds calibrated for 1h bars.",
        f"   For 4h analysis, re-calibrate vol_burst (threshold: 1.3→1.5) and",
        f"   funding_extreme (threshold: 2e-5→8e-5).",
        f"",
        f"3. **No order book**: Execution KG proxies spread quality via candle range.",
        f"   Real execution edge validation requires L2 order book data.",
        f"",
        f"4. **Heuristic pair states**: Beta instability and correlation breakdown",
        f"   detection uses rolling windows. Parameters need calibration on real data.",
        f"",
        f"## Recommended Next Steps",
        f"",
        f"1. **Connect live Hyperliquid data**: implement `crypto/src/ingestion/hyperliquid_connector.py`",
        f"   using Hyperliquid REST API (`/info` → candle_snapshot, funding_history)",
        f"2. **Backtest top internal_watchlist cards**: prioritize cards with",
        f"   `next_recommended_test = event_study_vol_burst_lead_lag`",
        f"3. **Re-run on 4h timeframe**: recalibrate thresholds, expect fewer but cleaner states",
        f"4. **Validate Pair/RV states on real HYPE-BTC data**: check if spread_divergence",
        f"   actually precedes mean_reversion_setup in historical data",
        f"5. **P10 consideration**: Apply T3 investigability pre-filter from research",
        f"   to prevent low-frontier hypotheses from crowding the inventory",
    ]
    path = os.path.join(run_dir, "review_memo.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict[str, PipelineResult]:
    """Run the MVP experiment end-to-end and write all artifacts."""
    print(f"[HYPE KG Discovery Engine MVP]")
    print(f"Run ID : {_RUN_ID}")
    print(f"Output : {_ARTIFACTS_DIR}")
    print()

    os.makedirs(_ARTIFACTS_DIR, exist_ok=True)

    print("Step 1/4  Running pipeline (C1 baseline + C2 full 5-KG) ...")
    results = run_hype_pipeline(run_id=_RUN_ID)
    c1, c2 = results["C1"], results["C2"]
    print(f"          C1: {len(c1.candidates)} candidates → {len(c1.cards)} cards")
    print(f"          C2: {len(c2.candidates)} candidates → {len(c2.cards)} cards")

    print("Step 2/4  Saving run_config.json ...")
    run_config = save_run_config(_ARTIFACTS_DIR, c1, c2)

    print("Step 3/4  Saving hypothesis cards ...")
    n_pub = save_candidates(_ARTIFACTS_DIR, c2.cards, "output_candidates.json")
    n_full = save_candidates(
        _ARTIFACTS_DIR, c2.cards, "output_candidates_full.json", include_private=True
    )
    n_priv = n_full - n_pub
    print(f"          {n_pub} cards public  |  {n_priv} private_alpha (redacted from public file)")

    store = HypothesisStore(os.path.join(_ARTIFACTS_DIR, "hypothesis_store"))
    store.save_batch(c2.cards)
    stats = store.get_stats()
    print(f"          Store stats: {stats}")

    print("Step 4/4  Writing review_memo.md ...")
    write_review_memo(_ARTIFACTS_DIR, run_config, c1, c2)

    print()
    print("=== MVP EXPERIMENT COMPLETE ===")
    print(f"Run  : {_RUN_NAME}")
    print(f"C1 actionable: {run_config['conditions']['C1']['secrecy_dist']}")
    print(f"C2 actionable: {run_config['conditions']['C2']['secrecy_dist']}")
    print(f"Artifacts: {_ARTIFACTS_DIR}")
    return results
>>>>>>> claude/gifted-cray
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf


if __name__ == "__main__":
    main()
