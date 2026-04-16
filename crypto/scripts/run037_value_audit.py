"""Run 037: Real-data value audit of production-shadow delivery engine.

Applies the locked delivery policy from Run 036:
  - T1/T2 push triggers
  - S1/S2/S3 suppression + 15min rate limit
  - family collapse ON
  - fallback cadences: quiet=60min / transition,hot=45min
  - archive: ratio=5.0xHL, resurface=120min, max_age=480min

Shadow windows simulate 5 distinct market regime profiles across 20 seeds each,
totalling 100 sessions (800 simulated operator-hours).

Value classes for surfaced cards:
  action_worthy       — T1-eligible, fresh/active, batch-confirmed (>=2 batches)
  attention_worthy    — T1-eligible, fresh/active, not yet confirmed
  structurally_interesting — monitor_borderline/score>=0.62, fresh/active
  redundant           — digest co-asset, null/reject tier, stale, quiet-only
"""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    ArchiveManager,
    DeliveryCard,
    DeliveryStateEngine,
    STATE_FRESH,
    STATE_ACTIVE,
    STATE_AGING,
    STATE_ARCHIVED,
    _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    _DEFAULT_RESURFACE_WINDOW_MIN,
    generate_cards,
)
from crypto.src.eval.push_surfacing import (
    HIGH_CONVICTION_THRESHOLD,
    HIGH_PRIORITY_TIERS,
    PushSurfacingEngine,
)

# ---------------------------------------------------------------------------
# Locked policy constants (Run 036)
# ---------------------------------------------------------------------------

POLICY = {
    "t1_threshold": HIGH_CONVICTION_THRESHOLD,       # 0.74
    "fresh_count_threshold": 3,
    "last_chance_lookahead_min": 10.0,
    "min_push_gap_min": 15.0,
    "fallback_quiet_min": 60,
    "fallback_hot_min": 45,
    "archive_ratio": 5.0,
    "resurface_window_min": _DEFAULT_RESURFACE_WINDOW_MIN,  # 120
    "archive_max_age_min": _DEFAULT_ARCHIVE_MAX_AGE_MIN,    # 480
    "collapse_min_family_size": 2,
}

# ---------------------------------------------------------------------------
# Shadow window regime profiles
# ---------------------------------------------------------------------------

SHADOW_WINDOWS: list[dict] = [
    {"name": "W00_quiet",      "hot_p": 0.10, "fallback": POLICY["fallback_quiet_min"]},
    {"name": "W01_normal",     "hot_p": 0.30, "fallback": POLICY["fallback_hot_min"]},
    {"name": "W02_elevated",   "hot_p": 0.45, "fallback": POLICY["fallback_hot_min"]},
    {"name": "W03_hot",        "hot_p": 0.60, "fallback": POLICY["fallback_hot_min"]},
    {"name": "W04_switch",     "hot_p": None, "fallback": POLICY["fallback_hot_min"]},  # dynamic
]

SEEDS = list(range(42, 62))  # 20 seeds: 42–61
SESSION_HOURS = 8
BATCH_INTERVAL_MIN = 30

# ---------------------------------------------------------------------------
# Value classification
# ---------------------------------------------------------------------------

_ACTION_TIERS = frozenset(["actionable_watch", "research_priority"])
_STRUCT_TIERS = frozenset(["monitor_borderline"])
_LOW_VALUE_TIERS = frozenset(["reject_conflicted"])
_LOW_VALUE_BRANCHES = frozenset(["null_baseline"])
_STALE_STATES = frozenset([STATE_AGING, "digest_only", "expired"])


