"""Run 027/028: Delivery-state staging, family digest/collapse, and archive engine.

Models operator-facing delivery lifecycle for FusionCards:

  fresh       — created/updated within 50% of half-life; full-priority review
  active      — 50–100% of half-life elapsed; normal review
  aging       — 100–175% of half-life; approaching stale, review before it expires
  digest_only — 175–250% of half-life; show only in collapsed family digest
  expired     — beyond 250% of half-life; suppress from all surfaces
  archived    — Run 028 addition: explicitly pruned after archive_retention_min;
                can re-surface if same (branch, grammar_family) recurs within
                resurface_window_min.

Also implements family-level digest collapse (Run 027):
  Cards sharing the same (branch, grammar_family) across multiple assets
  (e.g., positioning_unwind on HYPE/BTC/ETH/SOL) are collapsed into one
  DigestCard.  The lead asset (highest composite_score) is shown
  prominently; the remaining co-assets are listed in one line.

Why digest collapse instead of hard dedup:
  Full dedup discards co-asset signal (different HL trajectories, possible
  divergence).  Digest retains the lead card at full detail while still
  surfacing co-asset context in a single line.  Information loss is
  bounded to non-lead assets only.

Why age/HL ratio thresholds at 0.5 / 1.0 / 1.75 / 2.5 (not 1.0 / 2.0):
  At HL=40 min a 60-min cadence hits ratio=1.5 (aging, operator gets one
  more chance).  A 120-min cadence hits ratio=3.0 (expired — confirms the
  HL vs window mismatch identified in Run 026).  Thresholds at exact
  multiples of 1.0 would make the 60-min cadence appear fine; the 0.5
  granularity exposes the transition zone.

Archive lifecycle (Run 028):
  expired → archived: when age_min >= archive_retention_min (default: 5 * half_life_min).
    Why 5x half-life: gives a 2.5x buffer beyond the 2.5x expiry threshold, keeping
    cards available for re-surface matching during a full trading session (≈200 min
    for HL=40 actionable_watch tier) without inflating the query set indefinitely.
  archived → fresh (re-surface): when a new card arrives with the same
    (branch, grammar_family) within resurface_window_min (default: 120 min).
    Why 120 min: covers 2–3 detection cycles for the shortest HL tier (40 min),
    allowing pattern recurrence to be treated as confirmation rather than noise.
  Archive retention: archived cards are deleted after archive_max_age_min (default:
    480 min / 8 h).  A full trading session is the natural retention horizon; cards
    older than that cannot meaningfully influence current positioning decisions.
"""
from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Delivery state thresholds (age / half_life_min ratio)
# ---------------------------------------------------------------------------

_FRESH_MAX: float = 0.5
_ACTIVE_MAX: float = 1.0
_AGING_MAX: float = 1.75
_DIGEST_MAX: float = 2.5
# ratio >= _DIGEST_MAX → expired

# Archive retention multiplier (age_min / half_life_min before expired → archived)
# Must be > _DIGEST_MAX (2.5) to only archive cards that have fully expired.
_ARCHIVE_RATIO: float = 5.0
# Re-surface window in minutes: archived card re-surfaces if same family recurs within this window
_DEFAULT_RESURFACE_WINDOW_MIN: int = 120
# Hard deletion threshold: archived cards older than this are removed from the pool
_DEFAULT_ARCHIVE_MAX_AGE_MIN: int = 480

# Delivery states (ordered worst → best for surfacing)
STATE_EXPIRED: str = "expired"
STATE_DIGEST_ONLY: str = "digest_only"
STATE_AGING: str = "aging"
STATE_ACTIVE: str = "active"
STATE_FRESH: str = "fresh"
# Run 028: archive state (post-expired, queryable but not surfaced)
STATE_ARCHIVED: str = "archived"

# States that the operator sees during a full review (before any collapse)
_SURFACED_STATES: frozenset[str] = frozenset([STATE_FRESH, STATE_ACTIVE, STATE_AGING])
# States eligible for digest-only surface (still shown but collapsed)
_DIGEST_STATES: frozenset[str] = frozenset([STATE_DIGEST_ONLY])


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DeliveryCard:
    """A FusionCard annotated with delivery metadata.

    Attributes:
        card_id:         Stable identifier.
        branch:          Hypothesis branch (positioning_unwind, beta_reversion, …).
        grammar_family:  Coarser family label used for collapse grouping.
        asset:           Primary asset symbol (HYPE / BTC / ETH / SOL).
        tier:            Decision tier from I1.
        composite_score: Score in [0, 1].
        half_life_min:   Nominal half-life for this card's tier (minutes).
        age_min:         Elapsed minutes since card was first surfaced.
        archived_at_min: Session-time minutes when card was moved to archive.
                         None means the card has not been archived.
        resurface_count: Number of times this card has been re-surfaced from
                         the archive pool (for diagnostics).
    """

    card_id: str
    branch: str
    grammar_family: str
    asset: str
    tier: str
    composite_score: float
    half_life_min: float
    age_min: float
    archived_at_min: Optional[float] = None
    resurface_count: int = 0

    def delivery_state(self) -> str:
        """Compute delivery state from age/half_life ratio.

        Returns STATE_ARCHIVED if the card has been explicitly archived
        (archived_at_min is set), regardless of age.  This allows
        ArchiveManager to re-surface it by clearing archived_at_min.

        Why archived overrides the ratio check:
          Once the archive decision is made externally (by ArchiveManager),
          the card must stay hidden even if its ratio would re-enter an
          active state due to a batch refresh resetting age_min.  Archive
          is a deliberate policy action, not an age computation.

        Returns:
            One of the six STATE_* constants (including STATE_ARCHIVED).
        """
        if self.archived_at_min is not None:
            return STATE_ARCHIVED
        if self.half_life_min <= 0:
            return STATE_EXPIRED
        ratio = self.age_min / self.half_life_min
        if ratio < _FRESH_MAX:
            return STATE_FRESH
        if ratio < _ACTIVE_MAX:
            return STATE_ACTIVE
        if ratio < _AGING_MAX:
            return STATE_AGING
        if ratio < _DIGEST_MAX:
            return STATE_DIGEST_ONLY
        return STATE_EXPIRED

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "card_id": self.card_id,
            "branch": self.branch,
            "grammar_family": self.grammar_family,
            "asset": self.asset,
            "tier": self.tier,
            "composite_score": round(self.composite_score, 4),
            "half_life_min": self.half_life_min,
            "age_min": round(self.age_min, 1),
            "delivery_state": self.delivery_state(),
            "age_hl_ratio": round(self.age_min / max(self.half_life_min, 1), 3),
            "archived_at_min": self.archived_at_min,
            "resurface_count": self.resurface_count,
        }


