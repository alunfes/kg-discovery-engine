"""Surface policy for KG Discovery Engine delivery stack.

Implements two pruning rules:
1. null_baseline: Drop single non-HYPE symbol paths (intra-domain trivial sequences).
2. baseline_like: Archive shareable_structure cards with novelty_score <= 0.30.

These are the Run 038 finalized surface pruning rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schema.hypothesis_card import HypothesisCard

_TRADEABLE_ASSETS: frozenset[str] = frozenset({"HYPE", "BTC", "ETH", "SOL"})

# Surface tiers
SURFACE_ACTIVE = "active"     # Deliver immediately
SURFACE_ARCHIVE = "archive"   # Store, do not surface by default
SURFACE_DROP = "drop"         # Exclude from delivery entirely


def _symbols_in_provenance(provenance_path: list[str]) -> frozenset[str]:
    """Extract tradeable asset symbols from the provenance path nodes."""
    symbols: set[str] = set()
    for node in provenance_path[0::2]:  # every other element is a node ID
        sym = node.split(":")[0]
        if sym in _TRADEABLE_ASSETS:
            symbols.add(sym)
    return frozenset(symbols)


def is_null_baseline(card: "HypothesisCard") -> bool:
    """Return True if the card is a null_baseline and should be dropped.

    Definition: single non-HYPE tradeable asset in the entire provenance path.
    These are intra-asset sequences (BTC:calm -> BTC:price_momentum -> BTC:vol_burst)
    that any naive baseline operator would also discover, with zero cross-domain signal.
    HYPE paths are always excluded from null_baseline (they carry potential alpha).
    """
    syms = _symbols_in_provenance(card.provenance_path)
    return len(syms) == 1 and "HYPE" not in syms


def is_baseline_like(card: "HypothesisCard") -> bool:
    """Return True if the card is baseline_like and should be archived.

    Definition: shareable_structure tier with novelty_score <= 0.30.
    These are structural patterns at the minimum novelty floor — known expected
    relationships (e.g., regime transitions, execution-regime bridges) that do
    not carry distinctive operator value. Archived for potential promotion if
    confirmed by follow-up evidence.
    """
    return (
        card.secrecy_level == "shareable_structure"
        and card.novelty_score <= 0.30
        and not is_null_baseline(card)  # avoid double-counting
    )


def classify_surface_tier(card: "HypothesisCard") -> str:
    """Classify a card into SURFACE_ACTIVE, SURFACE_ARCHIVE, or SURFACE_DROP.

    Rules (in priority order):
    1. null_baseline → SURFACE_DROP
    2. baseline_like → SURFACE_ARCHIVE
    3. Everything else → SURFACE_ACTIVE
    """
    if is_null_baseline(card):
        return SURFACE_DROP
    if is_baseline_like(card):
        return SURFACE_ARCHIVE
    return SURFACE_ACTIVE


def apply_surface_policy(
    cards: list["HypothesisCard"],
) -> dict[str, list["HypothesisCard"]]:
    """Apply surface policy to a list of cards.

    Returns a dict with keys SURFACE_ACTIVE, SURFACE_ARCHIVE, SURFACE_DROP.
    """
    result: dict[str, list["HypothesisCard"]] = {
        SURFACE_ACTIVE: [],
        SURFACE_ARCHIVE: [],
        SURFACE_DROP: [],
    }
    for card in cards:
        tier = classify_surface_tier(card)
        result[tier].append(card)
    return result


_ACTION_SECRECY: frozenset[str] = frozenset({"private_alpha", "internal_watchlist"})
_REVIEWS_PER_DAY: float = 2.0


def compute_surface_metrics(
    cards: list["HypothesisCard"],
    surface_tiers: dict[str, list["HypothesisCard"]],
    reviews_per_day: float = _REVIEWS_PER_DAY,
) -> dict:
    """Compute surface policy metrics for reporting.

    Args:
        cards:          All pre-policy cards (for total_input denominator).
        surface_tiers:  Output of apply_surface_policy().
        reviews_per_day: Assumed daily review cadence for burden calculation.

    Returns:
        Dict with keys: total_input, total_surfaced, action_worthy,
        attention_worthy, redundant, archived, pruning_rate,
        reviews_per_day, operator_burden, missed_critical, resurface_potential.
    """
    active = surface_tiers[SURFACE_ACTIVE]
    archived = surface_tiers[SURFACE_ARCHIVE]
    dropped = surface_tiers[SURFACE_DROP]

    action_worthy = [c for c in active if c.secrecy_level in _ACTION_SECRECY]
    attention_worthy = [c for c in active if c.secrecy_level not in _ACTION_SECRECY]
    missed_critical = sum(
        1 for c in archived + dropped if c.secrecy_level in _ACTION_SECRECY
    )
    total_surfaced = len(active)
    return {
        "total_input": len(cards),
        "total_surfaced": total_surfaced,
        "action_worthy": len(action_worthy),
        "attention_worthy": len(attention_worthy),
        "redundant": len(dropped),
        "archived": len(archived),
        "pruning_rate": round(1.0 - total_surfaced / max(len(cards), 1), 4),
        "reviews_per_day": reviews_per_day,
        "operator_burden": round(reviews_per_day * total_surfaced, 2),
        "missed_critical": missed_critical,
        "resurface_potential": len(archived),
    }
