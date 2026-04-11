"""RunStatus schema for tracking KG discovery pipeline execution."""

from __future__ import annotations
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

VALID_PHASES: tuple[str, ...] = (
    "ingestion",
    "state_extraction",
    "kg_build",
    "operator",
    "evaluation",
    "complete",
    "failed",
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class RunStatus:
    """Status of a KG discovery pipeline run.

    Tracks progress through each pipeline phase, counts of processed
    entities, and any error information for post-run diagnostics.
    """

    run_id: str                    # "RUN-20260412-001"
    started_at: str                # ISO timestamp
    completed_at: str | None
    phase: str                     # one of VALID_PHASES
    symbols: list[str]
    timeframe: str
    n_candles_loaded: int
    n_state_events: int
    n_kg_nodes: dict[str, int]     # {"microstructure": 12, "cross_asset": 8}
    n_candidates: int
    n_hypotheses_stored: int
    error: str | None
    notes: str

    # -----------------------------------------------------------------------
    # Status helpers
    # -----------------------------------------------------------------------

    def is_complete(self) -> bool:
        """Return True if the run finished successfully."""
        return self.phase == "complete" and self.error is None

    def is_failed(self) -> bool:
        """Return True if the run terminated with an error."""
        return self.phase == "failed" or self.error is not None

    def total_kg_nodes(self) -> int:
        """Return the total number of KG nodes across all scopes."""
        return sum(self.n_kg_nodes.values())

    # -----------------------------------------------------------------------
    # Serialisation helpers
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON storage."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "phase": self.phase,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "n_candles_loaded": self.n_candles_loaded,
            "n_state_events": self.n_state_events,
            "n_kg_nodes": self.n_kg_nodes,
            "n_candidates": self.n_candidates,
            "n_hypotheses_stored": self.n_hypotheses_stored,
            "error": self.error,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RunStatus":
        """Deserialise a RunStatus from a plain dict."""
        return cls(
            run_id=d["run_id"],
            started_at=d["started_at"],
            completed_at=d.get("completed_at"),
            phase=d["phase"],
            symbols=d["symbols"],
            timeframe=d["timeframe"],
            n_candles_loaded=int(d.get("n_candles_loaded", 0)),
            n_state_events=int(d.get("n_state_events", 0)),
            n_kg_nodes=d.get("n_kg_nodes", {}),
            n_candidates=int(d.get("n_candidates", 0)),
            n_hypotheses_stored=int(d.get("n_hypotheses_stored", 0)),
            error=d.get("error"),
            notes=d.get("notes", ""),
        )

    @classmethod
    def new(cls, run_id: str, started_at: str, symbols: list[str],
            timeframe: str) -> "RunStatus":
        """Create a fresh RunStatus at the start of a pipeline run."""
        return cls(
            run_id=run_id,
            started_at=started_at,
            completed_at=None,
            phase="ingestion",
            symbols=symbols,
            timeframe=timeframe,
            n_candles_loaded=0,
            n_state_events=0,
            n_kg_nodes={},
            n_candidates=0,
            n_hypotheses_stored=0,
            error=None,
            notes="",
        )