@dataclass
class DigestCard:
    """Collapsed representation of same-family multi-asset cards.

    Attributes:
        family_key:       Tuple of (branch, grammar_family) used as collapse key.
        lead_card:        Highest-scoring card (shown in full).
        co_assets:        Asset symbols of cards collapsed into this digest.
        co_scores:        Scores of co-asset cards (for info_loss computation).
        info_loss_score:  Fraction of unique content suppressed (0.0 = no loss).
        delivery_state:   Delivery state of the lead card.
    """

    family_key: tuple[str, str]
    lead_card: DeliveryCard
    co_assets: list[str] = field(default_factory=list)
    co_scores: list[float] = field(default_factory=list)
    info_loss_score: float = 0.0
    delivery_state: str = STATE_ACTIVE

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        return {
            "family_key": f"{self.family_key[0]}:{self.family_key[1]}",
            "lead_asset": self.lead_card.asset,
            "lead_score": round(self.lead_card.composite_score, 4),
            "co_assets": self.co_assets,
            "co_scores": [round(s, 4) for s in self.co_scores],
            "n_collapsed": len(self.co_assets) + 1,
            "info_loss_score": round(self.info_loss_score, 4),
            "delivery_state": self.delivery_state,
        }


# ---------------------------------------------------------------------------
# Archive manager (Run 028)
# ---------------------------------------------------------------------------

class ArchiveManager:
    """Manage the archive pool: expired→archived transition and re-surface logic.

    Why a separate class (not baked into DeliveryStateEngine):
      ArchiveManager maintains stateful knowledge of which families have
      recently been archived.  This state would pollute the stateless
      snapshot-per-review model of DeliveryStateEngine.  Keeping them
      separate lets callers opt into archive semantics without breaking
      existing first_review / batch_refresh simulations.

    Archive rules:
      1. expired → archived: when age_min >= archive_retention_min
         (default: _ARCHIVE_RATIO * half_life_min = 5x HL).
      2. archived + same-family recurrence within resurface_window_min →
         card is cloned as fresh (age_min=0, resurface_count+1).
      3. archived cards older than archive_max_age_min are hard-deleted from
         the pool (no further re-surface possible).

    Args:
        resurface_window_min:    Window for same-family recurrence to trigger
                                 re-surface (default 120 min).
        archive_max_age_min:     Hard deletion threshold for archived cards
                                 (default 480 min / 8 h = one trading session).
        family_max_age_overrides: Per-grammar-family override for archive_max_age_min.
                                 Cards whose grammar_family appears in this dict use
                                 the mapped value instead of archive_max_age_min.
                                 Example: {"cross_asset": 720, "reversion": 720}
                                 Families absent from the dict use archive_max_age_min.
    """

    def __init__(
        self,
        resurface_window_min: int = _DEFAULT_RESURFACE_WINDOW_MIN,
        archive_max_age_min: int = _DEFAULT_ARCHIVE_MAX_AGE_MIN,
        family_max_age_overrides: Optional[dict[str, int]] = None,
    ) -> None:
        self.resurface_window_min = resurface_window_min
        self.archive_max_age_min = archive_max_age_min
        self.family_max_age_overrides: dict[str, int] = family_max_age_overrides or {}
        # Archive pool: card_id → (card, archived_at_min)
        self._pool: dict[str, tuple[DeliveryCard, float]] = {}

    def _effective_max_age(self, card: DeliveryCard) -> int:
        """Return effective archive_max_age_min for a card, applying per-family overrides.

        Why per-family override (not a global bump):
          Families with longer inter-signal gaps (e.g. cross_asset, reversion) benefit
          from a wider retention window, while high-frequency families (momentum, unwind)
          would bloat the pool unnecessarily with stale context.

        Args:
            card: The archived DeliveryCard.

        Returns:
            Effective max-age in minutes for this card's grammar_family.
        """
        return self.family_max_age_overrides.get(card.grammar_family, self.archive_max_age_min)

    def apply_archive_transitions(
        self, cards: list[DeliveryCard], current_time_min: float
    ) -> list[DeliveryCard]:
        """Move expired cards into the archive pool when retention threshold hit.

        Modifies cards in-place: sets archived_at_min on cards that cross
        the archive threshold.  Does NOT remove them from the list — callers
        decide what to do with archived cards.

        Why we set archived_at_min rather than deleting the card:
          Keeping the card object alive (with STATE_ARCHIVED) lets the
          push-surfacing engine query the pool for re-surface candidates
          without maintaining a separate data structure.  The card is still
          queryable; it just doesn't render in reviews.

        Args:
            cards:            Current card list (mutated in-place).
            current_time_min: Current session time in minutes.

        Returns:
            Same list (mutated).
        """
        for card in cards:
            if card.archived_at_min is not None:
                continue
            if card.delivery_state() != STATE_EXPIRED:
                continue
            # Apply archive threshold: age_min >= _ARCHIVE_RATIO * half_life_min
            if card.age_min >= _ARCHIVE_RATIO * card.half_life_min:
                card.archived_at_min = current_time_min
                self._pool[card.card_id] = (card, current_time_min)
        return cards

    def check_resurface(
        self,
        incoming_cards: list[DeliveryCard],
        current_time_min: float,
    ) -> list[DeliveryCard]:
        """Check incoming cards for archived-family recurrence and re-surface.

        For each incoming card: if there is an archived card with matching
        (branch, grammar_family) that was archived within resurface_window_min
        ago, the archived card is cloned as a fresh card and returned as an
        additional resurfaced card.

        Why clone rather than mutate the archived card:
          The incoming card and the re-surfaced card represent two distinct
          signals (current detection + historical confirmation).  Cloning
          with a new card_id avoids card_id collisions in the deck and makes
          it unambiguous which card is the original detection vs re-surface.

        Args:
            incoming_cards:   Newly arrived batch of DeliveryCards (age_min=0).
            current_time_min: Current session time in minutes.

        Returns:
            List of additional re-surfaced cards (may be empty).
        """
        import copy

        # Prune expired archive entries before checking
        self._prune_archive(current_time_min)

        # Build family key → archived cards mapping
        archived_by_family: dict[tuple[str, str], list[DeliveryCard]] = {}
        for cid, (card, archived_at) in self._pool.items():
            key = (card.branch, card.grammar_family)
            archived_by_family.setdefault(key, []).append(card)

        resurfaced: list[DeliveryCard] = []
        triggered_families: set[tuple[str, str]] = set()

        for inc in incoming_cards:
            key = (inc.branch, inc.grammar_family)
            if key in triggered_families:
                continue  # already triggered a re-surface for this family
            if key not in archived_by_family:
                continue

            # Check recency: archived cards must be within resurface_window_min
            candidates = [
                c for c in archived_by_family[key]
                if (current_time_min - (self._pool[c.card_id][1])) <= self.resurface_window_min
            ]
            if not candidates:
                continue

            # Re-surface the highest-scoring archived candidate
            candidates.sort(key=lambda c: c.composite_score, reverse=True)
            src = candidates[0]
            new_card = copy.copy(src)
            new_card.card_id = f"{src.card_id}_rs{src.resurface_count + 1}"
            new_card.age_min = 0.0
            new_card.archived_at_min = None  # clear archive flag
            new_card.resurface_count = src.resurface_count + 1
            resurfaced.append(new_card)
            triggered_families.add(key)

            # Remove from pool to avoid double re-surface
            del self._pool[src.card_id]

        return resurfaced

    def _prune_archive(self, current_time_min: float) -> None:
        """Hard-delete archived cards older than their effective archive_max_age_min."""
        to_delete = [
            cid for cid, (card, archived_at) in self._pool.items()
            if (current_time_min - archived_at) > self._effective_max_age(card)
        ]
        for cid in to_delete:
            del self._pool[cid]

    @property
    def pool_size(self) -> int:
        """Number of cards currently in the archive pool."""
        return len(self._pool)

    def archive_summary(self) -> dict:
        """Return a summary dict for diagnostics."""
        return {
            "pool_size": self.pool_size,
            "resurface_window_min": self.resurface_window_min,
            "archive_max_age_min": self.archive_max_age_min,
            "family_max_age_overrides": dict(self.family_max_age_overrides),
        }


