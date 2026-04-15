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

from .eval.generator import generate_hypotheses
from .eval.scorer import score_hypothesis
from .ingestion.synthetic import SyntheticGenerator
from .inventory.store import HypothesisInventory
from .kg.base import KGraph
from .kg.cross_asset import build_cross_asset_kg
from .kg.execution import build_execution_kg
from .kg.microstructure import build_microstructure_kg
from .kg.pair import build_pair_kg
from .kg.regime import build_regime_kg
from .operators.ops import align, compose, difference, rank, union
from .states.extractor import extract_states


@dataclass
class PipelineConfig:
    """Configuration for one pipeline run.

    Why a dataclass not a plain dict: type safety and named access
    make the config self-documenting and IDE-friendly.
    """

    run_id: str
    seed: int = 42
    n_minutes: int = 60
    assets: Optional[list[str]] = None
    top_k: int = 10
    output_dir: str = "crypto/artifacts/runs"


def run_pipeline(config: PipelineConfig) -> list:
    """Execute the full KG discovery pipeline.

    Args:
        config: PipelineConfig controlling seed, duration, assets, output.

    Returns:
        List of HypothesisCard objects (also saved to output_dir).
    """
    random.seed(config.seed)

    # 1. Synthetic data generation
    generator = SyntheticGenerator(
        seed=config.seed,
        n_minutes=config.n_minutes,
        assets=config.assets,
    )
    dataset = generator.generate()

    assets = config.assets or ["HYPE", "ETH", "BTC", "SOL"]

    # 2. State extraction (per asset)
    collections = {}
    for asset in assets:
        collections[asset] = extract_states(dataset, asset, config.run_id)

    # 3. KG construction (per family)
    micro_kgs = {a: build_microstructure_kg(collections[a]) for a in assets}
    execution_kgs = {a: build_execution_kg(collections[a]) for a in assets}
    regime_kgs = {a: build_regime_kg(collections[a]) for a in assets}
    cross_kg = build_cross_asset_kg(collections)
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

    # 9. Persist outputs
    _save_outputs(config, cards, inventory)

    return cards


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
) -> None:
    """Write run config, hypothesis cards, and review memo to output_dir."""
    run_dir = os.path.join(
        config.output_dir,
        f"{config.run_id}",
    )
    os.makedirs(run_dir, exist_ok=True)

    # run_config.json
    run_config = {
        "run_id": config.run_id,
        "seed": config.seed,
        "n_minutes": config.n_minutes,
        "assets": config.assets or ["HYPE", "ETH", "BTC", "SOL"],
        "top_k": config.top_k,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(run_dir, "run_config.json"), "w") as f:
        json.dump(run_config, f, indent=2)

    # output_candidates.json
    inventory.save(os.path.join(run_dir, "output_candidates.json"))

    # review_memo.md
    _write_review_memo(run_dir, config, cards)


def _write_review_memo(
    run_dir: str,
    config: PipelineConfig,
    cards: list,
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
