#!/usr/bin/env python3
"""
Run 045: Live-data reality pass simulation.

Tests frozen delivery policy (run_034 + run_036 regime-aware fallback) under
14-day non-stationary conditions:
  - daily hot_batch_probability drawn from Uniform(0.10, 0.55)
  - regime label dynamically derived from hot_prob
  - biased family distribution (cross_asset 30%, momentum 25%, ...)
  - batch_interval = 30 min, session = 8h

Tracks: push/fallback ratio, reviews/day, missed_critical,
        archive_loss%, family_coverage, burden vs guardrails.
Outputs: claim_status_live_check comparing frozen expectations.
"""

import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ── Determinism ──────────────────────────────────────────────────────────────
SEED = 45
random.seed(SEED)

# ── Frozen policy (run_034 recommended_config + run_036 regime-aware fallback)
POLICY: dict = {
    "T1_score_threshold": 0.74,
    "T2_fresh_count_threshold": 3,
    "S2_min_family_size": 2,
    "S3_min_gap_min": 15.0,
    "fallback_cadence_quiet_min": 60,   # hot_prob <= 0.25  (run_036)
    "fallback_cadence_active_min": 45,  # hot_prob >  0.25  (run_036)
    "archive_ratio_hl": 5.0,
    "resurface_window_min": 120,
    "archive_max_age_min": 480,
    "half_lives": {
        "actionable_watch": 40,
        "research_priority": 50,
        "monitor_borderline": 60,
        "baseline": 90,
    },
}

# ── Simulation constants ──────────────────────────────────────────────────────
FAMILIES: list[str] = ["cross_asset", "momentum", "reversion", "unwind", "null"]
FAMILY_WEIGHTS: list[float] = [0.30, 0.25, 0.20, 0.15, 0.10]
BATCH_INTERVAL_MIN: int = 30
SESSION_HOURS: int = 8
BATCHES_PER_DAY: int = (SESSION_HOURS * 60) // BATCH_INTERVAL_MIN   # 16
SIMULATION_DAYS: int = 14
CARDS_PER_BATCH_MEAN: int = 15  # cards drawn Uniform(8, 22)

# ── Frozen expectations (baseline from run_034/035/036/039) ───────────────────
FROZEN_EXPECTATIONS: dict = {
    "reviews_per_day_max": 35,          # alert threshold (run_034 guardrails)
    "reviews_per_day_warn": 25,
    "missed_critical_max": 0,           # zero-miss guarantee
    "archive_loss_pct_max": 25.0,       # run_039 measured ~21% loss
    "push_ratio_min": 0.25,             # push should contribute meaningfully
    "family_coverage_min": 1.0,         # all 5 families must appear over 14 days
    "quiet_reviews_lt_active": True,    # regime-aware fallback claim (run_036)
    "active_push_ratio_gt_quiet": True, # push dominates on hot days
}

# ── Claims under live-like conditions ─────────────────────────────────────────
CLAIMS: list[dict] = [
    {
        "id": "C1",
        "description": "missed_critical = 0 under 14-day non-stationary hot_prob",
        "expectation": "missed_critical == 0",
    },
    {
        "id": "C2",
        "description": "avg reviews/day stays below alert threshold (35)",
        "expectation": "reviews_per_day < 35",
    },
    {
        "id": "C3",
        "description": "push ratio >= 25% overall (push contributes meaningfully)",
        "expectation": "push_ratio >= 0.25",
    },
    {
        "id": "C4",
        "description": "100% family coverage across all 14 days",
        "expectation": "family_coverage == 1.0",
    },
    {
        "id": "C5",
        "description": "archive permanent loss < 25% (run_039 baseline: ~21%)",
        "expectation": "archive_loss_pct < 25.0",
    },
    {
        "id": "C6",
        "description": "quiet days have fewer reviews than active days (regime-aware fallback)",
        "expectation": "regime_avg_reviews['quiet'] < regime_avg_reviews['active']",
    },
    {
        "id": "C7",
        "description": "active days push_ratio > quiet days push_ratio",
        "expectation": "regime_avg_push_ratio['active'] > regime_avg_push_ratio['quiet']",
    },
]