@dataclass
class ReviewSnapshot:
    """What the operator sees at one review point.

    Attributes:
        review_time_min:  Minutes elapsed since session start.
        cadence_min:      Configured review cadence.
        raw_cards:        All cards with their delivery states.
        surfaced_before:  Cards shown before family collapse.
        surfaced_after:   Cards shown after family collapse (digest applied).
        digests:          DigestCards created by family collapse.
        stale_count:      Cards in aging + digest_only + expired states.
        stale_rate:       stale_count / total cards.
        precision:        surfaced_after fresh+active / surfaced_after total.
        archived_count:   Cards currently in STATE_ARCHIVED (Run 028).
        resurfaced_count: Cards re-surfaced from archive this review (Run 028).
    """

    review_time_min: float
    cadence_min: int
    raw_cards: list[DeliveryCard]
    surfaced_before: list[DeliveryCard]
    surfaced_after: list[object]  # DeliveryCard | DigestCard
    digests: list[DigestCard]
    stale_count: int
    stale_rate: float
    precision: float
    archived_count: int = 0
    resurfaced_count: int = 0

    def to_dict(self) -> dict:
        """Serialise to JSON-compatible dict."""
        fresh_active = [
            c for c in self.surfaced_after
            if getattr(c, "delivery_state", None) in (STATE_FRESH, STATE_ACTIVE)
            or (isinstance(c, DigestCard) and c.delivery_state in (STATE_FRESH, STATE_ACTIVE))
        ]
        return {
            "review_time_min": round(self.review_time_min, 1),
            "cadence_min": self.cadence_min,
            "total_cards": len(self.raw_cards),
            "stale_count": self.stale_count,
            "stale_rate": round(self.stale_rate, 4),
            "surfaced_before_collapse": len(self.surfaced_before),
            "surfaced_after_collapse": len(self.surfaced_after),
            "reduction": len(self.surfaced_before) - len(self.surfaced_after),
            "digests_created": len(self.digests),
            "precision": round(self.precision, 4),
            "fresh_active_count": len(fresh_active),
            "archived_count": self.archived_count,
            "resurfaced_count": self.resurfaced_count,
        }


# ---------------------------------------------------------------------------
# Delivery state engine
# ---------------------------------------------------------------------------

