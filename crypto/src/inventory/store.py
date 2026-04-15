"""In-memory hypothesis card store with JSON persistence.

The store supports:
- Append (always creates a new version, never mutates)
- Query by secrecy level, validation status, or composite score threshold
- Novelty distance (used by the eval layer to compute novelty scores)
- JSON export to the run output directory
"""

import json
import os
from typing import Optional

from ..schema.hypothesis_card import HypothesisCard
from ..schema.task_status import SecrecyLevel, ValidationStatus


class HypothesisInventory:
    """Append-only store for HypothesisCards.

    Why append-only: cards are immutable artefacts.  A correction is always
    a new version, preserving full audit trail.  This mirrors the design in
    docs/hypothesis_card_schema.md §Immutability Convention.
    """

    def __init__(self) -> None:
        self._cards: list[HypothesisCard] = []

    def add(self, card: HypothesisCard) -> None:
        """Append a card to the inventory."""
        self._cards.append(card)

    def all(self) -> list[HypothesisCard]:
        """Return all cards (newest first within same card_id)."""
        return list(self._cards)

    def query(
        self,
        secrecy: Optional[SecrecyLevel] = None,
        validation: Optional[ValidationStatus] = None,
        min_composite: float = 0.0,
    ) -> list[HypothesisCard]:
        """Filter cards by optional criteria."""
        results = self._cards
        if secrecy is not None:
            results = [c for c in results if c.secrecy_level == secrecy]
        if validation is not None:
            results = [c for c in results if c.validation_status == validation]
        results = [c for c in results if c.composite_score >= min_composite]
        return sorted(results, key=lambda c: c.composite_score, reverse=True)

    def novelty_distance(self, claim: str) -> float:
        """Estimate novelty of a new claim relative to existing inventory.

        Uses simple Jaccard similarity on word sets as a proxy.  Returns
        a value in [0.0, 1.0] where 1.0 = completely novel.

        Why word-set Jaccard: avoids external NLP dependencies while still
        capturing lexical overlap.  Sufficient for MVP; can be upgraded to
        embedding similarity without changing the interface.
        """
        if not self._cards:
            return 1.0
        new_words = set(claim.lower().split())
        max_sim = 0.0
        for card in self._cards:
            existing_words = set(card.claim.lower().split())
            union = new_words | existing_words
            intersection = new_words & existing_words
            sim = len(intersection) / len(union) if union else 0.0
            max_sim = max(max_sim, sim)
        return round(1.0 - max_sim, 4)

    def save(self, path: str) -> None:
        """Serialise all cards to a JSON file at `path`."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = [c.to_dict() for c in self._cards]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: str) -> None:
        """Not implemented for MVP — inventory is rebuilt each pipeline run.

        Why: loading requires reconstructing enum fields from strings, which
        needs a full deserialiser.  Deferred until inventory querying across
        runs is required.
        """
        raise NotImplementedError(
            "Cross-run inventory loading is out of scope for MVP. "
            "Re-run the pipeline to rebuild the inventory."
        )

    def __len__(self) -> int:
        return len(self._cards)
