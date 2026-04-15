"""Run 028: Card archive policy — lifecycle extension beyond expired.

Extends the Run 027 delivery state machine with two new states:

  archive          — card that has aged past the expiry grace period;
                     removed from the active deck, stored in archive store.
  archive_resurface — archived card returned to operator attention because
                     a new card in the same (branch, grammar_family) achieved
                     a high enough score to suggest the hypothesis is alive again.

Full lifecycle:
  fresh → active → aging → digest_only → expired → archive → [archive_resurface]

Archive trigger:
  A card transitions expired → archive when:
    age_min >= (EXPIRY_RATIO + archive_grace_factor) * half_life_min

  Default archive_grace_factor = 1.0 means archive at 3.5× HL:
    2.5× expiry threshold  +  1.0× grace period

  Rationale: give the operator at least one more cadence window after expiry
  before the card disappears entirely.  Immediate archival at 2.5× HL would
  hide cards that were just reviewed as digest_only.

Resurfacing trigger:
  An archived card `arc` is resurfaced when ALL of:
    1. A new deck card `new` shares (branch, grammar_family) with `arc`
    2. new.composite_score >= resurface_threshold (default 0.70)
    3. arc has been in archive >= resurface_min_archive_age_min

  Why score threshold on the NEW card (not the archived one):
    The archived card's score is stale.  We want to know whether the
    hypothesis family is currently active again, which is best indicated
    by a strong new card in the same family — not by the archived card
    having had a high score in the past.

Archive churn:
  High churn (many cards archiving and resurfacing quickly) indicates the
  archive_grace_factor is too aggressive (too short).  Target: churn < 20%.

Metrics:
  archive_rate_per_session  — cards archived per 8h session
  resurface_rate            — fraction of archived cards that resurface
  archive_churn             — resurface within 2× half_life of archiving
  avg_archive_age_min       — how long cards spend in archive before resurface
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .delivery_state import (
    DeliveryCard,
    generate_cards,
    STATE_EXPIRED,
    STATE_DIGEST_ONLY,
    STATE_AGING,
    STATE_ACTIVE,
    STATE_FRESH,
    _HL_BY_TIER,
)

# ---------------------------------------------------------------------------
# Archive state constants
# ---------------------------------------------------------------------------

STATE_ARCHIVE: str = "archive"
STATE_ARCHIVE_RESURFACE: str = "archive_resurface"

# Ratio at which a card is considered expired (from delivery_state.py)
_EXPIRY_RATIO: float = 2.5


# ---------------------------------------------------------------------------
# Archive policy configuration
# ---------------------------------------------------------------------------

@dataclass
class ArchivePolicyConfig:
    """Tunable parameters for one archive policy configuration.

    Attributes:
        name:                     Human-readable config label.
        archive_grace_factor:     Additional HL multiples beyond expiry_ratio
                                  before archiving.  archive at
                                  (2.5 + grace) * HL.
        resurface_threshold:      Min composite_score on a NEW same-family card
                                  to trigger resurfacing of an archived card.
        resurface_min_archive_age_min:
                                  Min time a card must spend in archive before
                                  it can be resurfaced (prevents instant churn).
    """

    name: str
    archive_grace_factor: float = 1.0
    resurface_threshold: float = 0.70
    resurface_min_archive_age_min: float = 60.0


# Three archive configs to compare in Run 028
ARCHIVE_CONFIG_TIGHT = ArchivePolicyConfig(
    name="tight",
    archive_grace_factor=0.5,
    resurface_threshold=0.70,
    resurface_min_archive_age_min=30.0,
)
ARCHIVE_CONFIG_STANDARD = ArchivePolicyConfig(
    name="standard",
    archive_grace_factor=1.0,
    resurface_threshold=0.70,
    resurface_min_archive_age_min=60.0,
)
ARCHIVE_CONFIG_RELAXED = ArchivePolicyConfig(
    name="relaxed",
    archive_grace_factor=2.0,
    resurface_threshold=0.75,
    resurface_min_archive_age_min=120.0,
)

ALL_ARCHIVE_CONFIGS = [ARCHIVE_CONFIG_TIGHT, ARCHIVE_CONFIG_STANDARD, ARCHIVE_CONFIG_RELAXED]


# ---------------------------------------------------------------------------
# Archive record
# ---------------------------------------------------------------------------

@dataclass
class ArchiveRecord:
    """Metadata about an archived card.

    Attributes:
        card:                Original DeliveryCard.
        archived_at_min:     Session time when the card was archived.
        resurfaced_at_min:   Session time when the card was resurfaced
                             (None if still in archive).
        resurface_trigger_id:card_id of the new card that triggered resurfacing.
        churn:               True if resurfaced within 2× HL of archiving.
    """

    card: DeliveryCard
    archived_at_min: float
    resurfaced_at_min: Optional[float] = None
    resurface_trigger_id: Optional[str] = None
    churn: bool = False

    @property
    def is_resurfaced(self) -> bool:
        """Return True if this card has been resurfaced."""
        return self.resurfaced_at_min is not None

    def archive_age_at(self, t: float) -> float:
        """Return how long the card has been in archive at time t."""
        return t - self.archived_at_min

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "card_id": self.card.card_id,
            "branch": self.card.branch,
            "grammar_family": self.card.grammar_family,
            "asset": self.card.asset,
            "tier": self.card.tier,
            "composite_score": round(self.card.composite_score, 4),
            "half_life_min": self.card.half_life_min,
            "archived_at_min": round(self.archived_at_min, 1),
            "resurfaced_at_min": (
                round(self.resurfaced_at_min, 1)
                if self.resurfaced_at_min is not None else None
            ),
            "resurface_trigger_id": self.resurface_trigger_id,
            "churn": self.churn,
        }


@dataclass
class ArchiveSurfaceItem:
    """A resurfaced archive card shown to the operator.

    Attributes:
        archive_record:     The original ArchiveRecord.
        trigger_card:       New deck card that triggered resurfacing.
        surface_time_min:   When this item was surfaced.
    """

    archive_record: ArchiveRecord
    trigger_card: DeliveryCard
    surface_time_min: float

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "state": STATE_ARCHIVE_RESURFACE,
            "card_id": self.archive_record.card.card_id,
            "branch": self.archive_record.card.branch,
            "grammar_family": self.archive_record.card.grammar_family,
            "asset": self.archive_record.card.asset,
            "original_score": round(self.archive_record.card.composite_score, 4),
            "trigger_card_id": self.trigger_card.card_id,
            "trigger_score": round(self.trigger_card.composite_score, 4),
            "archive_age_min": round(
                self.surface_time_min - self.archive_record.archived_at_min, 1
            ),
            "surface_time_min": round(self.surface_time_min, 1),
        }


# ---------------------------------------------------------------------------
# Archive policy engine
# ---------------------------------------------------------------------------

class ArchivePolicyEngine:
    """Manage the archive state machine for a card deck.

    Args:
        config:  ArchivePolicyConfig controlling archive and resurface thresholds.
    """

    def __init__(self, config: ArchivePolicyConfig) -> None:
        self.config = config
        self._archive: list[ArchiveRecord] = []
        self._archived_ids: set[str] = set()

    @property
    def archive_records(self) -> list[ArchiveRecord]:
        """All archive records created so far."""
        return list(self._archive)

    def _archive_threshold(self, half_life_min: float) -> float:
        """Compute age_min at which a card transitions to archive.

        Args:
            half_life_min: Card's half-life in minutes.

        Returns:
            Age in minutes at which the card should be archived.
        """
        return (_EXPIRY_RATIO + self.config.archive_grace_factor) * half_life_min

    def step(
        self,
        deck: list[DeliveryCard],
        elapsed_min: float,
    ) -> tuple[list[DeliveryCard], list[ArchiveSurfaceItem]]:
        """Process one time step: archive eligible cards; check for resurfaces.

        Cards that exceed the archive threshold are moved from the deck to the
        archive store.  Archived cards whose family is re-activated by a high-
        scoring deck card are returned as ArchiveSurfaceItems.

        Args:
            deck:         Current active deck (mutated in-place: archived cards removed).
            elapsed_min:  Current session time.

        Returns:
            Tuple of (remaining_deck, resurface_items).
              remaining_deck:   deck with archived cards removed.
              resurface_items:  ArchiveSurfaceItems ready for operator display.
        """
        remaining: list[DeliveryCard] = []
        newly_archived: list[ArchiveRecord] = []

        for card in deck:
            threshold = self._archive_threshold(card.half_life_min)
            if card.age_min >= threshold and card.card_id not in self._archived_ids:
                rec = ArchiveRecord(
                    card=card,
                    archived_at_min=elapsed_min,
                )
                self._archive.append(rec)
                self._archived_ids.add(card.card_id)
                newly_archived.append(rec)
            else:
                remaining.append(card)

        # Check for resurface triggers
        resurface_items: list[ArchiveSurfaceItem] = []
        for rec in self._archive:
            if rec.is_resurfaced:
                continue
            archive_age = rec.archive_age_at(elapsed_min)
            if archive_age < self.config.resurface_min_archive_age_min:
                continue
            # Check if any deck card shares family and exceeds threshold
            fk = (rec.card.branch, rec.card.grammar_family)
            for deck_card in remaining:
                dk = (deck_card.branch, deck_card.grammar_family)
                if (
                    dk == fk
                    and deck_card.composite_score >= self.config.resurface_threshold
                    and deck_card.card_id != rec.card.card_id
                ):
                    # Mark as resurfaced
                    rec.resurfaced_at_min = elapsed_min
                    rec.resurface_trigger_id = deck_card.card_id
                    rec.churn = archive_age <= 2.0 * rec.card.half_life_min
                    resurface_items.append(ArchiveSurfaceItem(
                        archive_record=rec,
                        trigger_card=deck_card,
                        surface_time_min=elapsed_min,
                    ))
                    break  # one trigger per archived card

        return remaining, resurface_items


# ---------------------------------------------------------------------------
# Archive simulation
# ---------------------------------------------------------------------------

@dataclass
class ArchiveSessionResult:
    """Aggregate metrics for one full session under an archive policy config.

    Attributes:
        config_name:            ArchivePolicyConfig.name.
        n_archived:             Total cards moved to archive.
        n_resurfaced:           Archived cards that re-entered the deck.
        archive_rate_per_8h:    Cards archived per 8h session.
        resurface_rate:         n_resurfaced / n_archived.
        archive_churn:          Fraction of resurfaced cards marked churn.
        avg_archive_age_min:    Mean archive age at time of resurface.
        archive_records:        Raw ArchiveRecord list.
    """

    config_name: str
    n_archived: int
    n_resurfaced: int
    archive_rate_per_8h: float
    resurface_rate: float
    archive_churn: float
    avg_archive_age_min: float
    archive_records: list[ArchiveRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "config_name": self.config_name,
            "n_archived": self.n_archived,
            "n_resurfaced": self.n_resurfaced,
            "archive_rate_per_8h": round(self.archive_rate_per_8h, 2),
            "resurface_rate": round(self.resurface_rate, 4),
            "archive_churn": round(self.archive_churn, 4),
            "avg_archive_age_min": round(self.avg_archive_age_min, 1),
        }


def simulate_archive_session(
    seed: int,
    config: ArchivePolicyConfig,
    n_cards: int = 20,
    session_hours: int = 8,
    eval_interval_min: int = 15,
    perturb_prob: float = 0.20,
    max_delta: float = 0.15,
) -> ArchiveSessionResult:
    """Simulate one session of the archive state machine.

    Cards start fresh at t=0.  Every eval_interval_min minutes, cards age and
    the archive engine checks for archive/resurface transitions.  Score
    perturbations can elevate co-family cards above the resurface threshold.

    Args:
        seed:             RNG seed.
        config:           ArchivePolicyConfig.
        n_cards:          Initial deck size.
        session_hours:    Total session length.
        eval_interval_min:How often to step the engine.
        perturb_prob:     Fraction of cards perturbed per cycle.
        max_delta:        Max score delta per cycle.

    Returns:
        ArchiveSessionResult with per-session archive metrics.
    """
    import copy

    rng = random.Random(seed)
    cards = generate_cards(seed=seed, n_cards=n_cards)
    engine = ArchivePolicyEngine(config=config)

    session_min = session_hours * 60
    eval_times = list(range(eval_interval_min, session_min + 1, eval_interval_min))

    all_resurface_items: list[ArchiveSurfaceItem] = []

    for t in eval_times:
        deck = copy.deepcopy(cards)
        # Age all cards
        for card in deck:
            card.age_min = float(t)

        # Perturb scores (simulates live re-evaluation)
        for card in deck:
            if rng.random() < perturb_prob:
                delta = rng.uniform(-max_delta, max_delta)
                card.composite_score = max(0.0, min(1.0, card.composite_score + delta))
                card.composite_score = round(card.composite_score, 4)

        remaining, resurface_items = engine.step(deck, float(t))
        all_resurface_items.extend(resurface_items)

    # Aggregate
    records = engine.archive_records
    n_archived = len(records)
    resurfaced = [r for r in records if r.is_resurfaced]
    n_resurfaced = len(resurfaced)

    archive_rate = n_archived / (session_hours / 8.0)
    resurface_rate = n_resurfaced / max(n_archived, 1)

    churn_count = sum(1 for r in resurfaced if r.churn)
    archive_churn = churn_count / max(n_resurfaced, 1) if n_resurfaced > 0 else 0.0

    resurface_ages = [
        r.resurfaced_at_min - r.archived_at_min
        for r in resurfaced
        if r.resurfaced_at_min is not None
    ]
    avg_archive_age = sum(resurface_ages) / len(resurface_ages) if resurface_ages else 0.0

    return ArchiveSessionResult(
        config_name=config.name,
        n_archived=n_archived,
        n_resurfaced=n_resurfaced,
        archive_rate_per_8h=archive_rate,
        resurface_rate=resurface_rate,
        archive_churn=archive_churn,
        avg_archive_age_min=avg_archive_age,
        archive_records=records,
    )


def run_archive_comparison(
    seeds: list[int],
    configs: Optional[list[ArchivePolicyConfig]] = None,
    n_cards: int = 20,
    session_hours: int = 8,
) -> dict[str, ArchiveSessionResult]:
    """Run all archive configs over multiple seeds and return averaged results.

    Args:
        seeds:         RNG seeds to average over.
        configs:       Archive configs to compare (default: all 3).
        n_cards:       Cards per session.
        session_hours: Session duration.

    Returns:
        Dict mapping config_name → ArchiveSessionResult (averaged).
    """
    if configs is None:
        configs = ALL_ARCHIVE_CONFIGS

    per_config: dict[str, list[ArchiveSessionResult]] = {c.name: [] for c in configs}

    for seed in seeds:
        for config in configs:
            result = simulate_archive_session(
                seed=seed,
                config=config,
                n_cards=n_cards,
                session_hours=session_hours,
            )
            per_config[config.name].append(result)

    averaged: dict[str, ArchiveSessionResult] = {}
    for config_name, results in per_config.items():
        n = len(results)
        averaged[config_name] = ArchiveSessionResult(
            config_name=config_name,
            n_archived=round(sum(r.n_archived for r in results) / n, 1),
            n_resurfaced=round(sum(r.n_resurfaced for r in results) / n, 1),
            archive_rate_per_8h=round(sum(r.archive_rate_per_8h for r in results) / n, 2),
            resurface_rate=round(sum(r.resurface_rate for r in results) / n, 4),
            archive_churn=round(sum(r.archive_churn for r in results) / n, 4),
            avg_archive_age_min=round(sum(r.avg_archive_age_min for r in results) / n, 1),
        )

    return averaged