class DeliveryStateEngine:
    """Compute delivery states and family digests for a set of FusionCards.

    Args:
        cadence_min:  Review cadence in minutes (used for simulation only).
        collapse_min_family_size:
            Minimum number of cards in the same family/asset group before
            triggering a digest collapse.  Default 2 (collapse any multi-asset
            duplicate).
    """

    def __init__(self, cadence_min: int = 60, collapse_min_family_size: int = 2) -> None:
        self.cadence_min = cadence_min
        self.collapse_min_family_size = collapse_min_family_size

    # ------------------------------------------------------------------
    # Core state assignment
    # ------------------------------------------------------------------

    def assign_states(
        self, cards: list[DeliveryCard], elapsed_min: float
    ) -> list[DeliveryCard]:
        """Return cards with age_min set to elapsed_min (in-place update).

        Args:
            cards:       Cards to update.
            elapsed_min: Minutes since session start (applied to all cards).

        Returns:
            Same list (mutated in-place) for chaining.
        """
        for card in cards:
            card.age_min = elapsed_min
        return cards

    # ------------------------------------------------------------------
    # Family collapse
    # ------------------------------------------------------------------

    def collapse_families(
        self, cards: list[DeliveryCard]
    ) -> tuple[list[object], list[DigestCard]]:
        """Group same-family cards and collapse multi-asset duplicates.

        Two cards are in the same family if they share (branch, grammar_family).
        When a family has >= collapse_min_family_size cards across different
        assets, they are replaced by a single DigestCard backed by the
        highest-scoring member.

        Why info_loss_score is score-weighted delta (not count):
          A 4-card family where 3 co-assets all score 0.62 (near base) and one
          lead scores 0.81 loses very little signal on collapse — the co-assets
          add almost no new information.  A weighted approach correctly
          assigns near-zero info_loss in that case.

        Args:
            cards: DeliveryCards with delivery_state already assigned.

        Returns:
            Tuple of (surface_items, digests).
              surface_items: mix of DeliveryCards (singletons) and DigestCards.
              digests:       only the DigestCard entries.
        """
        # Group by (branch, grammar_family)
        from collections import defaultdict
        groups: dict[tuple[str, str], list[DeliveryCard]] = defaultdict(list)
        for card in cards:
            key = (card.branch, card.grammar_family)
            groups[key].append(card)

        surface_items: list[object] = []
        digests: list[DigestCard] = []

        for key, group in groups.items():
            if len(group) < self.collapse_min_family_size:
                surface_items.extend(group)
                continue

            # Sort descending by composite_score → lead card first
            group.sort(key=lambda c: c.composite_score, reverse=True)
            lead = group[0]
            co = group[1:]

            # Info loss: fraction of total score held by collapsed co-assets
            total_score = sum(c.composite_score for c in group)
            co_score = sum(c.composite_score for c in co)
            info_loss = co_score / total_score if total_score > 0 else 0.0

            digest = DigestCard(
                family_key=key,
                lead_card=lead,
                co_assets=[c.asset for c in co],
                co_scores=[c.composite_score for c in co],
                info_loss_score=info_loss,
                delivery_state=lead.delivery_state(),
            )
            surface_items.append(digest)
            digests.append(digest)

        return surface_items, digests

    # ------------------------------------------------------------------
    # Review simulation
    # ------------------------------------------------------------------

    def snapshot_review(
        self,
        cards: list[DeliveryCard],
        review_time_min: float,
        resurfaced_count: int = 0,
        update_ages: bool = True,
    ) -> ReviewSnapshot:
        """Compute one operator review snapshot at review_time_min.

        Archived cards (STATE_ARCHIVED) are excluded from surfacing and from
        the stale_count denominator.  They are counted separately in
        archived_count.  This keeps stale_rate comparable across archive-on
        and archive-off simulations.

        Args:
            cards:            DeliveryCards (may include archived cards).
            review_time_min:  Elapsed minutes since session start.
            resurfaced_count: Number of cards re-surfaced from archive this
                              review (injected by caller for diagnostics).
            update_ages:      If True (default), set all non-archived cards'
                              age_min to review_time_min.  Pass False when the
                              caller (e.g. simulate_batch_refresh_with_archive)
                              has already computed per-card ages relative to
                              each card's creation time.  Overwriting ages in
                              the batch-refresh model assigns all cards the
                              absolute session time instead of their true
                              elapsed age, causing artificially high stale rates.

        Returns:
            ReviewSnapshot with before/after surface counts and metrics.
        """
        # Update ages for non-archived cards only when requested
        if update_ages:
            for card in cards:
                if card.archived_at_min is None:
                    card.age_min = review_time_min

        # Separate archived from active pool
        archived_cards = [c for c in cards if c.delivery_state() == STATE_ARCHIVED]
        active_cards = [c for c in cards if c.delivery_state() != STATE_ARCHIVED]

        # Before collapse: surfaced = fresh + active + aging (from active pool only)
        surfaced_before = [
            c for c in active_cards if c.delivery_state() in _SURFACED_STATES
        ]

        # Family collapse
        surface_items, digests = self.collapse_families(surfaced_before)

        # Stale count across active cards only (archived excluded from denominator)
        stale_states = {STATE_AGING, STATE_DIGEST_ONLY, STATE_EXPIRED}
        stale_count = sum(1 for c in active_cards if c.delivery_state() in stale_states)
        stale_rate = stale_count / max(len(active_cards), 1)

        # Precision: fraction of surfaced_after that are fresh/active
        def _is_fresh_or_active(item: object) -> bool:
            if isinstance(item, DeliveryCard):
                return item.delivery_state() in (STATE_FRESH, STATE_ACTIVE)
            if isinstance(item, DigestCard):
                return item.delivery_state in (STATE_FRESH, STATE_ACTIVE)
            return False

        n_fresh_active = sum(1 for x in surface_items if _is_fresh_or_active(x))
        precision = n_fresh_active / max(len(surface_items), 1)

        return ReviewSnapshot(
            review_time_min=review_time_min,
            cadence_min=self.cadence_min,
            raw_cards=list(cards),
            surfaced_before=surfaced_before,
            surfaced_after=surface_items,
            digests=digests,
            stale_count=stale_count,
            stale_rate=stale_rate,
            precision=precision,
            archived_count=len(archived_cards),
            resurfaced_count=resurfaced_count,
        )


# ---------------------------------------------------------------------------
# Card generator (deterministic synthetic data for simulation)
# ---------------------------------------------------------------------------

# Half-life per tier (minutes) — from Run 014 calibration
_HL_BY_TIER: dict[str, float] = {
    "actionable_watch":   40.0,
    "research_priority":  50.0,
    "monitor_borderline": 60.0,
    "baseline_like":      90.0,
    "reject_conflicted":  20.0,
}

# Grammar families (coarser than branch; used for collapse grouping)
_FAMILY_BY_BRANCH: dict[str, str] = {
    "positioning_unwind": "unwind",
    "beta_reversion":     "reversion",
    "flow_continuation":  "momentum",
    "cross_asset":        "cross_asset",
    "null_baseline":      "null",
}