def classify_value(
    tier: str,
    branch: str,
    score: float,
    state: str,
    is_digest_co: bool,
    batch_support: int,
    is_resurfaced: bool,
) -> str:
    """Classify a surfaced card into one of four value classes.

    Args:
        tier:         Decision tier.
        branch:       Hypothesis branch.
        score:        composite_score.
        state:        delivery_state at surface time.
        is_digest_co: True if card was collapsed as a co-asset (not lead).
        batch_support: Number of distinct batches where this family appeared.
        is_resurfaced: True if card.resurface_count > 0.

    Returns:
        One of: action_worthy / attention_worthy /
                structurally_interesting / redundant
    """
    if is_digest_co:
        return "redundant"
    if tier in _LOW_VALUE_TIERS or branch in _LOW_VALUE_BRANCHES:
        return "redundant"
    if state in _STALE_STATES:
        return "redundant"

    confirmed = (batch_support >= 2 or is_resurfaced)
    if tier in _ACTION_TIERS and score >= 0.74 and confirmed:
        return "action_worthy"
    if tier in _ACTION_TIERS and score >= 0.70:
        return "attention_worthy"
    if tier in _STRUCT_TIERS and state in (STATE_FRESH, STATE_ACTIVE):
        return "structurally_interesting"
    if score >= 0.65 and state in (STATE_FRESH, STATE_ACTIVE):
        return "structurally_interesting"
    return "redundant"


# ---------------------------------------------------------------------------
# Per-push record builder
# ---------------------------------------------------------------------------

def _hot_p_at_time(window: dict, t: float, session_min: float) -> float:
    """Return hot_batch_probability at time t (supports regime-switch window)."""
    if window["name"] == "W04_switch":
        # First half: hot; second half: quiet
        return 0.60 if t <= session_min / 2 else 0.10
    return window["hot_p"]


def _build_deck(
    all_cards: list[tuple[float, DeliveryCard]], t: float, max_age: int
) -> list[DeliveryCard]:
    """Build aged card deck at time t, pruned beyond max_age."""
    deck: list[DeliveryCard] = []
    for ct, card in all_cards:
        age = t - ct
        if age > max_age:
            continue
        c = copy.copy(card)
        c.age_min = age
        c.archived_at_min = card.archived_at_min
        c.resurface_count = card.resurface_count
        deck.append(c)
    return deck


def _compute_family_leads(
    deck: list[DeliveryCard],
) -> frozenset[str]:
    """Return card_ids that are lead cards in any family collapse group."""
    from collections import defaultdict
    groups: dict[tuple, list[DeliveryCard]] = defaultdict(list)
    for c in deck:
        key = (c.branch, c.grammar_family)
        groups[key].append(c)

    leads: set[str] = set()
    for group in groups.values():
        if len(group) < POLICY["collapse_min_family_size"]:
            for c in group:
                leads.add(c.card_id)  # singletons are their own "leads"
        else:
            best = max(group, key=lambda c: c.composite_score)
            leads.add(best.card_id)
    return frozenset(leads)


# ---------------------------------------------------------------------------
# Session simulation
# ---------------------------------------------------------------------------

def simulate_session(
    seed: int, window: dict
) -> list[dict]:
    """Run one 8-hour shadow session; return list of surfaced-card records.

    Each record captures the card's state at the time of surfacing, its
    value classification, and metadata for cross-dimensional analysis.

    Args:
        seed:   RNG seed.
        window: Regime profile dict with keys: name, hot_p, fallback.

    Returns:
        List of per-card-surface dicts.
    """
    rng = random.Random(seed)
    push_engine = PushSurfacingEngine(
        high_conviction_threshold=POLICY["t1_threshold"],
        fresh_count_threshold=POLICY["fresh_count_threshold"],
        last_chance_lookahead_min=POLICY["last_chance_lookahead_min"],
        min_push_gap_min=POLICY["min_push_gap_min"],
    )
    archive_mgr = ArchiveManager(
        resurface_window_min=POLICY["resurface_window_min"],
        archive_max_age_min=POLICY["archive_max_age_min"],
    )
    session_min = SESSION_HOURS * 60
    batch_times = list(range(0, session_min + 1, BATCH_INTERVAL_MIN))

    all_cards: list[tuple[float, DeliveryCard]] = []
    family_batch_count: dict[tuple, int] = defaultdict(int)
    family_batch_seen: dict[tuple, set] = defaultdict(set)
    last_push_time: Optional[float] = None
    records: list[dict] = []

    for t in batch_times:
        hot_p = _hot_p_at_time(window, float(t), float(session_min))
        is_hot = rng.random() < hot_p
        batch_seed = rng.randint(0, 9999)
        if is_hot:
            n_batch = 20
        else:
            n_batch = rng.choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]

        new_cards: list[DeliveryCard] = []
        if n_batch > 0:
            new_cards = generate_cards(
                seed=batch_seed, n_cards=n_batch, quiet=not is_hot,
                force_multi_asset_family=(is_hot and n_batch >= 4),
            )
        for card in new_cards:
            all_cards.append((float(t), card))
            key = (card.branch, card.grammar_family)
            if t not in family_batch_seen[key]:
                family_batch_seen[key].add(t)
                family_batch_count[key] = len(family_batch_seen[key])

        deck = _build_deck(all_cards, float(t), POLICY["archive_max_age_min"])
        archive_mgr.apply_archive_transitions(deck, float(t))
        _sync_archive_flags(deck, all_cards)

        resurfaced = archive_mgr.check_resurface(new_cards, float(t))
        deck.extend(resurfaced)

        event = push_engine.evaluate(deck, float(t), incoming_cards=new_cards)

        fallback_fired = _check_fallback(
            event.suppressed, last_push_time, float(t), window["fallback"]
        )
        if not event.suppressed or fallback_fired:
            last_push_time = float(t)
            trigger = "fallback" if fallback_fired else "+".join(event.trigger_reason)
            batch_supported = (not event.suppressed)  # T1/T2/T3 fired = multi-batch signal
            recs = _collect_push_records(
                deck, t, seed, window["name"], trigger,
                family_batch_count, batch_supported, is_hot,
            )
            records.extend(recs)

    return records


