"""HypothesisCard schema for KG Discovery Engine."""

from __future__ import annotations
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Module-level constants for categorical field validation
# ---------------------------------------------------------------------------

VALID_MARKET_SCOPES: tuple[str, ...] = (
    "microstructure", "cross_asset", "execution", "regime",
)

VALID_REGIME_CONDITIONS: tuple[str, ...] = (
    "high_volatility", "calm", "funding_extreme", "any",
)

VALID_EDGE_TYPES: tuple[str, ...] = (
    "leads_to", "amplifies", "precedes_move_in",
)

VALID_SECRECY_LEVELS: tuple[str, ...] = (
    "private_alpha", "internal_watchlist", "shareable_structure", "discard",
)

VALID_VALIDATION_STATUSES: tuple[str, ...] = (
    "untested", "weakly_supported", "reproduced", "invalidated", "decayed",
)

VALID_DECAY_RISKS: tuple[str, ...] = ("low", "medium", "high")

SECRECY_DISPLAY: dict[str, str] = {
    "private_alpha": "PRIVATE ALPHA — Do not share",
    "internal_watchlist": "Internal Watchlist — Team only",
    "shareable_structure": "Shareable Structure — OK to discuss pattern",
    "discard": "DISCARD — No edge found",
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class HypothesisCard:
    """Structured record of a single market hypothesis discovered by the KG pipeline.

    Each card captures the full provenance, scoring, and operational metadata
    needed to evaluate, track decay, and act on a hypothesis.
    """

    hypothesis_id: str
    created_at: str
    symbols: list[str]
    timeframe: str
    market_scope: str
    hypothesis_text: str
    operator_chain: list[str]
    provenance_path: list[str]
    source_streams: list[str]
    regime_condition: str
    expected_edge_type: str
    estimated_half_life: str
    actionability_score: float
    novelty_score: float
    reproducibility_score: float
    secrecy_level: str
    validation_status: str
    decay_risk: str
    next_recommended_test: str

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def secrecy_label(self) -> str:
        """Return a human-readable display string for the secrecy level."""
        return SECRECY_DISPLAY.get(self.secrecy_level, self.secrecy_level)

    # -----------------------------------------------------------------------
    # Serialisation helpers
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the card to a plain dict suitable for JSON storage."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "created_at": self.created_at,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "market_scope": self.market_scope,
            "hypothesis_text": self.hypothesis_text,
            "operator_chain": self.operator_chain,
            "provenance_path": self.provenance_path,
            "source_streams": self.source_streams,
            "regime_condition": self.regime_condition,
            "expected_edge_type": self.expected_edge_type,
            "estimated_half_life": self.estimated_half_life,
            "actionability_score": self.actionability_score,
            "novelty_score": self.novelty_score,
            "reproducibility_score": self.reproducibility_score,
            "secrecy_level": self.secrecy_level,
            "validation_status": self.validation_status,
            "decay_risk": self.decay_risk,
            "next_recommended_test": self.next_recommended_test,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HypothesisCard":
        """Deserialise a HypothesisCard from a plain dict."""
        return cls(
            hypothesis_id=d["hypothesis_id"],
            created_at=d["created_at"],
            symbols=d["symbols"],
            timeframe=d["timeframe"],
            market_scope=d["market_scope"],
            hypothesis_text=d["hypothesis_text"],
            operator_chain=d["operator_chain"],
            provenance_path=d["provenance_path"],
            source_streams=d["source_streams"],
            regime_condition=d["regime_condition"],
            expected_edge_type=d["expected_edge_type"],
            estimated_half_life=d["estimated_half_life"],
            actionability_score=float(d["actionability_score"]),
            novelty_score=float(d["novelty_score"]),
            reproducibility_score=float(d["reproducibility_score"]),
            secrecy_level=d["secrecy_level"],
            validation_status=d["validation_status"],
            decay_risk=d["decay_risk"],
            next_recommended_test=d["next_recommended_test"],
        )