_ASSETS: list[str] = ["HYPE", "BTC", "ETH", "SOL"]
_BRANCHES: list[str] = [
    "positioning_unwind",
    "beta_reversion",
    "flow_continuation",
    "cross_asset",
    "null_baseline",
]
_TIERS_WEIGHTED: list[tuple[str, float]] = [
    ("actionable_watch",   0.20),
    ("research_priority",  0.30),
    ("monitor_borderline", 0.30),
    ("baseline_like",      0.15),
    ("reject_conflicted",  0.05),
]

# Quiet-regime tier distribution: models market windows with no genuine signal.
# Used in push-surfacing simulation to distinguish active from quiet periods.
# Why this distribution:
#   In real crypto markets ~70% of 30-min windows have no actionable hypothesis
#   changes — prices oscillate around equilibrium without new cross-asset signals.
#   Quiet batches should NOT trigger a push; the push engine's selectivity is
#   only meaningful if it can suppress these low-signal periods.
_TIERS_WEIGHTED_QUIET: list[tuple[str, float]] = [
    ("actionable_watch",   0.03),
    ("research_priority",  0.08),
    ("monitor_borderline", 0.24),
    ("baseline_like",      0.45),
    ("reject_conflicted",  0.20),
]


def _weighted_choice(rng: random.Random, choices: list[tuple[str, float]]) -> str:
    """Pick a label from (label, weight) pairs."""
    labels, weights = zip(*choices)
    total = sum(weights)
    r = rng.random() * total
    cumulative = 0.0
    for label, w in zip(labels, weights):
        cumulative += w
        if r < cumulative:
            return label
    return labels[-1]


def generate_cards(
    seed: int,
    n_cards: int = 20,
    force_multi_asset_family: bool = True,
    quiet: bool = False,
) -> list[DeliveryCard]:
    """Generate a deterministic synthetic card set for delivery simulation.

    Args:
        seed:                    RNG seed for reproducibility.
        n_cards:                 Total number of cards to generate.
        force_multi_asset_family:
            If True, always include one complete 4-asset positioning_unwind
            family (the primary family-duplicate pattern from Run 026).
        quiet:  If True, use _TIERS_WEIGHTED_QUIET (low-signal regime).
            Models market windows with no genuine hypothesis change.
            Used in push-surfacing simulation to test engine selectivity:
            a well-designed push engine should suppress quiet batches.

    Returns:
        List of DeliveryCards with age_min=0 (just created).
    """
    tier_weights = _TIERS_WEIGHTED_QUIET if quiet else _TIERS_WEIGHTED
    rng = random.Random(seed)
    cards: list[DeliveryCard] = []
    card_idx = 0

    # Always inject the 4-asset family duplicate set first (Run 026 hot-pattern)
    # In quiet mode, suppress forced family (no high-priority anchor card)
    if force_multi_asset_family and not quiet:
        for asset in _ASSETS:
            tier = "research_priority" if asset == "HYPE" else "monitor_borderline"
            score = rng.uniform(0.65, 0.80) if asset == "HYPE" else rng.uniform(0.60, 0.70)
            cards.append(DeliveryCard(
                card_id=f"c{card_idx:03d}",
                branch="positioning_unwind",
                grammar_family="unwind",
                asset=asset,
                tier=tier,
                composite_score=round(score, 4),
                half_life_min=_HL_BY_TIER[tier],
                age_min=0.0,
            ))
            card_idx += 1

    # Fill remaining slots with diverse cards
    while len(cards) < n_cards:
        branch = rng.choice(_BRANCHES)
        asset = rng.choice(_ASSETS)
        tier = _weighted_choice(rng, tier_weights)
        score_base = {
            "actionable_watch":   (0.74, 0.95),
            "research_priority":  (0.65, 0.82),
            "monitor_borderline": (0.60, 0.74),
            "baseline_like":      (0.40, 0.62),
            "reject_conflicted":  (0.20, 0.55),
        }[tier]
        score = round(rng.uniform(*score_base), 4)
        cards.append(DeliveryCard(
            card_id=f"c{card_idx:03d}",
            branch=branch,
            grammar_family=_FAMILY_BY_BRANCH.get(branch, branch),
            asset=asset,
            tier=tier,
            composite_score=score,
            half_life_min=_HL_BY_TIER[tier],
            age_min=0.0,
        ))
        card_idx += 1

    return cards


# ---------------------------------------------------------------------------
# Multi-cadence simulation
# ---------------------------------------------------------------------------

@dataclass
class CadenceResult:
    """Aggregate metrics for one cadence setting over N review cycles.

    Attributes:
        cadence_min:          Review interval in minutes.
        n_reviews:            Total review points simulated.
        avg_stale_rate:       Mean stale_rate across all reviews.
        avg_surfaced_before:  Mean surfaced count before collapse.
        avg_surfaced_after:   Mean surfaced count after collapse.
        avg_reduction:        Mean item reduction from collapse.
        avg_precision:        Mean attention precision.
        avg_info_loss:        Mean info_loss_score across all digests.
        stale_rate_by_review: Per-review stale rate list.
        snapshots:            Raw ReviewSnapshot list.
        avg_archived:         Mean archived card count per review (Run 028).
        total_resurfaced:     Total re-surface events across all reviews (Run 028).
    """

    cadence_min: int
    n_reviews: int
    avg_stale_rate: float
    avg_surfaced_before: float
    avg_surfaced_after: float
    avg_reduction: float
    avg_precision: float
    avg_info_loss: float
    stale_rate_by_review: list[float]
    snapshots: list[ReviewSnapshot] = field(default_factory=list)
    avg_archived: float = 0.0
    total_resurfaced: int = 0

    def to_csv_row(self) -> dict:
        """Return a flat dict suitable for CSV writing."""
        return {
            "cadence_min": self.cadence_min,
            "n_reviews": self.n_reviews,
            "avg_stale_rate": round(self.avg_stale_rate, 4),
            "avg_surfaced_before": round(self.avg_surfaced_before, 2),
            "avg_surfaced_after": round(self.avg_surfaced_after, 2),
            "avg_reduction": round(self.avg_reduction, 2),
            "avg_precision": round(self.avg_precision, 4),
            "avg_info_loss": round(self.avg_info_loss, 4),
            "avg_archived": round(self.avg_archived, 2),
            "total_resurfaced": self.total_resurfaced,
        }