# ── Card model ─────────────────────────────────────────────────────────────────
@dataclass
class Card:
    """Single hypothesis card in the delivery deck."""

    card_id: int
    family: str
    tier: str
    score: float
    birth_time: int    # minutes since session start (0-based)
    half_life: int     # minutes

    archived: bool = False
    archive_time: Optional[int] = None
    resurfaced: bool = False
    reviewed: bool = False

    def archive_threshold(self) -> int:
        """Time at which card is archived (5× HL)."""
        return self.birth_time + int(POLICY["archive_ratio_hl"] * self.half_life)

    def is_critical(self) -> bool:
        return self.tier == "actionable_watch" and self.score >= POLICY["T1_score_threshold"]

    def is_high_priority(self) -> bool:
        return self.tier in ("actionable_watch", "research_priority")

    def state_at(self, t: int) -> str:
        """Lifecycle state: fresh / active / aging / digest_only / archived."""
        if self.archived:
            return "archived"
        age = t - self.birth_time
        hl = self.half_life
        if age < hl:
            return "fresh"
        if age < 2 * hl:
            return "active"
        if age < 3 * hl:
            return "aging"
        return "digest_only"


# ── Card generation ────────────────────────────────────────────────────────────
def _make_card(card_id: int, hot_prob: float, t: int) -> Card:
    """Generate one card at time t with hot_prob-driven score distribution."""
    family = random.choices(FAMILIES, weights=FAMILY_WEIGHTS)[0]
    is_hot = random.random() < hot_prob
    if is_hot:
        score = random.uniform(0.65, 0.98)
        if score >= 0.80:
            tier = "actionable_watch"
        else:
            tier = "research_priority"
    else:
        score = random.uniform(0.20, 0.70)
        if score >= 0.55:
            tier = "monitor_borderline"
        else:
            tier = "baseline"
    hl = POLICY["half_lives"][tier]
    return Card(card_id=card_id, family=family, tier=tier, score=score,
                birth_time=t, half_life=hl)


def generate_batch(counter_ref: list, hot_prob: float, t: int) -> list[Card]:
    """Generate 8–22 cards. counter_ref is a 1-element list used as mutable int."""
    n = random.randint(8, 22)
    batch = []
    for _ in range(n):
        batch.append(_make_card(counter_ref[0], hot_prob, t))
        counter_ref[0] += 1
    return batch


# ── Regime helpers ─────────────────────────────────────────────────────────────
def get_regime(hot_prob: float) -> str:
    """quiet / transition / active derived from hot_prob."""
    if hot_prob <= 0.20:
        return "quiet"
    if hot_prob >= 0.40:
        return "active"
    return "transition"


def get_fallback_cadence(hot_prob: float) -> int:
    """Run_036 regime-aware cadence."""
    if hot_prob <= 0.25:
        return POLICY["fallback_cadence_quiet_min"]   # 60 min
    return POLICY["fallback_cadence_active_min"]       # 45 min


# ── Delivery logic (S1/S2/S3, T1/T2, fallback) ────────────────────────────────
def check_s1(deck: list[Card]) -> bool:
    """S1: no high-priority non-archived cards → suppress."""
    return not any(not c.archived and c.is_high_priority() for c in deck)


def check_s2(deck: list[Card]) -> bool:
    """S2: all non-archived cards are low-priority AND family-collapsed."""
    live = [c for c in deck if not c.archived]
    if not live:
        return True
    if any(c.is_high_priority() for c in live):
        return False
    counts: Counter = Counter(c.family for c in live)
    return all(counts[c.family] >= POLICY["S2_min_family_size"] for c in live)


def check_s3(last_push_time: Optional[int], t: int) -> bool:
    """S3: rate-limit — minimum 15 min gap between push events."""
    if last_push_time is None:
        return False
    return (t - last_push_time) < POLICY["S3_min_gap_min"]


def check_t1(batch: list[Card]) -> bool:
    """T1: any high-priority card in batch has score >= threshold."""
    return any(c.is_high_priority() and c.score >= POLICY["T1_score_threshold"]
               for c in batch)


def check_t2(batch: list[Card]) -> bool:
    """T2: batch contains >= 3 high-priority cards."""
    return sum(1 for c in batch if c.is_high_priority()) >= POLICY["T2_fresh_count_threshold"]