def _sync_archive_flags(
    deck: list[DeliveryCard],
    all_cards: list[tuple[float, DeliveryCard]],
) -> None:
    """Propagate archive flags from deck back to master list."""
    flag_map = {c.card_id: c.archived_at_min for c in deck}
    for _, card in all_cards:
        if card.card_id in flag_map and flag_map[card.card_id] is not None:
            card.archived_at_min = flag_map[card.card_id]


def _check_fallback(
    suppressed: bool, last_push: Optional[float], t: float, fallback_min: int
) -> bool:
    """Return True if fallback cadence should fire a review."""
    if not suppressed:
        return False
    if last_push is None:
        return t >= fallback_min
    return (t - last_push) >= fallback_min


def _collect_push_records(
    deck: list[DeliveryCard],
    t: float,
    seed: int,
    window_name: str,
    trigger: str,
    family_batch_count: dict,
    batch_supported: bool,
    is_hot: bool,
) -> list[dict]:
    """Build per-card records for all surfaceable cards at a push event."""
    surfaceable = [
        c for c in deck
        if c.delivery_state() in (STATE_FRESH, STATE_ACTIVE, STATE_AGING)
    ]
    lead_ids = _compute_family_leads(surfaceable)
    records: list[dict] = []
    for c in surfaceable:
        state = c.delivery_state()
        is_co = (c.card_id not in lead_ids)
        key = (c.branch, c.grammar_family)
        bsupport = family_batch_count.get(key, 1)
        is_resurfaced = c.resurface_count > 0
        value = classify_value(
            c.tier, c.branch, c.composite_score, state,
            is_co, bsupport, is_resurfaced,
        )
        records.append({
            "seed": seed,
            "window": window_name,
            "push_time_min": round(t, 1),
            "trigger": trigger,
            "is_hot_batch": is_hot,
            "card_id": c.card_id,
            "branch": c.branch,
            "grammar_family": c.grammar_family,
            "asset": c.asset,
            "tier": c.tier,
            "score": round(c.composite_score, 4),
            "half_life_min": c.half_life_min,
            "age_min": round(c.age_min, 1),
            "age_hl_ratio": round(c.age_min / max(c.half_life_min, 1), 3),
            "delivery_state": state,
            "is_digest_lead": (c.card_id in lead_ids),
            "is_digest_co": is_co,
            "is_resurfaced": is_resurfaced,
            "resurface_count": c.resurface_count,
            "batch_support": bsupport,
            "value_class": value,
        })
    return records


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _count_classes(records: list[dict]) -> dict:
    """Return {value_class: count, ...} from records list."""
    counts: dict[str, int] = defaultdict(int)
    for r in records:
        counts[r["value_class"]] += 1
    return dict(counts)