def simulate_cadence(
    cards: list[DeliveryCard],
    cadence_min: int,
    session_hours: int = 8,
    collapse_min_family_size: int = 2,
) -> CadenceResult:
    """Run a full session simulation for one cadence setting.

    Cards are assumed freshly created at session start (age_min=0).
    For each review point, all cards age by cadence_min and a snapshot
    is taken.  Cards do NOT expire mid-session; they age continuously.

    Why we don't reset ages between reviews:
      In production the operator reviews the same set of active cards
      (they accumulate age).  Resetting would model per-review card
      injection which is a different scenario from this run's scope.

    Args:
        cards:                  DeliveryCards (age_min=0 at session start).
        cadence_min:            Minutes between reviews.
        session_hours:          Total session duration in hours.
        collapse_min_family_size: Passed to DeliveryStateEngine.

    Returns:
        CadenceResult with per-review and aggregate metrics.
    """
    import copy

    engine = DeliveryStateEngine(
        cadence_min=cadence_min,
        collapse_min_family_size=collapse_min_family_size,
    )
    session_min = session_hours * 60
    review_times = list(range(cadence_min, session_min + 1, cadence_min))

    snapshots: list[ReviewSnapshot] = []

    for t in review_times:
        # Deep copy so each snapshot gets its own card state
        cards_copy = copy.deepcopy(cards)
        snap = engine.snapshot_review(cards_copy, float(t))
        snapshots.append(snap)

    # Aggregate
    n = len(snapshots)
    avg_stale_rate = sum(s.stale_rate for s in snapshots) / max(n, 1)
    avg_before = sum(len(s.surfaced_before) for s in snapshots) / max(n, 1)
    avg_after = sum(len(s.surfaced_after) for s in snapshots) / max(n, 1)
    avg_reduction = avg_before - avg_after
    avg_precision = sum(s.precision for s in snapshots) / max(n, 1)

    # Info loss from all digests across all reviews
    all_digests = [d for s in snapshots for d in s.digests]
    avg_info_loss = (
        sum(d.info_loss_score for d in all_digests) / max(len(all_digests), 1)
        if all_digests else 0.0
    )

    return CadenceResult(
        cadence_min=cadence_min,
        n_reviews=n,
        avg_stale_rate=avg_stale_rate,
        avg_surfaced_before=avg_before,
        avg_surfaced_after=avg_after,
        avg_reduction=avg_reduction,
        avg_precision=avg_precision,
        avg_info_loss=avg_info_loss,
        stale_rate_by_review=[s.stale_rate for s in snapshots],
        snapshots=snapshots,
    )


def simulate_first_review(
    cards: list[DeliveryCard],
    cadence_min: int,
    collapse_min_family_size: int = 2,
) -> ReviewSnapshot:
    """Snapshot the card set aged exactly cadence_min (first-batch, first-review).

    This is the primary comparison metric for cadence selection.  It answers:
    "If a batch just ran and the operator waits exactly cadence_min before
    reviewing, how fresh are the cards?"

    Why first-review and not session-average:
      A session-long decay model without batch refresh consistently shows all
      cadences degrading to ~100% stale after ~3 half-lives (≈2-3h).  That
      models a pathological no-refresh scenario, not the real one.  The first-
      review snapshot isolates the delivery-window quality independently of
      long-run session management.

    Args:
        cards:                  DeliveryCards with age_min=0.
        cadence_min:            Minutes to age the cards before snapshotting.
        collapse_min_family_size: Passed to DeliveryStateEngine.

    Returns:
        ReviewSnapshot at t=cadence_min.
    """
    import copy
    engine = DeliveryStateEngine(
        cadence_min=cadence_min,
        collapse_min_family_size=collapse_min_family_size,
    )
    return engine.snapshot_review(copy.deepcopy(cards), float(cadence_min))