# ── Single-day simulator ───────────────────────────────────────────────────────
def simulate_day(day: int, hot_prob: float) -> dict:
    """Simulate one 8-hour session. Returns metrics dict."""
    regime = get_regime(hot_prob)
    fallback_cadence = get_fallback_cadence(hot_prob)

    deck: list[Card] = []
    archive_pool: list[Card] = []
    card_counter = [0]        # mutable ref for card IDs within this day

    last_push_time: Optional[int] = None   # only resets on T1/T2 push

    push_reviews = 0
    fallback_reviews = 0
    s1_count = 0
    s2_count = 0
    s3_count = 0
    missed_critical = 0
    total_archived = 0
    permanent_loss = 0
    resurfaced_count = 0
    stale_reviews = 0
    families_seen: set[str] = set()

    def do_review(t: int, rtype: str, batch: list[Card]) -> None:
        nonlocal push_reviews, fallback_reviews, last_push_time, stale_reviews
        for c in deck:
            c.reviewed = True
        for c in batch:
            families_seen.add(c.family)
        for c in deck:
            if not c.archived:
                families_seen.add(c.family)
        live_active = [c for c in deck if not c.archived and
                       c.state_at(t) in ("fresh", "active")]
        if not live_active:
            stale_reviews += 1
        if rtype == "push":
            push_reviews += 1
            last_push_time = t
        else:
            fallback_reviews += 1

    def expire_and_archive(t: int) -> None:
        nonlocal total_archived, missed_critical
        still_live, newly_archived = [], []
        for c in deck:
            if not c.archived and t >= c.archive_threshold():
                c.archived = True
                c.archive_time = t
                total_archived += 1
                if c.is_critical() and not c.reviewed:
                    missed_critical += 1
                newly_archived.append(c)
            else:
                still_live.append(c)
        deck.clear()
        deck.extend(still_live)
        archive_pool.extend(newly_archived)

        # Hard-delete expired archive entries (> 480 min since archival)
        survivors = []
        for c in archive_pool:
            if c.archive_time is not None and (t - c.archive_time) > POLICY["archive_max_age_min"]:
                if not c.resurfaced:
                    pass  # counted at end-of-day sweep
            else:
                survivors.append(c)
        archive_pool.clear()
        archive_pool.extend(survivors)

    def try_resurface(t: int, incoming_families: set[str]) -> None:
        nonlocal resurfaced_count
        for c in archive_pool:
            if not c.resurfaced and c.archive_time is not None:
                age_in_archive = t - c.archive_time
                if age_in_archive <= POLICY["resurface_window_min"]:
                    if c.family in incoming_families:
                        c.resurfaced = True
                        resurfaced_count += 1

    # ── Main batch loop ──────────────────────────────────────────────────────
    total_cards_generated = 0
    for batch_idx in range(BATCHES_PER_DAY):
        t = batch_idx * BATCH_INTERVAL_MIN   # 0, 30, 60, … 450 min

        batch = generate_batch(card_counter, hot_prob, t)
        total_cards_generated += len(batch)

        # Archive expired cards before processing batch
        expire_and_archive(t)

        # Add incoming batch to deck
        deck.extend(batch)

        # Try resurface
        try_resurface(t, {c.family for c in batch})

        # ── Delivery decision ────────────────────────────────────────────────
        push_fired = False
        t1 = check_t1(batch)
        t2 = check_t2(batch)

        if t1 or t2:
            if check_s1(deck):
                s1_count += 1
            elif check_s2(deck):
                s2_count += 1
            elif check_s3(last_push_time, t):
                s3_count += 1
            else:
                do_review(t, "push", batch)
                push_fired = True

        # ── Fallback check ───────────────────────────────────────────────────
        if not push_fired:
            ref = last_push_time if last_push_time is not None else 0
            if (t - ref) >= fallback_cadence:
                do_review(t, "fallback", batch)
                # Note: fallback does NOT reset last_push_time

    # ── End-of-day: sweep unreviewed critical cards still in deck ────────────
    for c in deck:
        if c.is_critical() and not c.reviewed:
            missed_critical += 1

    # ── Permanent loss: archived cards that were never resurfaced ────────────
    for c in archive_pool:
        if not c.resurfaced:
            permanent_loss += 1

    # ── Compute day metrics ──────────────────────────────────────────────────
    total_reviews = push_reviews + fallback_reviews
    push_ratio = push_reviews / total_reviews if total_reviews else 0.0
    archive_loss_pct = permanent_loss / total_archived * 100 if total_archived else 0.0
    stale_rate = stale_reviews / total_reviews if total_reviews else 0.0
    fallback_pct = fallback_reviews / total_reviews * 100 if total_reviews else 0.0
    family_coverage = len(families_seen) / len(FAMILIES)

    return {
        "day": day,
        "hot_prob": round(hot_prob, 3),
        "regime": regime,
        "fallback_cadence_min": fallback_cadence,
        "total_reviews": total_reviews,
        "push_reviews": push_reviews,
        "fallback_reviews": fallback_reviews,
        "push_ratio": round(push_ratio, 3),
        "fallback_pct": round(fallback_pct, 1),
        "s1_suppressions": s1_count,
        "s2_suppressions": s2_count,
        "s3_suppressions": s3_count,
        "missed_critical": missed_critical,
        "total_cards_generated": total_cards_generated,
        "total_archived": total_archived,
        "permanent_loss": permanent_loss,
        "archive_loss_pct": round(archive_loss_pct, 1),
        "resurfaced_count": resurfaced_count,
        "stale_rate": round(stale_rate, 3),
        "family_coverage": round(family_coverage, 3),
        "families_seen": sorted(families_seen),
    }