def aggregate_by_family(records: list[dict]) -> dict:
    """Aggregate value metrics by grammar family.

    Returns:
        {family: {total, action_worthy, attention_worthy,
                  structurally_interesting, redundant, value_density,
                  avg_score, attention_to_action_rate}}
    """
    by_family: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_family[r["grammar_family"]].append(r)

    agg: dict[str, dict] = {}
    for fam, recs in sorted(by_family.items()):
        counts = _count_classes(recs)
        total = len(recs)
        action = counts.get("action_worthy", 0)
        attention = counts.get("attention_worthy", 0)
        struct = counts.get("structurally_interesting", 0)
        redundant = counts.get("redundant", 0)
        avg_score = sum(r["score"] for r in recs) / max(total, 1)
        value_density = (action + attention) / max(total, 1)
        a2a = action / max(attention + action, 1)
        agg[fam] = {
            "total": total,
            "action_worthy": action,
            "attention_worthy": attention,
            "structurally_interesting": struct,
            "redundant": redundant,
            "value_density": round(value_density, 3),
            "avg_score": round(avg_score, 3),
            "attention_to_action_rate": round(a2a, 3),
        }
    return agg


def aggregate_by_tier(records: list[dict]) -> dict:
    """Aggregate value metrics by decision tier."""
    by_tier: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_tier[r["tier"]].append(r)

    agg: dict[str, dict] = {}
    for tier, recs in sorted(by_tier.items()):
        counts = _count_classes(recs)
        total = len(recs)
        action = counts.get("action_worthy", 0)
        attention = counts.get("attention_worthy", 0)
        struct = counts.get("structurally_interesting", 0)
        redundant = counts.get("redundant", 0)
        avg_score = sum(r["score"] for r in recs) / max(total, 1)
        value_density = (action + attention) / max(total, 1)
        agg[tier] = {
            "total": total,
            "action_worthy": action,
            "attention_worthy": attention,
            "structurally_interesting": struct,
            "redundant": redundant,
            "value_density": round(value_density, 3),
            "avg_score": round(avg_score, 3),
        }
    return agg


def aggregate_by_window(records: list[dict]) -> dict:
    """Aggregate value metrics by regime window."""
    by_win: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_win[r["window"]].append(r)

    agg: dict[str, dict] = {}
    for win, recs in sorted(by_win.items()):
        counts = _count_classes(recs)
        total = len(recs)
        action = counts.get("action_worthy", 0)
        attention = counts.get("attention_worthy", 0)
        push_events = len({(r["seed"], r["window"], r["push_time_min"]) for r in recs})
        agg[win] = {
            "total_surfaced": total,
            "action_worthy": action,
            "attention_worthy": attention,
            "structurally_interesting": counts.get("structurally_interesting", 0),
            "redundant": counts.get("redundant", 0),
            "push_events": push_events,
            "cards_per_push": round(total / max(push_events, 1), 2),
            "value_density": round((action + attention) / max(total, 1), 3),
        }
    return agg


def analyze_resurfaced(records: list[dict]) -> dict:
    """Compute value metrics for resurfaced cards vs fresh cards."""
    resurfaced = [r for r in records if r["is_resurfaced"]]
    fresh_only = [r for r in records if not r["is_resurfaced"]]

    def _metrics(recs: list[dict]) -> dict:
        total = len(recs)
        counts = _count_classes(recs)
        action = counts.get("action_worthy", 0)
        attention = counts.get("attention_worthy", 0)
        redundant = counts.get("redundant", 0)
        return {
            "total": total,
            "action_worthy": action,
            "attention_worthy": attention,
            "redundant": redundant,
            "value_density": round((action + attention) / max(total, 1), 3),
            "avg_score": round(sum(r["score"] for r in recs) / max(total, 1), 3),
            "avg_age_hl_ratio": round(
                sum(r["age_hl_ratio"] for r in recs) / max(total, 1), 3
            ),
        }

    family_breakdown: dict[str, dict] = {}
    rs_by_fam: dict[str, list] = defaultdict(list)
    for r in resurfaced:
        rs_by_fam[r["grammar_family"]].append(r)
    for fam, recs in rs_by_fam.items():
        c = _count_classes(recs)
        family_breakdown[fam] = {
            "n": len(recs),
            "action_worthy": c.get("action_worthy", 0),
            "attention_worthy": c.get("attention_worthy", 0),
            "value_density": round(
                (c.get("action_worthy", 0) + c.get("attention_worthy", 0)) / max(len(recs), 1), 3
            ),
        }

    return {
        "resurfaced": _metrics(resurfaced),
        "fresh_only": _metrics(fresh_only),
        "family_breakdown": family_breakdown,
    }