def simulate_batch_refresh(
    seed: int,
    cadence_min: int,
    batch_interval_min: int = 30,
    n_cards_per_batch: int = 20,
    session_hours: int = 8,
    collapse_min_family_size: int = 2,
) -> CadenceResult:
    """Steady-state simulation with periodic batch refresh.

    Models a realistic production scenario:
      - A new batch of cards arrives every batch_interval_min
      - The operator reviews the accumulated deck at cadence_min intervals
      - Cards from prior batches accumulate age; expired cards are pruned

    Why batch_interval_min defaults to 30:
      The typical Hyperliquid detection pipeline runs on 15-30 min windows.
      30 min is the conservative (slower) estimate; reduce to 15 if the
      pipeline refresh rate is confirmed faster.

    Args:
        seed:                RNG seed.
        cadence_min:         Operator review interval in minutes.
        batch_interval_min:  New card injection interval in minutes.
        n_cards_per_batch:   Cards per batch injection.
        session_hours:       Total simulation duration.
        collapse_min_family_size: Passed to DeliveryStateEngine.

    Returns:
        CadenceResult with per-review snapshots from the batch-refresh model.
    """
    import copy

    engine = DeliveryStateEngine(
        cadence_min=cadence_min,
        collapse_min_family_size=collapse_min_family_size,
    )
    session_min = session_hours * 60
    batch_rng = random.Random(seed)

    # Timeline: all cards ever created, keyed by creation time
    all_cards: list[tuple[float, DeliveryCard]] = []  # (creation_time, card)

    # Inject initial batch at t=0
    for card in generate_cards(seed=batch_rng.randint(0, 9999), n_cards=n_cards_per_batch):
        all_cards.append((0.0, card))

    # Schedule batch arrivals and review times
    batch_times = list(range(batch_interval_min, session_min + 1, batch_interval_min))
    review_times = list(range(cadence_min, session_min + 1, cadence_min))

    next_batch_idx = 0
    snapshots: list[ReviewSnapshot] = []

    for t in sorted(set(batch_times + review_times)):
        # Inject any batches that arrive at or before this time
        while next_batch_idx < len(batch_times) and batch_times[next_batch_idx] <= t:
            bt = float(batch_times[next_batch_idx])
            for card in generate_cards(
                seed=batch_rng.randint(0, 9999), n_cards=n_cards_per_batch
            ):
                all_cards.append((bt, card))
            next_batch_idx += 1

        if t not in review_times:
            continue

        # Build deck: cards still alive at time t
        deck: list[DeliveryCard] = []
        for (ct, card) in all_cards:
            age = t - ct
            c = copy.copy(card)
            c.age_min = age
            # Prune expired cards older than 3 * half_life_min
            if age <= 3.0 * card.half_life_min:
                deck.append(c)

        # update_ages=False: per-card ages already set as (t - creation_time)
        snap = engine.snapshot_review(deck, float(t), update_ages=False)
        snapshots.append(snap)

    if not snapshots:
        return CadenceResult(
            cadence_min=cadence_min, n_reviews=0,
            avg_stale_rate=0.0, avg_surfaced_before=0.0,
            avg_surfaced_after=0.0, avg_reduction=0.0,
            avg_precision=0.0, avg_info_loss=0.0,
            stale_rate_by_review=[], snapshots=[],
        )

    n = len(snapshots)
    avg_stale_rate = sum(s.stale_rate for s in snapshots) / n
    avg_before = sum(len(s.surfaced_before) for s in snapshots) / n
    avg_after = sum(len(s.surfaced_after) for s in snapshots) / n
    avg_precision = sum(s.precision for s in snapshots) / n
    all_digests = [d for s in snapshots for d in s.digests]
    avg_info_loss = (
        sum(d.info_loss_score for d in all_digests) / len(all_digests)
        if all_digests else 0.0
    )

    return CadenceResult(
        cadence_min=cadence_min,
        n_reviews=n,
        avg_stale_rate=avg_stale_rate,
        avg_surfaced_before=avg_before,
        avg_surfaced_after=avg_after,
        avg_reduction=avg_before - avg_after,
        avg_precision=avg_precision,
        avg_info_loss=avg_info_loss,
        stale_rate_by_review=[s.stale_rate for s in snapshots],
        snapshots=snapshots,
    )


def run_multi_cadence(
    seeds: list[int],
    cadences: list[int],
    n_cards: int = 20,
    session_hours: int = 8,
    model: str = "first_review",
) -> dict[int, CadenceResult]:
    """Run all cadences over multiple seeds and return averaged results.

    Args:
        seeds:         RNG seeds to average over (reduces variance).
        cadences:      Review cadence values in minutes to compare.
        n_cards:       Cards per simulated session.
        session_hours: Session duration (used only for batch_refresh model).
        model:         Simulation model to use:
                         "first_review"    — age cards to cadence_min once
                           (best isolation of cadence quality, recommended)
                         "batch_refresh"   — periodic batch injection over
                           session_hours (realistic steady-state)
                         "decay"           — original single-batch decay model
                           (retained for comparison; all cadences look bad
                           eventually due to no refresh)

    Returns:
        Dict mapping cadence_min → CadenceResult (averaged across seeds).
    """
    from collections import defaultdict

    per_seed_results: dict[int, list[CadenceResult]] = defaultdict(list)

    for seed in seeds:
        for cadence in cadences:
            if model == "first_review":
                cards = generate_cards(seed=seed, n_cards=n_cards)
                snap = simulate_first_review(cards, cadence)
                # Wrap single snapshot into a CadenceResult
                digests_here = snap.digests
                info_loss = (
                    sum(d.info_loss_score for d in digests_here) / len(digests_here)
                    if digests_here else 0.0
                )
                result = CadenceResult(
                    cadence_min=cadence,
                    n_reviews=1,
                    avg_stale_rate=snap.stale_rate,
                    avg_surfaced_before=float(len(snap.surfaced_before)),
                    avg_surfaced_after=float(len(snap.surfaced_after)),
                    avg_reduction=float(len(snap.surfaced_before) - len(snap.surfaced_after)),
                    avg_precision=snap.precision,
                    avg_info_loss=info_loss,
                    stale_rate_by_review=[snap.stale_rate],
                    snapshots=[snap],
                )
            elif model == "batch_refresh":
                result = simulate_batch_refresh(
                    seed=seed,
                    cadence_min=cadence,
                    session_hours=session_hours,
                )
            else:  # decay
                cards = generate_cards(seed=seed, n_cards=n_cards)
                result = simulate_cadence(cards, cadence, session_hours=session_hours)

            per_seed_results[cadence].append(result)

    # Average across seeds for each cadence
    averaged: dict[int, CadenceResult] = {}
    for cadence, results in per_seed_results.items():
        n = len(results)
        averaged[cadence] = CadenceResult(
            cadence_min=cadence,
            n_reviews=results[0].n_reviews,  # same for all seeds
            avg_stale_rate=sum(r.avg_stale_rate for r in results) / n,
            avg_surfaced_before=sum(r.avg_surfaced_before for r in results) / n,
            avg_surfaced_after=sum(r.avg_surfaced_after for r in results) / n,
            avg_reduction=sum(r.avg_reduction for r in results) / n,
            avg_precision=sum(r.avg_precision for r in results) / n,
            avg_info_loss=sum(r.avg_info_loss for r in results) / n,
            avg_archived=sum(r.avg_archived for r in results) / n,
            total_resurfaced=sum(r.total_resurfaced for r in results),
            stale_rate_by_review=[],
            snapshots=[],
        )

    return averaged