# ── 14-day simulation ──────────────────────────────────────────────────────────
def run_simulation() -> dict:
    """Run 14-day simulation. Returns full results dict."""
    random.seed(SEED)
    hot_probs = [round(random.uniform(0.10, 0.55), 3) for _ in range(SIMULATION_DAYS)]

    day_results = []
    for i, hp in enumerate(hot_probs, start=1):
        day_results.append(simulate_day(day=i, hot_prob=hp))

    # ── Aggregate ────────────────────────────────────────────────────────────
    total_reviews = sum(r["total_reviews"] for r in day_results)
    total_push = sum(r["push_reviews"] for r in day_results)
    total_fallback = sum(r["fallback_reviews"] for r in day_results)
    total_missed = sum(r["missed_critical"] for r in day_results)
    total_archived = sum(r["total_archived"] for r in day_results)
    total_perm_loss = sum(r["permanent_loss"] for r in day_results)

    reviews_per_day = total_reviews / SIMULATION_DAYS
    push_ratio = total_push / total_reviews if total_reviews else 0.0
    archive_loss_pct = total_perm_loss / total_archived * 100 if total_archived else 0.0
    avg_stale = sum(r["stale_rate"] for r in day_results) / SIMULATION_DAYS

    all_families: set[str] = set()
    for r in day_results:
        all_families.update(r["families_seen"])
    family_coverage = len(all_families) / len(FAMILIES)

    over_warn = sum(1 for r in day_results if r["total_reviews"] > 25)
    over_alert = sum(1 for r in day_results if r["total_reviews"] > 35)

    # Per-regime stats
    regime_rev: Counter = Counter()
    regime_push: Counter = Counter()
    regime_days: Counter = Counter()
    for r in day_results:
        rg = r["regime"]
        regime_rev[rg] += r["total_reviews"]
        regime_push[rg] += r["push_reviews"]
        regime_days[rg] += 1

    regime_avg_reviews = {
        rg: round(regime_rev[rg] / regime_days[rg], 1)
        for rg in regime_days
    }
    regime_avg_push_ratio = {
        rg: round(regime_push[rg] / regime_rev[rg], 3)
        if regime_rev[rg] > 0 else 0.0
        for rg in regime_days
    }

    agg = {
        "reviews_per_day": round(reviews_per_day, 1),
        "total_reviews": total_reviews,
        "push_reviews": total_push,
        "fallback_reviews": total_fallback,
        "push_ratio": round(push_ratio, 3),
        "missed_critical_total": total_missed,
        "total_archived": total_archived,
        "permanent_loss_total": total_perm_loss,
        "archive_loss_pct": round(archive_loss_pct, 1),
        "avg_stale_rate": round(avg_stale, 3),
        "family_coverage_14d": round(family_coverage, 3),
        "families_seen_14d": sorted(all_families),
        "over_warn_days": over_warn,
        "over_alert_days": over_alert,
        "regime_day_counts": dict(regime_days),
        "regime_avg_reviews": regime_avg_reviews,
        "regime_avg_push_ratio": regime_avg_push_ratio,
    }

    # ── Claim status live check ───────────────────────────────────────────────
    claims_out = []
    for claim in CLAIMS:
        cid = claim["id"]
        if cid == "C1":
            passed = total_missed == 0
            value = total_missed
        elif cid == "C2":
            passed = reviews_per_day < 35
            value = round(reviews_per_day, 1)
        elif cid == "C3":
            passed = push_ratio >= 0.25
            value = round(push_ratio, 3)
        elif cid == "C4":
            passed = family_coverage == 1.0
            value = round(family_coverage, 3)
        elif cid == "C5":
            passed = archive_loss_pct < 25.0
            value = round(archive_loss_pct, 1)
        elif cid == "C6":
            q_rev = regime_avg_reviews.get("quiet", 0)
            a_rev = regime_avg_reviews.get("active", 0)
            passed = q_rev < a_rev if (q_rev and a_rev) else None
            value = f"quiet={q_rev}, active={a_rev}"
        elif cid == "C7":
            q_push = regime_avg_push_ratio.get("quiet", 0)
            a_push = regime_avg_push_ratio.get("active", 0)
            passed = a_push > q_push if (regime_days.get("active") and regime_days.get("quiet")) else None
            value = f"quiet={q_push}, active={a_push}"
        else:
            passed = None
            value = "n/a"

        status = "PASS" if passed is True else ("FAIL" if passed is False else "N/A")
        claims_out.append({
            "claim_id": cid,
            "description": claim["description"],
            "expectation": claim["expectation"],
            "value": value,
            "status": status,
        })

    return {
        "run_id": "run_045_live_reality_pass",
        "simulation_config": {
            "seed": SEED,
            "simulation_days": SIMULATION_DAYS,
            "batch_interval_min": BATCH_INTERVAL_MIN,
            "session_hours": SESSION_HOURS,
            "batches_per_day": BATCHES_PER_DAY,
            "family_weights": dict(zip(FAMILIES, FAMILY_WEIGHTS)),
            "hot_prob_range": [0.10, 0.55],
            "policy_source": "run_034_recommended_config + run_036_regime_aware_fallback",
        },
        "aggregate_metrics": agg,
        "frozen_expectations": FROZEN_EXPECTATIONS,
        "claim_status_live_check": claims_out,
        "day_results": day_results,
    }


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    """Run simulation, save results, print summary."""
    results = run_simulation()
    agg = results["aggregate_metrics"]
    claims = results["claim_status_live_check"]

    # Save artifacts
    out_dir = Path("artifacts/runs/20260416_run045_live_reality_pass")
    out_dir.mkdir(parents=True, exist_ok=True)

    results_path = out_dir / "simulation_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # ── Console summary ──────────────────────────────────────────────────────
    print("=" * 60)
    print("RUN 045  Live-data reality pass  (14-day simulation)")
    print("=" * 60)

    print("\n── Daily hot_prob + regime ─────────────────────────────")
    header = f"{'Day':>4}  {'hot_prob':>8}  {'regime':>12}  {'FB cad':>7}  {'reviews':>7}  {'push%':>6}  {'missed':>6}"
    print(header)
    for r in results["day_results"]:
        push_pct = r["push_ratio"] * 100
        print(
            f"{r['day']:>4}  {r['hot_prob']:>8.3f}  {r['regime']:>12}  "
            f"{r['fallback_cadence_min']:>7}  {r['total_reviews']:>7}  "
            f"{push_pct:>5.1f}%  {r['missed_critical']:>6}"
        )

    print("\n── Aggregate metrics ───────────────────────────────────")
    print(f"  reviews/day avg      : {agg['reviews_per_day']}")
    print(f"  push reviews         : {agg['push_reviews']}")
    print(f"  fallback reviews     : {agg['fallback_reviews']}")
    print(f"  push ratio           : {agg['push_ratio']:.1%}")
    print(f"  missed_critical      : {agg['missed_critical_total']}")
    print(f"  archive_loss%        : {agg['archive_loss_pct']}%")
    print(f"  avg stale_rate       : {agg['avg_stale_rate']:.1%}")
    print(f"  family_coverage (14d): {agg['family_coverage_14d']:.0%}")
    print(f"  over warn (>25/day)  : {agg['over_warn_days']} days")
    print(f"  over alert (>35/day) : {agg['over_alert_days']} days")

    print("\n── Regime breakdown ────────────────────────────────────")
    for rg in ("quiet", "transition", "active"):
        cnt = agg["regime_day_counts"].get(rg, 0)
        rev = agg["regime_avg_reviews"].get(rg, 0)
        pr = agg["regime_avg_push_ratio"].get(rg, 0)
        print(f"  {rg:>12}: {cnt} days | avg {rev:.1f} reviews/day | push {pr:.1%}")

    print("\n── Claim status live check ─────────────────────────────")
    for c in claims:
        mark = "✓" if c["status"] == "PASS" else ("✗" if c["status"] == "FAIL" else "—")
        print(f"  [{mark}] {c['claim_id']}  {c['status']:5}  val={c['value']}")
        print(f"         {c['description']}")

    passes = sum(1 for c in claims if c["status"] == "PASS")
    fails = sum(1 for c in claims if c["status"] == "FAIL")
    nas = sum(1 for c in claims if c["status"] == "N/A")
    print(f"\n  PASS {passes} / FAIL {fails} / N/A {nas}  ({len(claims)} claims)")

    print(f"\nArtifacts saved → {results_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
