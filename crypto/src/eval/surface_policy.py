"""Surface Policy v2: baseline_like archive-only routing and post-resurface classification.

Run 038b introduced Surface Policy v2, which routes ``baseline_like`` cards
directly to the archive pool instead of surfacing them normally.  The intent
is to reduce operator noise from low-signal cards while retaining the ability
to recover them if the same family produces confirmed signal later.

Policy decision per incoming card:
  ARCHIVE_ONLY  — tier == baseline_like: archived immediately, not shown to operator
  SURFACE       — all other tiers: proceed through normal delivery lifecycle

Post-resurface classification (applied when an archived card is resurfaced):
  action_worthy     — trigger companion card is actionable_watch or research_priority
                      with composite_score >= ACTION_THRESHOLD
  attention_worthy  — trigger companion is monitor_borderline or research_priority
                      below ACTION_THRESHOLD; card merits secondary review
  redundant         — trigger companion is also baseline_like; low-value recurrence

Counterfactual definition:
  A baseline_like card is "counterfactually attention_worthy" if its composite_score
  meets the monitor_borderline threshold (>= COUNTERFACTUAL_ATTENTION_THRESHOLD).
  This identifies near-misses: cards just below the surface tier boundary that
  might have merited operator attention if surfaced immediately.

Note: No baseline_like card can be counterfactually action_worthy because
action_watch requires composite_score >= 0.74 while baseline_like tops out at 0.62.
The relevant counterfactual is whether the card would have been classified as
monitor_borderline or above, not actionable_watch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

BASELINE_LIKE_TIER: str = "baseline_like"

# Tiers that, when triggering a resurface, classify the resurfaced card as
# action_worthy (the family produced genuinely actionable signal)
ACTION_WORTHY_TRIGGER_TIERS: frozenset[str] = frozenset([
    "actionable_watch",
    "research_priority",
])

# Minimum score for the trigger card to classify resurface as action_worthy
# (research_priority cards near the lower bound may not warrant action)
ACTION_THRESHOLD: float = 0.74

# Score threshold for post-resurface "attention_worthy" classification
# (trigger card score below ACTION_THRESHOLD but above this)
ATTENTION_THRESHOLD: float = 0.60

# Baseline_like card score above this = "counterfactually attention_worthy"
# = would have been monitor_borderline if surfaced immediately
COUNTERFACTUAL_ATTENTION_THRESHOLD: float = 0.60


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PolicyDecision:
    """Result of Surface Policy v2 routing for one card.

    Attributes:
        card_id:     Card identifier.
        tier:        Card tier.
        route:       "archive_only" or "surface".
        reason:      Human-readable routing rationale.
    """

    card_id: str
    tier: str
    route: str
    reason: str


@dataclass
class PostResurfaceClass:
    """Classification of a resurfaced baseline_like card.

    Attributes:
        archived_card_id:   Original archived card identifier.
        trigger_card_id:    Card that triggered the resurface.
        trigger_tier:       Tier of the trigger card.
        trigger_score:      composite_score of the trigger card.
        classification:     "action_worthy" / "attention_worthy" / "redundant".
        reason:             Human-readable classification rationale.
    """

    archived_card_id: str
    trigger_card_id: str
    trigger_tier: str
    trigger_score: float
    classification: str
    reason: str


# ---------------------------------------------------------------------------
# Surface Policy v2
# ---------------------------------------------------------------------------

class SurfacePolicyV2:
    """Route incoming delivery cards per Surface Policy v2.

    Baseline_like cards are archived immediately (not surfaced).
    All other tiers proceed through the normal delivery lifecycle.
    """

    def route(self, card_id: str, tier: str) -> PolicyDecision:
        """Apply Surface Policy v2 to one incoming card.

        Args:
            card_id: Card identifier.
            tier:    Decision tier (e.g. "baseline_like", "actionable_watch").

        Returns:
            PolicyDecision with route "archive_only" or "surface".
        """
        if tier == BASELINE_LIKE_TIER:
            return PolicyDecision(
                card_id=card_id,
                tier=tier,
                route="archive_only",
                reason=(
                    "baseline_like tier: undifferentiated from baseline, "
                    "archived to reduce operator noise; eligible for resurface "
                    "on family recurrence"
                ),
            )
        return PolicyDecision(
            card_id=card_id,
            tier=tier,
            route="surface",
            reason=f"{tier}: surfaced normally through delivery lifecycle",
        )

    def classify_post_resurface(
        self,
        archived_card_id: str,
        trigger_card_id: str,
        trigger_tier: str,
        trigger_score: float,
    ) -> PostResurfaceClass:
        """Classify the value of a resurfaced baseline_like card.

        Classification is driven by the trigger companion card (the card
        whose family arrival caused the resurface).  A high-quality trigger
        indicates the family produced genuine signal; the historical baseline_like
        record provides confirmatory context.

        Args:
            archived_card_id: Original archived card identifier.
            trigger_card_id:  ID of the card that triggered the resurface.
            trigger_tier:     Tier of the trigger card.
            trigger_score:    composite_score of the trigger card.

        Returns:
            PostResurfaceClass with classification and rationale.
        """
        if (trigger_tier in ACTION_WORTHY_TRIGGER_TIERS
                and trigger_score >= ACTION_THRESHOLD):
            return PostResurfaceClass(
                archived_card_id=archived_card_id,
                trigger_card_id=trigger_card_id,
                trigger_tier=trigger_tier,
                trigger_score=trigger_score,
                classification="action_worthy",
                reason=(
                    f"trigger {trigger_tier} (score={trigger_score:.3f}) "
                    f">= ACTION_THRESHOLD={ACTION_THRESHOLD}: "
                    "family produced actionable signal; resurface adds confirmation"
                ),
            )
        if trigger_tier in ACTION_WORTHY_TRIGGER_TIERS or trigger_score >= ATTENTION_THRESHOLD:
            return PostResurfaceClass(
                archived_card_id=archived_card_id,
                trigger_card_id=trigger_card_id,
                trigger_tier=trigger_tier,
                trigger_score=trigger_score,
                classification="attention_worthy",
                reason=(
                    f"trigger {trigger_tier} (score={trigger_score:.3f}) "
                    f"in action-worthy tiers but below ACTION_THRESHOLD or "
                    f"score >= ATTENTION_THRESHOLD={ATTENTION_THRESHOLD}: "
                    "family is noteworthy; resurface merits secondary review"
                ),
            )
        return PostResurfaceClass(
            archived_card_id=archived_card_id,
            trigger_card_id=trigger_card_id,
            trigger_tier=trigger_tier,
            trigger_score=trigger_score,
            classification="redundant",
            reason=(
                f"trigger {trigger_tier} (score={trigger_score:.3f}): "
                "low-quality recurrence; resurface provides no new signal"
            ),
        )


# ---------------------------------------------------------------------------
# Counterfactual helper
# ---------------------------------------------------------------------------

def is_counterfactual_attention_worthy(composite_score: float) -> bool:
    """Return True if a baseline_like card would be attention_worthy if surfaced.

    A baseline_like card with score >= COUNTERFACTUAL_ATTENTION_THRESHOLD
    is close enough to the monitor_borderline boundary that it would plausibly
    have merited operator attention if surfaced normally.

    Note: No baseline_like card can be counterfactually *action_worthy*
    because actionable_watch requires score >= 0.74 while baseline_like
    cards are capped at 0.62 by the decision tier scorer.

    Args:
        composite_score: Card composite_score.

    Returns:
        True if score >= COUNTERFACTUAL_ATTENTION_THRESHOLD.
    """
    return composite_score >= COUNTERFACTUAL_ATTENTION_THRESHOLD