def simulate_batch_refresh_with_archive(
    seed: int,
    cadence_min: int,
    batch_interval_min: int = 30,
    n_cards_per_batch: int = 20,
    session_hours: int = 8,
    collapse_min_family_size: int = 2,
    resurface_window_min: int = _DEFAULT_RESURFACE_WINDOW_MIN,
    archive_max_age_min: int = _DEFAULT_ARCHIVE_MAX_AGE_MIN,
) -> CadenceResult:
    """Batch-refresh simulation with Run 028 archive + re-surface semantics.

    Extends simulate_batch_refresh with:
      - ArchiveManager applied at each review point (expired → archived)
      - Re-surface candidates injected when incoming batch shares a family
        with recently archived cards

    Why a separate function rather than a flag on simulate_batch_refresh:
      Adding archive semantics changes the deck composition (archived cards
      are excluded from stale_count, re-surfaced cards are injected fresh).
      A flag would require branching throughout the inner loop, making both
      paths harder to audit.  Separate functions are independently testable.

    Args:
        seed:                RNG seed.
        cadence_min:         Operator review interval in minutes.
        batch_interval_min:  New card injection interval in minutes.
        n_cards_per_batch:   Cards per batch injection.
        session_hours:       Total simulation duration.
        collapse_min_family_size: Passed to DeliveryStateEngine.
        resurface_window_min: Passed to ArchiveManager.
        archive_max_age_min:  Passed to ArchiveManager.

    Returns:
        CadenceResult including avg_archived and total_resurfaced metrics.
    """
    import copy

    engine = DeliveryStateEngine(
        cadence_min=cadence_min,
        collapse_min_family_size=collapse_min_family_size,
    )
    archive_mgr = ArchiveManager(
        resurface_window_min=resurface_window_min,
        archive_max_age_min=archive_max_age_min,
    )
    session_min = session_hours * 60
    batch_rng = random.Random(seed)

    # Timeline: all cards ever created — (creation_time, card)
    all_cards: list[tuple[float, DeliveryCard]] = []

    # Inject initial batch at t=0
    for card in generate_cards(seed=batch_rng.randint(0, 9999), n_cards=n_cards_per_batch):
        all_cards.append((0.0, card))

    batch_times = list(range(batch_interval_min, session_min + 1, batch_interval_min))
    review_times = list(range(cadence_min, session_min + 1, cadence_min))
    next_batch_idx = 0
    snapshots: list[ReviewSnapshot] = []

    for t in sorted(set(batch_times + review_times)):
        # Collect any newly arriving batches
        new_batch_cards: list[DeliveryCard] = []
        while next_batch_idx < len(batch_times) and batch_times[next_batch_idx] <= t:
            bt = float(batch_times[next_batch_idx])
            for card in generate_cards(
                seed=batch_rng.randint(0, 9999), n_cards=n_cards_per_batch
            ):
                all_cards.append((bt, card))
                new_batch_cards.append(card)
            next_batch_idx += 1

        if t not in review_times:
            continue

        # Build deck with current ages; hard-prune beyond archive_max_age_min
        deck: list[DeliveryCard] = []
        for (ct, card) in all_cards:
            age = float(t) - ct
            c = copy.copy(card)
            c.age_min = age
            c.archived_at_min = card.archived_at_min  # carry archive flag
            c.resurface_count = card.resurface_count
            if age <= archive_max_age_min:
                deck.append(c)

        # Apply archive transitions (expired → archived)
        archive_mgr.apply_archive_transitions(deck, float(t))

        # Propagate archive flags back to the master list
        flag_map = {c.card_id: c.archived_at_min for c in deck}
        for (ct, card) in all_cards:
            if card.card_id in flag_map and flag_map[card.card_id] is not None:
                card.archived_at_min = flag_map[card.card_id]

        # Check for re-surface from newly arrived batch.
        # Re-surfaced cards must be added to all_cards (the persistent timeline)
        # so they age correctly in subsequent cycles.  Extending only deck (the
        # per-review snapshot) causes re-surfaced cards to vanish in the next
        # iteration because all_cards never learned about them.
        resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
        for card in resurfaced:
            all_cards.append((float(t), card))
        deck.extend(resurfaced)

        # update_ages=False: ages already computed as (t - creation_time) per card;
        # overwriting with absolute session time would give every card age=t regardless
        # of when it was created, causing artificially high stale rates.
        snap = engine.snapshot_review(
            deck, float(t), resurfaced_count=len(resurfaced), update_ages=False
        )
        snapshots.append(snap)

    if not snapshots:
        return CadenceResult(
            cadence_min=cadence_min, n_reviews=0,
            avg_stale_rate=0.0, avg_surfaced_before=0.0,
            avg_surfaced_after=0.0, avg_reduction=0.0,
            avg_precision=0.0, avg_info_loss=0.0,
            stale_rate_by_review=[], snapshots=[],
        )

    n = len(snapshots)
    avg_stale_rate = sum(s.stale_rate for s in snapshots) / n
    avg_before = sum(len(s.surfaced_before) for s in snapshots) / n
    avg_after = sum(len(s.surfaced_after) for s in snapshots) / n
    avg_precision = sum(s.precision for s in snapshots) / n
    all_digests = [d for s in snapshots for d in s.digests]
    avg_info_loss = (
        sum(d.info_loss_score for d in all_digests) / len(all_digests)
        if all_digests else 0.0
    )
    avg_archived = sum(s.archived_count for s in snapshots) / n
    total_resurfaced = sum(s.resurfaced_count for s in snapshots)

    return CadenceResult(
        cadence_min=cadence_min,
        n_reviews=n,
        avg_stale_rate=avg_stale_rate,
        avg_surfaced_before=avg_before,
        avg_surfaced_after=avg_after,
        avg_reduction=avg_before - avg_after,
        avg_precision=avg_precision,
        avg_info_loss=avg_info_loss,
        avg_archived=avg_archived,
        total_resurfaced=total_resurfaced,
        stale_rate_by_review=[s.stale_rate for s in snapshots],
        snapshots=snapshots,
    )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def results_to_csv(results: dict[int, CadenceResult]) -> str:
    """Render CadenceResult dict as CSV string.

    Args:
        results: Cadence → CadenceResult mapping.

    Returns:
        CSV string with header row.
    """
    fieldnames = [
        "cadence_min", "n_reviews",
        "avg_stale_rate", "avg_surfaced_before", "avg_surfaced_after",
        "avg_reduction", "avg_precision", "avg_info_loss",
        "avg_archived", "total_resurfaced",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for cadence in sorted(results):
        writer.writerow(results[cadence].to_csv_row())
    return buf.getvalue()