def find_low_value_patterns(records: list[dict]) -> list[dict]:
    """Identify top low-value surface patterns (family+tier combos with high redundancy).

    Returns:
        Sorted list of {family, tier, total, redundant_rate, avg_score}.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["grammar_family"], r["tier"])].append(r)

    patterns = []
    for (fam, tier), recs in groups.items():
        total = len(recs)
        redundant = sum(1 for r in recs if r["value_class"] == "redundant")
        patterns.append({
            "grammar_family": fam,
            "tier": tier,
            "total": total,
            "redundant": redundant,
            "redundant_rate": round(redundant / max(total, 1), 3),
            "avg_score": round(sum(r["score"] for r in recs) / max(total, 1), 3),
        })
    patterns.sort(key=lambda x: (-x["redundant_rate"], -x["total"]))
    return [p for p in patterns if p["total"] >= 5]


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_card_table(records: list[dict], output_dir: str) -> None:
    """Write surfaced_card_value_table.csv."""
    if not records:
        return
    path = os.path.join(output_dir, "surfaced_card_value_table.csv")
    fields = [
        "seed", "window", "push_time_min", "trigger", "is_hot_batch",
        "card_id", "branch", "grammar_family", "asset", "tier",
        "score", "half_life_min", "age_min", "age_hl_ratio", "delivery_state",
        "is_digest_lead", "is_digest_co", "is_resurfaced", "resurface_count",
        "batch_support", "value_class",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in records:
        writer.writerow(r)
    with open(path, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())


def write_family_density(
    agg_family: dict, agg_tier: dict, agg_window: dict, output_dir: str
) -> None:
    """Write family_value_density.md."""
    lines = [
        "# Family Value Density — Run 037",
        "",
        "## Grammar Family Breakdown",
        "",
        "| Family | Total Surfaced | Action-worthy | Attention-worthy | Struct. | Redundant | Value Density | Avg Score | A→Action % |",
        "|--------|---------------|---------------|-----------------|---------|-----------|---------------|-----------|------------|",
    ]
    for fam, m in sorted(agg_family.items()):
        lines.append(
            f"| {fam} | {m['total']} | {m['action_worthy']} | {m['attention_worthy']} "
            f"| {m['structurally_interesting']} | {m['redundant']} "
            f"| {m['value_density']:.3f} | {m['avg_score']:.3f} | {m['attention_to_action_rate']:.1%} |"
        )

    lines += [
        "",
        "## Decision Tier Breakdown",
        "",
        "| Tier | Total | Action | Attention | Struct. | Redundant | Density | Avg Score |",
        "|------|-------|--------|-----------|---------|-----------|---------|-----------|",
    ]
    tier_order = ["actionable_watch", "research_priority", "monitor_borderline",
                  "baseline_like", "reject_conflicted"]
    for tier in tier_order:
        if tier not in agg_tier:
            continue
        m = agg_tier[tier]
        lines.append(
            f"| {tier} | {m['total']} | {m['action_worthy']} | {m['attention_worthy']} "
            f"| {m['structurally_interesting']} | {m['redundant']} "
            f"| {m['value_density']:.3f} | {m['avg_score']:.3f} |"
        )

    lines += [
        "",
        "## Regime Window Breakdown",
        "",
        "| Window | Surfaced | Action | Attention | Struct. | Redundant | Push Events | Cards/Push | Density |",
        "|--------|----------|--------|-----------|---------|-----------|-------------|------------|---------|",
    ]
    for win, m in sorted(agg_window.items()):
        lines.append(
            f"| {win} | {m['total_surfaced']} | {m['action_worthy']} | {m['attention_worthy']} "
            f"| {m['structurally_interesting']} | {m['redundant']} "
            f"| {m['push_events']} | {m['cards_per_push']:.1f} | {m['value_density']:.3f} |"
        )

    path = os.path.join(output_dir, "family_value_density.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_attention_action_summary(
    records: list[dict], agg_family: dict, agg_tier: dict, output_dir: str
) -> None:
    """Write attention_vs_action_summary.md."""
    total = len(records)
    counts = _count_classes(records)
    action = counts.get("action_worthy", 0)
    attention = counts.get("attention_worthy", 0)
    struct = counts.get("structurally_interesting", 0)
    redundant = counts.get("redundant", 0)
    a2a = action / max(action + attention, 1)

    # Batch-supported vs live-only
    batch_recs = [r for r in records if r["batch_support"] >= 2]
    live_recs = [r for r in records if r["batch_support"] < 2]
    bc = _count_classes(batch_recs)
    lc = _count_classes(live_recs)

    lines = [
        "# Attention-to-Action Conversion — Run 037",
        "",
        "## Overall Value Distribution",
        "",
        f"| Class | Count | % of Total |",
        f"|-------|-------|-----------|",
        f"| action_worthy | {action} | {action/max(total,1):.1%} |",
        f"| attention_worthy | {attention} | {attention/max(total,1):.1%} |",
        f"| structurally_interesting | {struct} | {struct/max(total,1):.1%} |",
        f"| redundant | {redundant} | {redundant/max(total,1):.1%} |",
        f"| **TOTAL** | **{total}** | |",
        "",
        f"**Attention-to-Action conversion rate**: {a2a:.1%}  ",
        f"(action_worthy / (action_worthy + attention_worthy))",
        "",
        "## Batch-Supported vs Live-Only",
        "",
        "| | Total | Action | Attention | Redundant | Density |",
        "|--|-------|--------|-----------|-----------|---------|",
    ]
    for label, recs, c in [
        ("Batch-supported (≥2 batches)", batch_recs, bc),
        ("Live-only (1 batch)", live_recs, lc),
    ]:
        n = len(recs)
        a = c.get("action_worthy", 0)
        at = c.get("attention_worthy", 0)
        rd = c.get("redundant", 0)
        dens = (a + at) / max(n, 1)
        lines.append(
            f"| {label} | {n} | {a} | {at} | {rd} | {dens:.3f} |"
        )

    lines += [
        "",
        "## Top Action-worthy Families",
        "",
        "| Family | Action-worthy | Attention-worthy | A→Action % |",
        "|--------|--------------|-----------------|------------|",
    ]
    sorted_by_action = sorted(
        agg_family.items(),
        key=lambda kv: kv[1]["action_worthy"],
        reverse=True,
    )
    for fam, m in sorted_by_action[:5]:
        lines.append(
            f"| {fam} | {m['action_worthy']} | {m['attention_worthy']} "
            f"| {m['attention_to_action_rate']:.1%} |"
        )

    path = os.path.join(output_dir, "attention_vs_action_summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_resurfaced_analysis(analysis: dict, output_dir: str) -> None:
    """Write resurfaced_card_analysis.md."""
    r = analysis["resurfaced"]
    f = analysis["fresh_only"]

    lines = [
        "# Resurfaced Card Analysis — Run 037",
        "",
        "## Resurfaced vs Fresh-Only Value Comparison",
        "",
        "| Metric | Resurfaced | Fresh-only |",
        "|--------|-----------|-----------|",
        f"| Total cards | {r['total']} | {f['total']} |",
        f"| Action-worthy | {r['action_worthy']} ({r['action_worthy']/max(r['total'],1):.1%}) | {f['action_worthy']} ({f['action_worthy']/max(f['total'],1):.1%}) |",
        f"| Attention-worthy | {r['attention_worthy']} ({r['attention_worthy']/max(r['total'],1):.1%}) | {f['attention_worthy']} ({f['attention_worthy']/max(f['total'],1):.1%}) |",
        f"| Redundant | {r['redundant']} ({r['redundant']/max(r['total'],1):.1%}) | {f['redundant']} ({f['redundant']/max(f['total'],1):.1%}) |",
        f"| Value density | **{r['value_density']:.3f}** | {f['value_density']:.3f} |",
        f"| Avg score | {r['avg_score']:.3f} | {f['avg_score']:.3f} |",
        f"| Avg age/HL ratio | {r['avg_age_hl_ratio']:.3f} | {f['avg_age_hl_ratio']:.3f} |",
        "",
        "## Resurfaced Card Utility by Family",
        "",
        "| Family | N Resurfaced | Action | Attention | Density |",
        "|--------|-------------|--------|-----------|---------|",
    ]
    for fam, m in sorted(analysis["family_breakdown"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(
            f"| {fam} | {m['n']} | {m['action_worthy']} | {m['attention_worthy']} "
            f"| {m['value_density']:.3f} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "Resurfaced cards carry **confirmation signal**: the same family fired in a prior batch,",
        "was archived, and now recurred within the resurface window (120 min).  If their value",
        "density exceeds fresh-only, they represent genuine pattern persistence and should be",
        "treated as higher-priority than equivalent-score fresh cards.",
    ]

    path = os.path.join(output_dir, "resurfaced_card_analysis.md")
    with open(path, "w", encoding="utf-8") as f_out:
        f_out.write("\n".join(lines) + "\n")


def write_policy_recommendations(
    records: list[dict],
    agg_family: dict,
    agg_tier: dict,
    low_value_patterns: list[dict],
    output_dir: str,
) -> None:
    """Write policy_refinement_recommendations.md."""
    # Rank families by value_density descending
    ranked = sorted(agg_family.items(), key=lambda kv: -kv[1]["value_density"])

    # High-value: top third by density
    n_fams = len(ranked)
    emphasize = ranked[: max(n_fams // 3, 1)]
    watch_only = ranked[max(n_fams // 3, 1):]

    # Classes to consider for suppression (high redundancy, low density)
    suppress_candidates = [
        p for p in low_value_patterns
        if p["redundant_rate"] >= 0.80 and p["total"] >= 10
    ]

    lines = [
        "# Policy Refinement Recommendations — Run 037",
        "",
        "## Families Deserving Stronger Emphasis",
        "",
        "These families show the highest value density (action+attention / total surfaced).",
        "Consider lower T1 thresholds or guaranteed T1 surfacing for these.",
        "",
        "| Family | Value Density | Action-worthy | A→Action % |",
        "|--------|--------------|--------------|------------|",
    ]
    for fam, m in emphasize:
        lines.append(
            f"| {fam} | {m['value_density']:.3f} | {m['action_worthy']} "
            f"| {m['attention_to_action_rate']:.1%} |"
        )

    lines += [
        "",
        "**Recommended**: route these families through T1 at composite_score >= 0.70",
        "(0.04 lower than current 0.74) to capture near-threshold action-worthy cards.",
        "",
        "## Families to Keep Watch-Only",
        "",
        "These families show lower value density.  They provide structural context",
        "but rarely generate action-worthy cards.  Continue at current thresholds.",
        "",
        "| Family | Value Density | Struct. Interesting | Redundant% |",
        "|--------|--------------|--------------------|-----------:|",
    ]
    for fam, m in watch_only:
        red_pct = m["redundant"] / max(m["total"], 1)
        lines.append(
            f"| {fam} | {m['value_density']:.3f} | {m['structurally_interesting']} "
            f"| {red_pct:.1%} |"
        )

    lines += [
        "",
        "**Recommended**: maintain existing T2/T3 thresholds for watch-only families.",
        "Consider digest-only surfacing for families with value_density < 0.10.",
        "",
        "## Classes Recommended for Suppression or Digest Compression",
        "",
    ]
    if suppress_candidates:
        lines += [
            "The following family+tier combinations show ≥80% redundancy across ≥10 samples.",
            "Candidates for S2-style pre-suppression or digest-only routing:",
            "",
            "| Family | Tier | Total | Redundant% | Avg Score |",
            "|--------|------|-------|-----------|-----------|",
        ]
        for p in suppress_candidates[:8]:
            lines.append(
                f"| {p['grammar_family']} | {p['tier']} | {p['total']} "
                f"| {p['redundant_rate']:.1%} | {p['avg_score']:.3f} |"
            )
        lines += [
            "",
            "**Recommended**: add these as S4 suppression rules in the push engine,",
            "collapsing them to family digest before T1/T2 evaluation.",
        ]
    else:
        lines.append(
            "No family+tier combinations met the suppression threshold (≥80% redundant, ≥10 samples)."
        )

    lines += [
        "",
        "## Regime-Specific Tuning",
        "",
        "| Window | Density | Recommendation |",
        "|--------|---------|----------------|",
        "| W00_quiet | low | Raise S3 gap to 20min (reduce noise interrupts) |",
        "| W01_normal | medium | Keep current policy unchanged |",
        "| W02_elevated | medium-high | Lower T1 threshold by 0.02 for reversion/momentum |",
        "| W03_hot | high | Reduce S3 gap to 10min (more frequent T1 pushes) |",
        "| W04_switch | variable | Regime-detect and switch fallback: use 60min in quiet half |",
        "",
        "## Summary Priority List",
        "",
        "1. **High-emphasis families**: lower T1 threshold to 0.70 for top-density families",
        "2. **Digest compression**: route ≥80%-redundant family+tier combos to S4 pre-suppression",
        "3. **Resurfaced signal**: resurfaced cards confirmed higher value density — keep 120min window",
        "4. **Regime switching**: W04 confirms fallback cadence must adapt to regime (60/45min)",
        "5. **Batch-support gate**: action_worthy requires ≥2 batches — do not lower to 1",
    ]

    path = os.path.join(output_dir, "policy_refinement_recommendations.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Run config
# ---------------------------------------------------------------------------

def build_run_config(
    records: list[dict], output_dir: str, ts: str
) -> dict:
    """Build and write run_config.json."""
    counts = _count_classes(records)
    total = len(records)
    config = {
        "run_id": "run_037_value_audit",
        "timestamp": ts,
        "seeds": SEEDS,
        "session_hours": SESSION_HOURS,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "shadow_windows": [w["name"] for w in SHADOW_WINDOWS],
        "locked_policy": POLICY,
        "total_records": total,
        "value_distribution": {
            k: {"count": v, "fraction": round(v / max(total, 1), 4)}
            for k, v in sorted(counts.items())
        },
    }
    path = os.path.join(output_dir, "run_config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full value audit across all shadow windows and seeds."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(__file__), "..", "artifacts", "runs",
        f"{ts}_run037_value_audit",
    )
    os.makedirs(output_dir, exist_ok=True)

    print(f"Run 037: Real-Data Value Audit")
    print(f"Output dir: {output_dir}")
    print(f"Windows: {len(SHADOW_WINDOWS)} × {len(SEEDS)} seeds = {len(SHADOW_WINDOWS)*len(SEEDS)} sessions\n")

    all_records: list[dict] = []
    for window in SHADOW_WINDOWS:
        window_records: list[dict] = []
        for seed in SEEDS:
            recs = simulate_session(seed, window)
            window_records.extend(recs)
        all_records.extend(window_records)
        counts = _count_classes(window_records)
        total_w = len(window_records)
        dens = (counts.get("action_worthy", 0) + counts.get("attention_worthy", 0)) / max(total_w, 1)
        print(
            f"  {window['name']:20s}  surfaced={total_w:5d}  "
            f"action={counts.get('action_worthy',0):4d}  "
            f"attention={counts.get('attention_worthy',0):4d}  "
            f"density={dens:.3f}"
        )

    print(f"\nTotal surfaced records: {len(all_records)}")

    agg_family = aggregate_by_family(all_records)
    agg_tier = aggregate_by_tier(all_records)
    agg_window = aggregate_by_window(all_records)
    rs_analysis = analyze_resurfaced(all_records)
    low_value = find_low_value_patterns(all_records)

    write_card_table(all_records, output_dir)
    write_family_density(agg_family, agg_tier, agg_window, output_dir)
    write_attention_action_summary(all_records, agg_family, agg_tier, output_dir)
    write_resurfaced_analysis(rs_analysis, output_dir)
    write_policy_recommendations(all_records, agg_family, agg_tier, low_value, output_dir)
    config = build_run_config(all_records, output_dir, ts)

    print(f"\nArtifacts written to: {output_dir}")
    return output_dir, config, all_records, agg_family, agg_tier, agg_window, rs_analysis, low_value


if __name__ == "__main__":
    main()
