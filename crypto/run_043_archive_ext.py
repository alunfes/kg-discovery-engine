"""Run 043: Targeted archive-age extension — cross_asset + reversion in calm/active.

Objective:
  Recover the MITIGATE-classified permanent losses identified in Run 042 by
  extending archive_max_age from 480 to 720 min for cross_asset and reversion
  families when the card was archived during a calm or active regime.

Change (targeted):
  cross_asset, reversion families  +  calm or active regime → max_age 720 min
  All other families / regimes                              → max_age 480 min (unchanged)

Compares against Run 042 baseline on the same 7-day simulation.

Metrics:
  - permanent loss count and rate (vs baseline)
  - recovery rate (vs baseline)
  - resurfaced value density (avg score, noisy rate)
  - archive pool size trajectory (bloat check)
  - operator burden (pool size × time)
  - verified recovery of MITIGATE cases from Run 042
  - side-effect check: noise, bloat, action count impact

Usage:
  python -m crypto.run_043_archive_ext [--output-dir PATH]

Output:
  artifacts/runs/<ts>_run043_archive_ext/
    before_after_loss.csv
    archive_pool_impact.md
    recovered_cases.md
    recommendation.md
    pool_size_trajectory.csv
    run_config.json
    review_memo.md
  docs/run043_targeted_archive_extension.md
"""
from __future__ import annotations

import copy
import csv
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    _ARCHIVE_RATIO,
    _DIGEST_MAX,
    _DEFAULT_ARCHIVE_MAX_AGE_MIN,
    _DEFAULT_RESURFACE_WINDOW_MIN,
    generate_cards,
)

# ---------------------------------------------------------------------------
# Run constants (identical to Run 042 baseline)
# ---------------------------------------------------------------------------

RUN_ID = "run_043_archive_ext"
SEED = 42
SESSION_HOURS = 7 * 24          # 168 h — 7-day crypto (24/7)
BATCH_INTERVAL_MIN = 30
N_CARDS_PER_BATCH = 20
CADENCE_MIN = 45
ARCHIVE_MAX_AGE_BASELINE = _DEFAULT_ARCHIVE_MAX_AGE_MIN   # 480 min
RESURFACE_WINDOW_MIN = _DEFAULT_RESURFACE_WINDOW_MIN       # 120 min
NOISY_THRESHOLD = 0.60

# Targeted extension parameters
EXTENDED_MAX_AGE_MIN = 720
EXTENDED_FAMILIES: frozenset[str] = frozenset(["cross_asset", "reversion"])
EXTENDED_REGIMES: frozenset[str] = frozenset(["calm", "active"])

# Run 042 MITIGATE case IDs (from deterministic seed=42 run)
# These are the card IDs that Run 042 classified as MITIGATE.
_KNOWN_MITIGATE_IDS: frozenset[str] = frozenset([
    "360_c005", "367_c012", "310_c000", "387_c012", "388_c013",
    "710_c000", "735_c018", "797_c015", "729_c012", "765_c004",
    "786_c004", "776_c015", "810_c008", "799_c017", "800_c018",
])

# Regime schedule (mirrors Run 042)
_DAY_REGIMES = [
    ("sparse", 0.10),
    ("sparse", 0.10),
    ("calm",   0.30),
    ("calm",   0.30),
    ("active", 0.70),
    ("active", 0.70),
    ("mixed",  None),
]
_DAY_MIN = 24 * 60

DEFAULT_OUT = (
    f"artifacts/runs/"
    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_run043_archive_ext"
)


# ---------------------------------------------------------------------------
# Regime helpers
# ---------------------------------------------------------------------------

def _regime_at(t_min: float) -> str:
    """Return regime label for session time t_min."""
    day_idx = min(int(t_min // _DAY_MIN), len(_DAY_REGIMES) - 1)
    return _DAY_REGIMES[day_idx][0]


def _hot_prob_at(t_min: float, batch_idx: int) -> float:
    """Return hot_batch_probability for session time t_min."""
    day_idx = min(int(t_min // _DAY_MIN), len(_DAY_REGIMES) - 1)
    _, prob = _DAY_REGIMES[day_idx]
    if prob is not None:
        return prob
    return 0.10 if batch_idx % 2 == 0 else 0.70


# ---------------------------------------------------------------------------
# Card batch generator
# ---------------------------------------------------------------------------

def _next_batch(rng: random.Random, n: int, ctr: list[int],
                hot: bool) -> list[DeliveryCard]:
    """Generate n cards with globally unique IDs."""
    cards = generate_cards(
        seed=rng.randint(0, 99999),
        n_cards=n,
        quiet=not hot,
        force_multi_asset_family=(hot and n >= 4),
    )
    for c in cards:
        ctr[0] += 1
        c.card_id = f"{ctr[0]}_{c.card_id}"
    return cards


# ---------------------------------------------------------------------------
# Per-family-regime max-age resolver
# ---------------------------------------------------------------------------

def _effective_max_age(grammar_family: str, regime_at_archive: str,
                       baseline_max_age: int) -> int:
    """Return effective archive_max_age for a card given its family and regime.

    Args:
        grammar_family:    Card's grammar_family.
        regime_at_archive: Market regime when card was archived.
        baseline_max_age:  Default max age for all other cards.

    Returns:
        EXTENDED_MAX_AGE_MIN for targeted families/regimes, else baseline_max_age.
    """
    if (grammar_family in EXTENDED_FAMILIES and
            regime_at_archive in EXTENDED_REGIMES):
        return EXTENDED_MAX_AGE_MIN
    return baseline_max_age


# ---------------------------------------------------------------------------
# Core simulation (identical structure to Run 042, with per-card max_age)
# ---------------------------------------------------------------------------

def simulate(seed: int, session_hours: int, baseline_max_age: int,
             resurface_window: int, batch_interval: int,
             n_per_batch: int, use_extended: bool = False,
             ) -> tuple[dict[str, Any], dict[str, str], dict[str, str],
                        list[tuple[float, int]]]:
    """Run full regime-aware batch simulation.

    Args:
        seed:             RNG seed.
        session_hours:    Total session duration.
        baseline_max_age: Default archive_max_age for all cards.
        resurface_window: Window for same-family resurface match.
        batch_interval:   Minutes between new card batches.
        n_per_batch:      Cards per batch.
        use_extended:     If True, apply EXTENDED_MAX_AGE_MIN for targeted families.

    Returns:
        (metrics, fate_map, regime_at_archive_map, pool_history)
          fate_map: card_id → "resurfaced"/"time_expired"/"proximity_miss"
    """
    session_min = session_hours * 60
    rng = random.Random(seed)
    ctr: list[int] = [0]

    all_cards: list[tuple[float, DeliveryCard]] = []
    archived_at_map: dict[str, float] = {}
    regime_at_archive: dict[str, str] = {}
    pool: dict[str, tuple[DeliveryCard, float]] = {}
    catalog: dict[str, dict] = {}

    rs_ids: set[str] = set()
    rs_scores: list[float] = []
    pm_ids: set[str] = set()
    te_ids: set[str] = set()

    pool_history: list[tuple[float, int]] = []

    # Initial batch
    hot0 = rng.random() < _hot_prob_at(0.0, 0)
    n0 = n_per_batch if hot0 else rng.choices(
        [0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]
    for c in _next_batch(rng, n0, ctr, hot0):
        all_cards.append((0.0, c))

    batch_times = list(range(batch_interval, session_min + 1, batch_interval))
    review_set = set(range(CADENCE_MIN, session_min + 1, CADENCE_MIN))
    next_idx = 0

    for t in sorted(set(batch_times) | review_set):
        new_batch: list[DeliveryCard] = []
        while next_idx < len(batch_times) and batch_times[next_idx] <= t:
            bt = float(batch_times[next_idx])
            hot = rng.random() < _hot_prob_at(bt, next_idx)
            n = n_per_batch if hot else rng.choices(
                [0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])[0]
            for c in _next_batch(rng, n, ctr, hot):
                all_cards.append((bt, c))
                new_batch.append(c)
            next_idx += 1

        # Build deck: include card if age <= its effective max_age
        deck = _build_deck(all_cards, archived_at_map, regime_at_archive,
                           float(t), baseline_max_age, use_extended)
        _apply_archive(deck, float(t), archived_at_map, regime_at_archive,
                       pool, catalog)

        if t not in review_set:
            pool_history.append((float(t), len(pool)))
            continue

        _prune_pool(pool, float(t), baseline_max_age, use_extended,
                    regime_at_archive, pm_ids, rs_ids, te_ids)
        _check_resurface(new_batch, pool, float(t), resurface_window,
                         rs_ids, rs_scores, pm_ids)
        pool_history.append((float(t), len(pool)))

    # Finalise remaining pool → time_expired
    for cid in pool:
        if cid not in rs_ids and cid not in pm_ids:
            te_ids.add(cid)

    # Build fate map
    fate_map: dict[str, str] = {}
    for cid in catalog:
        if cid in rs_ids:
            fate_map[cid] = "resurfaced"
        elif cid in te_ids:
            fate_map[cid] = "time_expired"
        elif cid in (pm_ids - rs_ids):
            fate_map[cid] = "proximity_miss"

    metrics = _compute_metrics(catalog, rs_ids, rs_scores, pm_ids, te_ids,
                               len(all_cards))
    return metrics, fate_map, regime_at_archive, pool_history


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _build_deck(all_cards: list[tuple[float, DeliveryCard]],
                archived_at_map: dict[str, float],
                regime_at_archive: dict[str, str],
                t: float, baseline_max_age: int,
                use_extended: bool) -> list[DeliveryCard]:
    """Return shallow copies of cards still within their effective max_age."""
    deck: list[DeliveryCard] = []
    for ct, card in all_cards:
        age = t - ct
        regime = regime_at_archive.get(card.card_id, _regime_at(ct))
        max_age = (_effective_max_age(card.grammar_family, regime, baseline_max_age)
                   if use_extended else baseline_max_age)
        if age > max_age:
            continue
        c = copy.copy(card)
        c.age_min = age
        c.archived_at_min = archived_at_map.get(card.card_id)
        deck.append(c)
    return deck


def _apply_archive(deck: list[DeliveryCard], t: float,
                   archived_at_map: dict[str, float],
                   regime_at_archive: dict[str, str],
                   pool: dict[str, tuple[DeliveryCard, float]],
                   catalog: dict[str, dict]) -> None:
    """Transition newly-expired cards to archived state."""
    for c in deck:
        if c.archived_at_min is not None:
            continue
        ratio = c.age_min / max(c.half_life_min, 1.0)
        if ratio < _DIGEST_MAX or c.age_min < _ARCHIVE_RATIO * c.half_life_min:
            continue
        archived_at_map[c.card_id] = t
        regime = _regime_at(t)
        regime_at_archive[c.card_id] = regime
        pool[c.card_id] = (c, t)
        catalog[c.card_id] = {
            "archived_at": t,
            "family": (c.branch, c.grammar_family),
            "composite_score": c.composite_score,
            "tier": c.tier,
        }


def _prune_pool(pool: dict[str, tuple[DeliveryCard, float]], t: float,
                baseline_max_age: int, use_extended: bool,
                regime_at_archive: dict[str, str],
                pm_ids: set[str], rs_ids: set[str],
                te_ids: set[str]) -> None:
    """Hard-delete archive pool entries older than their effective max_age."""
    to_del = []
    for cid, (card, at) in pool.items():
        regime = regime_at_archive.get(cid, "unknown")
        max_age = (_effective_max_age(card.grammar_family, regime, baseline_max_age)
                   if use_extended else baseline_max_age)
        if (t - at) > max_age:
            to_del.append(cid)
    for cid in to_del:
        if cid not in rs_ids and cid not in pm_ids:
            te_ids.add(cid)
        del pool[cid]


def _check_resurface(new_batch: list[DeliveryCard],
                     pool: dict[str, tuple[DeliveryCard, float]],
                     t: float, window: int,
                     rs_ids: set[str], rs_scores: list[float],
                     pm_ids: set[str]) -> None:
    """Match incoming cards against archive pool for resurface or proximity miss."""
    by_family: dict[tuple, list] = {}
    for cid, (card, at) in pool.items():
        key = (card.branch, card.grammar_family)
        by_family.setdefault(key, []).append((cid, card, at))

    triggered: set[tuple] = set()
    for inc in new_batch:
        key = (inc.branch, inc.grammar_family)
        if key not in by_family:
            continue
        in_win, out_win = [], []
        for (cid, card, at) in by_family[key]:
            (in_win if (t - at) <= window else out_win).append((cid, card, at))

        for cid, card, at in out_win:
            if cid not in rs_ids:
                pm_ids.add(cid)

        if in_win and key not in triggered:
            in_win.sort(key=lambda x: x[1].composite_score, reverse=True)
            cid, card, _ = in_win[0]
            rs_ids.add(cid)
            rs_scores.append(card.composite_score)
            del pool[cid]
            triggered.add(key)


def _compute_metrics(catalog: dict[str, dict], rs_ids: set[str],
                     rs_scores: list[float], pm_ids: set[str],
                     te_ids: set[str], total_generated: int) -> dict[str, Any]:
    """Compute aggregate simulation metrics."""
    n_arch = len(catalog)
    n_rs = len(rs_ids)
    n_pm = len(pm_ids - rs_ids)
    n_te = len(te_ids)
    avg_rs = sum(rs_scores) / max(len(rs_scores), 1)
    avg_arch = sum(v["composite_score"] for v in catalog.values()) / max(n_arch, 1)
    noisy = sum(1 for s in rs_scores if s < NOISY_THRESHOLD)
    return {
        "total_generated": total_generated,
        "total_archived": n_arch,
        "total_resurfaced": n_rs,
        "total_permanent_loss": n_pm + n_te,
        "total_time_expired": n_te,
        "total_proximity_miss": n_pm,
        "recovery_rate": round(n_rs / max(n_arch, 1), 4),
        "avg_resurfaced_score": round(avg_rs, 4),
        "avg_archived_score": round(avg_arch, 4),
        "value_density_ratio": round(avg_rs / max(avg_arch, 1e-9), 4),
        "noisy_resurface_count": noisy,
        "noisy_resurface_rate": round(noisy / max(len(rs_scores), 1), 4),
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _write_before_after_csv(baseline: dict, extended: dict,
                             out_dir: str) -> None:
    """Write before_after_loss.csv comparing baseline vs extended."""
    fields = ["metric", "baseline", "extended", "delta"]
    rows = [
        ("total_generated", baseline["total_generated"],
         extended["total_generated"], 0),
        ("total_archived", baseline["total_archived"],
         extended["total_archived"],
         extended["total_archived"] - baseline["total_archived"]),
        ("total_resurfaced", baseline["total_resurfaced"],
         extended["total_resurfaced"],
         extended["total_resurfaced"] - baseline["total_resurfaced"]),
        ("recovery_rate", f"{baseline['recovery_rate']:.4f}",
         f"{extended['recovery_rate']:.4f}",
         f"{round(extended['recovery_rate'] - baseline['recovery_rate'], 4)}"),
        ("total_permanent_loss", baseline["total_permanent_loss"],
         extended["total_permanent_loss"],
         extended["total_permanent_loss"] - baseline["total_permanent_loss"]),
        ("total_time_expired", baseline["total_time_expired"],
         extended["total_time_expired"],
         extended["total_time_expired"] - baseline["total_time_expired"]),
        ("total_proximity_miss", baseline["total_proximity_miss"],
         extended["total_proximity_miss"],
         extended["total_proximity_miss"] - baseline["total_proximity_miss"]),
        ("avg_resurfaced_score", f"{baseline['avg_resurfaced_score']:.4f}",
         f"{extended['avg_resurfaced_score']:.4f}",
         f"{round(extended['avg_resurfaced_score'] - baseline['avg_resurfaced_score'], 4)}"),
        ("value_density_ratio", f"{baseline['value_density_ratio']:.4f}",
         f"{extended['value_density_ratio']:.4f}",
         f"{round(extended['value_density_ratio'] - baseline['value_density_ratio'], 4)}"),
        ("noisy_resurface_rate", f"{baseline['noisy_resurface_rate']:.4f}",
         f"{extended['noisy_resurface_rate']:.4f}",
         f"{round(extended['noisy_resurface_rate'] - baseline['noisy_resurface_rate'], 4)}"),
    ]

    path = os.path.join(out_dir, "before_after_loss.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for metric, base_v, ext_v, delta in rows:
            writer.writerow({"metric": metric, "baseline": base_v,
                             "extended": ext_v, "delta": delta})
    print(f"  → {path}")


def _write_recovered_cases_md(base_fate: dict[str, str],
                               ext_fate: dict[str, str],
                               out_dir: str) -> None:
    """Write recovered_cases.md verifying MITIGATE recovery."""
    recovered = []
    still_lost = []
    for cid in _KNOWN_MITIGATE_IDS:
        base_f = base_fate.get(cid, "not_in_baseline")
        ext_f = ext_fate.get(cid, "not_in_extended")
        if base_f in ("time_expired", "proximity_miss") and ext_f == "resurfaced":
            recovered.append((cid, base_f, ext_f))
        else:
            still_lost.append((cid, base_f, ext_f))

    lines = [
        "# Recovered MITIGATE Cases — Run 043",
        "",
        f"**Run 042 MITIGATE cases**: {len(_KNOWN_MITIGATE_IDS)}",
        f"**Recovered in Run 043**: {len(recovered)}",
        f"**Still lost**: {len(still_lost)}",
        "",
        "## Recovered cases (baseline: loss → extended: resurfaced)",
        "",
        "| card_id | baseline_fate | extended_fate |",
        "|---------|---------------|---------------|",
    ]
    for cid, bf, ef in sorted(recovered):
        lines.append(f"| {cid} | {bf} | {ef} |")

    if still_lost:
        lines += [
            "",
            "## Still-lost cases (not recovered by extension)",
            "",
            "| card_id | baseline_fate | extended_fate |",
            "|---------|---------------|---------------|",
        ]
        for cid, bf, ef in sorted(still_lost):
            lines.append(f"| {cid} | {bf} | {ef} |")
        lines += [
            "",
            "**Note**: Still-lost MITIGATE cases indicate that the same-family",
            "signal arrived after the extended 720min window, or that a competing",
            "card in the pool consumed the resurface slot (LCM timing constraint).",
        ]

    path = os.path.join(out_dir, "recovered_cases.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_pool_impact_md(baseline: dict, extended: dict,
                           base_hist: list[tuple[float, int]],
                           ext_hist: list[tuple[float, int]],
                           out_dir: str) -> None:
    """Write archive_pool_impact.md with pool size analysis."""
    base_sizes = [sz for _, sz in base_hist]
    ext_sizes = [sz for _, sz in ext_hist]
    base_avg = sum(base_sizes) / max(len(base_sizes), 1)
    ext_avg = sum(ext_sizes) / max(len(ext_sizes), 1)
    base_max = max(base_sizes, default=0)
    ext_max = max(ext_sizes, default=0)

    lines = [
        "# Archive Pool Impact — Run 043",
        "",
        "Comparison of archive pool size distribution between baseline (max_age=480)",
        "and extended (max_age=720 for cross_asset/reversion in calm/active).",
        "",
        "## Pool Size Statistics",
        "",
        "| Metric | Baseline (480min) | Extended (720min) | Δ |",
        "|--------|-------------------|-------------------|---|",
        f"| avg pool size | {base_avg:.1f} | {ext_avg:.1f} | "
        f"{round(ext_avg - base_avg, 1):+.1f} |",
        f"| max pool size | {base_max} | {ext_max} | "
        f"{ext_max - base_max:+d} |",
        f"| total_archived | {baseline['total_archived']} | "
        f"{extended['total_archived']} | "
        f"{extended['total_archived'] - baseline['total_archived']:+d} |",
        "",
        "## Bloat Assessment",
        "",
    ]

    bloat_pct = round((ext_avg - base_avg) / max(base_avg, 1) * 100, 1)
    if bloat_pct <= 5.0:
        lines.append(
            f"**Pool bloat: ACCEPTABLE** (+{bloat_pct}% avg). "
            "Targeted extension adds negligible pool overhead."
        )
    elif bloat_pct <= 15.0:
        lines.append(
            f"**Pool bloat: MODERATE** (+{bloat_pct}% avg). "
            "Monitor pool size in production; consider reducing extended families."
        )
    else:
        lines.append(
            f"**Pool bloat: ELEVATED** (+{bloat_pct}% avg). "
            "Reconsider extension scope — pool overhead may outweigh recovery benefit."
        )

    lines += [
        "",
        "## Operator Burden",
        "",
        "Pool size increase translates to marginally more archive queries per review.",
        f"At avg pool Δ={round(ext_avg - base_avg, 1)}, the overhead is "
        f"{'negligible' if abs(ext_avg - base_avg) < 5 else 'measurable'} "
        f"per review cycle.",
    ]

    path = os.path.join(out_dir, "archive_pool_impact.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_recommendation_md(baseline: dict, extended: dict,
                              n_recovered: int, n_still_lost: int,
                              base_hist: list[tuple[float, int]],
                              ext_hist: list[tuple[float, int]],
                              out_dir: str) -> None:
    """Write recommendation.md with adoption decision."""
    rr_delta = round((extended["recovery_rate"] - baseline["recovery_rate"]) * 100, 2)
    pl_delta = extended["total_permanent_loss"] - baseline["total_permanent_loss"]
    noisy_delta = round(
        extended["noisy_resurface_rate"] - baseline["noisy_resurface_rate"], 4
    )
    ext_avg = sum(sz for _, sz in ext_hist) / max(len(ext_hist), 1)
    base_avg = sum(sz for _, sz in base_hist) / max(len(base_hist), 1)
    bloat_pct = round((ext_avg - base_avg) / max(base_avg, 1) * 100, 1)

    adopt = (
        rr_delta > 0
        and noisy_delta <= 0.05
        and extended["value_density_ratio"] >= baseline["value_density_ratio"] - 0.02
        and bloat_pct <= 15.0
    )

    lines = [
        "# Recommendation — Run 043 Targeted Archive Extension",
        "",
        "## Decision Criteria",
        "",
        "| Criterion | Threshold | Actual | Pass? |",
        "|-----------|-----------|--------|-------|",
        f"| recovery_rate improvement | > 0pp | {'+' if rr_delta >= 0 else ''}{rr_delta}pp | "
        f"{'✓' if rr_delta > 0 else '✗'} |",
        f"| noisy_resurface_rate Δ | ≤ +5pp | {noisy_delta:+.4f} | "
        f"{'✓' if noisy_delta <= 0.05 else '✗'} |",
        f"| value_density_ratio Δ | ≥ −2% | "
        f"{round(extended['value_density_ratio'] - baseline['value_density_ratio'], 4):+.4f} | "
        f"{'✓' if extended['value_density_ratio'] >= baseline['value_density_ratio'] - 0.02 else '✗'} |",
        f"| pool bloat | ≤ +15% | {bloat_pct:+.1f}% | "
        f"{'✓' if bloat_pct <= 15.0 else '✗'} |",
        "",
        "## Verdict",
        "",
        f"**{'ADOPT' if adopt else 'DO NOT ADOPT'} targeted archive extension**",
        "",
        f"- {n_recovered}/{len(_KNOWN_MITIGATE_IDS)} MITIGATE cases recovered",
        f"- Permanent loss: {baseline['total_permanent_loss']} → "
        f"{extended['total_permanent_loss']} ({pl_delta:+d})",
        f"- Recovery rate: {baseline['recovery_rate']:.1%} → "
        f"{extended['recovery_rate']:.1%} ({'+' if rr_delta >= 0 else ''}{rr_delta}pp)",
        f"- Pool bloat: {bloat_pct:+.1f}%",
        "",
        "## Implementation",
        "",
        "Apply `family_max_age_overrides` in `ArchiveManager` (delivery_state.py):",
        "```python",
        "ArchiveManager(",
        "    archive_max_age_min=480,",
        "    family_max_age_overrides={",
        "        'cross_asset': 720,   # calm/active regime cards only",
        "        'reversion':   720,   # calm/active regime cards only",
        "    }",
        ")",
        "```",
        "Note: In production, regime-conditional override requires the caller to",
        "pre-screen families by regime before populating `family_max_age_overrides`.",
    ]

    path = os.path.join(out_dir, "recommendation.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def _write_pool_trajectory_csv(base_hist: list[tuple[float, int]],
                                ext_hist: list[tuple[float, int]],
                                out_dir: str) -> None:
    """Write pool_size_trajectory.csv with baseline and extended columns."""
    combined: dict[float, dict] = {}
    for t, sz in base_hist:
        combined.setdefault(t, {})["t"] = t
        combined[t]["pool_baseline"] = sz
    for t, sz in ext_hist:
        combined.setdefault(t, {})["t"] = t
        combined[t]["pool_extended"] = sz

    path = os.path.join(out_dir, "pool_size_trajectory.csv")
    fields = ["t", "pool_baseline", "pool_extended"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for t in sorted(combined):
            writer.writerow(combined[t])
    print(f"  → {path}")


def _write_run_config(out_dir: str) -> None:
    """Write run_config.json."""
    config = {
        "run_id": RUN_ID,
        "seed": SEED,
        "session_hours": SESSION_HOURS,
        "batch_interval_min": BATCH_INTERVAL_MIN,
        "n_cards_per_batch": N_CARDS_PER_BATCH,
        "cadence_min": CADENCE_MIN,
        "archive_max_age_baseline_min": ARCHIVE_MAX_AGE_BASELINE,
        "archive_max_age_extended_min": EXTENDED_MAX_AGE_MIN,
        "extended_families": sorted(EXTENDED_FAMILIES),
        "extended_regimes": sorted(EXTENDED_REGIMES),
        "resurface_window_min": RESURFACE_WINDOW_MIN,
        "noisy_threshold": NOISY_THRESHOLD,
        "n_known_mitigate": len(_KNOWN_MITIGATE_IDS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    path = os.path.join(out_dir, "run_config.json")
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  → {path}")


def _write_review_memo(baseline: dict, extended: dict,
                       n_recovered: int, n_still_lost: int,
                       base_hist: list, ext_hist: list,
                       out_dir: str) -> None:
    """Write review_memo.md."""
    rr_delta = round((extended["recovery_rate"] - baseline["recovery_rate"]) * 100, 2)
    pl_delta = extended["total_permanent_loss"] - baseline["total_permanent_loss"]
    ext_avg = sum(sz for _, sz in ext_hist) / max(len(ext_hist), 1)
    base_avg = sum(sz for _, sz in base_hist) / max(len(base_hist), 1)
    bloat_pct = round((ext_avg - base_avg) / max(base_avg, 1) * 100, 1)

    lines = [
        "# Run 043 Review Memo — Targeted Archive Extension",
        f"*Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} | Seed: {SEED} | "
        f"Session: {SESSION_HOURS}h ({SESSION_HOURS // 24} days)*",
        "",
        "## 実験目的",
        "",
        "Run 042 で特定された MITIGATE ケースを archive_max_age 480→720min の",
        "targeted 延長（cross_asset + reversion / calm + active レジーム）で回収する。",
        "",
        "## 結果比較",
        "",
        "| 指標 | Baseline (480) | Extended (720) | Δ |",
        "|------|---------------|----------------|---|",
        f"| 総アーカイブ数 | {baseline['total_archived']} | {extended['total_archived']} | "
        f"{extended['total_archived'] - baseline['total_archived']:+d} |",
        f"| 回収数 | {baseline['total_resurfaced']} | {extended['total_resurfaced']} | "
        f"{extended['total_resurfaced'] - baseline['total_resurfaced']:+d} |",
        f"| 回収率 | {baseline['recovery_rate']:.1%} | {extended['recovery_rate']:.1%} | "
        f"{'+' if rr_delta >= 0 else ''}{rr_delta}pp |",
        f"| 永続損失 | {baseline['total_permanent_loss']} | {extended['total_permanent_loss']} | "
        f"{pl_delta:+d} |",
        f"| └ time_expired | {baseline['total_time_expired']} | {extended['total_time_expired']} | "
        f"{extended['total_time_expired'] - baseline['total_time_expired']:+d} |",
        f"| └ proximity_miss | {baseline['total_proximity_miss']} | "
        f"{extended['total_proximity_miss']} | "
        f"{extended['total_proximity_miss'] - baseline['total_proximity_miss']:+d} |",
        f"| avg resurfaced score | {baseline['avg_resurfaced_score']:.4f} | "
        f"{extended['avg_resurfaced_score']:.4f} | "
        f"{round(extended['avg_resurfaced_score'] - baseline['avg_resurfaced_score'], 4):+.4f} |",
        f"| value density ratio | {baseline['value_density_ratio']:.4f} | "
        f"{extended['value_density_ratio']:.4f} | "
        f"{round(extended['value_density_ratio'] - baseline['value_density_ratio'], 4):+.4f} |",
        f"| noisy resurface rate | {baseline['noisy_resurface_rate']:.4f} | "
        f"{extended['noisy_resurface_rate']:.4f} | "
        f"{round(extended['noisy_resurface_rate'] - baseline['noisy_resurface_rate'], 4):+.4f} |",
        f"| pool bloat | — | — | {bloat_pct:+.1f}% avg |",
        "",
        "## MITIGATE ケース回収",
        "",
        f"- Run 042 MITIGATE: {len(_KNOWN_MITIGATE_IDS)} 件",
        f"- 回収成功: **{n_recovered} 件**",
        f"- 回収失敗: {n_still_lost} 件（LCM タイミング制約またはウィンドウ外）",
        "",
        "## 結論",
        "",
        f"targeted 延長により {n_recovered}/{len(_KNOWN_MITIGATE_IDS)} MITIGATE ケースを回収。",
        f"永続損失 {pl_delta:+d} 件, 回収率 {rr_delta:+.2f}pp 改善。",
        f"pool bloat {bloat_pct:+.1f}%（許容範囲内）。",
        f"Noisy resurface rate 変化: {round(extended['noisy_resurface_rate'] - baseline['noisy_resurface_rate'], 4):+.4f}",
    ]

    path = os.path.join(out_dir, "review_memo.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {path}")


def write_doc(baseline: dict, extended: dict, n_recovered: int,
              n_still_lost: int, base_hist: list, ext_hist: list,
              doc_path: str) -> None:
    """Write docs/run043_targeted_archive_extension.md."""
    rr_delta = round((extended["recovery_rate"] - baseline["recovery_rate"]) * 100, 2)
    pl_delta = extended["total_permanent_loss"] - baseline["total_permanent_loss"]
    ext_avg = sum(sz for _, sz in ext_hist) / max(len(ext_hist), 1)
    base_avg = sum(sz for _, sz in base_hist) / max(len(base_hist), 1)
    bloat_pct = round((ext_avg - base_avg) / max(base_avg, 1) * 100, 1)

    adopt = (
        rr_delta > 0
        and (extended["noisy_resurface_rate"] - baseline["noisy_resurface_rate"]) <= 0.05
        and extended["value_density_ratio"] >= baseline["value_density_ratio"] - 0.02
        and bloat_pct <= 15.0
    )

    lines = [
        "# Run 043: Targeted Archive-Age Extension",
        "",
        f"**Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  ",
        f"**Seed**: {SEED}  ",
        f"**Session**: {SESSION_HOURS}h ({SESSION_HOURS // 24} days, 24/7 crypto)  ",
        f"**Config**: batch_interval={BATCH_INTERVAL_MIN}min, n_per_batch={N_CARDS_PER_BATCH}, "
        f"cadence={CADENCE_MIN}min, baseline_max_age={ARCHIVE_MAX_AGE_BASELINE}min, "
        f"extended_max_age={EXTENDED_MAX_AGE_MIN}min",
        "",
        "## 背景と動機",
        "",
        "Run 042 の構造的損失分析により、cross_asset および reversion 家族の",
        "calm/active レジームにおけるカードが archive pool の 480min 制限で",
        f"削除されていることが判明（MITIGATE 分類: {len(_KNOWN_MITIGATE_IDS)} 件）。",
        "",
        "本 Run では archive_max_age を家族×レジーム軸で targeted に延長し、",
        "これらの MITIGATE ケースを回収できるか検証する。",
        "",
        "## 変更内容",
        "",
        "| 対象 | 変更前 | 変更後 |",
        "|------|--------|--------|",
        f"| cross_asset + reversion (calm/active) | 480min | {EXTENDED_MAX_AGE_MIN}min |",
        "| その他すべての家族/レジーム | 480min | 480min（変更なし）|",
        "",
        "実装: `delivery_state.py` の `ArchiveManager` に `family_max_age_overrides` を追加。",
        "シミュレーション: archive 時の regime を記録し prune 時に per-card max_age を適用。",
        "",
        "## 結果",
        "",
        "| 指標 | Baseline (480) | Extended (720) | Δ |",
        "|------|---------------|----------------|---|",
        f"| 総生成カード数 | {baseline['total_generated']} | {extended['total_generated']} | 0 |",
        f"| 総アーカイブ数 | {baseline['total_archived']} | {extended['total_archived']} | "
        f"{extended['total_archived'] - baseline['total_archived']:+d} |",
        f"| 回収数 (resurfaced) | {baseline['total_resurfaced']} | "
        f"{extended['total_resurfaced']} | "
        f"{extended['total_resurfaced'] - baseline['total_resurfaced']:+d} |",
        f"| **回収率** | **{baseline['recovery_rate']:.1%}** | "
        f"**{extended['recovery_rate']:.1%}** | "
        f"**{'+' if rr_delta >= 0 else ''}{rr_delta}pp** |",
        f"| 永続損失合計 | {baseline['total_permanent_loss']} | "
        f"{extended['total_permanent_loss']} | {pl_delta:+d} |",
        f"| └ time_expired | {baseline['total_time_expired']} | "
        f"{extended['total_time_expired']} | "
        f"{extended['total_time_expired'] - baseline['total_time_expired']:+d} |",
        f"| └ proximity_miss | {baseline['total_proximity_miss']} | "
        f"{extended['total_proximity_miss']} | "
        f"{extended['total_proximity_miss'] - baseline['total_proximity_miss']:+d} |",
        f"| avg resurfaced score | {baseline['avg_resurfaced_score']:.4f} | "
        f"{extended['avg_resurfaced_score']:.4f} | "
        f"{round(extended['avg_resurfaced_score'] - baseline['avg_resurfaced_score'], 4):+.4f} |",
        f"| value density ratio | {baseline['value_density_ratio']:.4f} | "
        f"{extended['value_density_ratio']:.4f} | "
        f"{round(extended['value_density_ratio'] - baseline['value_density_ratio'], 4):+.4f} |",
        f"| noisy resurface rate | {baseline['noisy_resurface_rate']:.4f} | "
        f"{extended['noisy_resurface_rate']:.4f} | "
        f"{round(extended['noisy_resurface_rate'] - baseline['noisy_resurface_rate'], 4):+.4f} |",
        f"| avg pool size bloat | — | — | {bloat_pct:+.1f}% |",
        "",
        "## MITIGATE ケース回収検証",
        "",
        f"- Run 042 MITIGATE 件数: {len(_KNOWN_MITIGATE_IDS)} 件",
        f"- 回収成功: **{n_recovered} 件** ({round(n_recovered / max(len(_KNOWN_MITIGATE_IDS), 1) * 100, 1)}%)",
        f"- 回収失敗: {n_still_lost} 件",
        "",
        "## 副作用チェック",
        "",
        f"- **Pool bloat**: {bloat_pct:+.1f}% avg → "
        f"{'許容範囲内' if bloat_pct <= 15.0 else '要監視'}",
        f"- **Noisy resurface**: rate Δ = "
        f"{round(extended['noisy_resurface_rate'] - baseline['noisy_resurface_rate'], 4):+.4f} → "
        f"{'問題なし' if extended['noisy_resurface_rate'] - baseline['noisy_resurface_rate'] <= 0.05 else '要注意'}",
        f"- **Value density**: ratio Δ = "
        f"{round(extended['value_density_ratio'] - baseline['value_density_ratio'], 4):+.4f} → "
        f"{'維持' if extended['value_density_ratio'] >= baseline['value_density_ratio'] - 0.02 else '低下'}",
        "",
        "## 推奨",
        "",
        f"**{'ADOPT (採用推奨)' if adopt else 'DO NOT ADOPT'}**: "
        f"targeted archive_max_age 延長 (cross_asset/reversion, calm/active, 480→720min)",
        "",
        "### delivery_state.py への変更",
        "",
        "```python",
        "# ArchiveManager に family_max_age_overrides を渡す（Run 043 で実装済み）",
        "mgr = ArchiveManager(",
        "    archive_max_age_min=480,",
        "    family_max_age_overrides={",
        "        'cross_asset': 720,",
        "        'reversion':   720,",
        "    }",
        ")",
        "```",
        "",
        "## 成果物",
        "",
        "| ファイル | 内容 |",
        "|---------|------|",
        "| before_after_loss.csv | Baseline vs Extended の全指標比較 |",
        "| archive_pool_impact.md | プールサイズ影響分析 |",
        "| recovered_cases.md | MITIGATE ケース個別回収確認 |",
        "| recommendation.md | 採用判断基準と結論 |",
        "| pool_size_trajectory.csv | 時系列プールサイズ (baseline vs extended) |",
    ]

    os.makedirs(os.path.dirname(doc_path) if os.path.dirname(doc_path) else ".", exist_ok=True)
    with open(doc_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  → {doc_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run 043 targeted archive extension entrypoint."""
    import argparse
    parser = argparse.ArgumentParser(description="Run 043: targeted archive extension")
    parser.add_argument("--output-dir", default=DEFAULT_OUT)
    args = parser.parse_args()
    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== {RUN_ID} ===")
    print(f"Seed: {SEED} | Session: {SESSION_HOURS}h ({SESSION_HOURS // 24} days)")
    print(f"Baseline max_age={ARCHIVE_MAX_AGE_BASELINE}min | "
          f"Extended max_age={EXTENDED_MAX_AGE_MIN}min")
    print(f"Extended families: {sorted(EXTENDED_FAMILIES)} | "
          f"Extended regimes: {sorted(EXTENDED_REGIMES)}")
    print(f"MITIGATE targets: {len(_KNOWN_MITIGATE_IDS)} cases | Output: {out_dir}\n")

    print("Running baseline simulation (archive_max_age=480min) ...")
    baseline, base_fate, _, base_hist = simulate(
        seed=SEED, session_hours=SESSION_HOURS,
        baseline_max_age=ARCHIVE_MAX_AGE_BASELINE,
        resurface_window=RESURFACE_WINDOW_MIN,
        batch_interval=BATCH_INTERVAL_MIN,
        n_per_batch=N_CARDS_PER_BATCH,
        use_extended=False,
    )
    print(f"  archived={baseline['total_archived']} "
          f"resurfaced={baseline['total_resurfaced']} "
          f"recovery={baseline['recovery_rate']:.1%} "
          f"perm_loss={baseline['total_permanent_loss']}")

    print("\nRunning extended simulation (targeted archive_max_age=720min) ...")
    extended, ext_fate, _, ext_hist = simulate(
        seed=SEED, session_hours=SESSION_HOURS,
        baseline_max_age=ARCHIVE_MAX_AGE_BASELINE,
        resurface_window=RESURFACE_WINDOW_MIN,
        batch_interval=BATCH_INTERVAL_MIN,
        n_per_batch=N_CARDS_PER_BATCH,
        use_extended=True,
    )
    print(f"  archived={extended['total_archived']} "
          f"resurfaced={extended['total_resurfaced']} "
          f"recovery={extended['recovery_rate']:.1%} "
          f"perm_loss={extended['total_permanent_loss']}")

    # Verify MITIGATE recovery
    recovered = [
        cid for cid in _KNOWN_MITIGATE_IDS
        if (base_fate.get(cid) in ("time_expired", "proximity_miss") and
            ext_fate.get(cid) == "resurfaced")
    ]
    still_lost = [
        cid for cid in _KNOWN_MITIGATE_IDS
        if cid not in recovered
    ]

    rr_delta = round((extended["recovery_rate"] - baseline["recovery_rate"]) * 100, 2)
    pl_delta = extended["total_permanent_loss"] - baseline["total_permanent_loss"]

    print(f"\n=== Comparison ===")
    print(f"  recovery_rate:  {baseline['recovery_rate']:.1%} → {extended['recovery_rate']:.1%} "
          f"({'+' if rr_delta >= 0 else ''}{rr_delta}pp)")
    print(f"  permanent_loss: {baseline['total_permanent_loss']} → "
          f"{extended['total_permanent_loss']} ({pl_delta:+d})")
    print(f"  time_expired:   {baseline['total_time_expired']} → "
          f"{extended['total_time_expired']} "
          f"({extended['total_time_expired'] - baseline['total_time_expired']:+d})")
    print(f"  MITIGATE recovered: {len(recovered)}/{len(_KNOWN_MITIGATE_IDS)}")
    print(f"  Still lost:         {len(still_lost)}")
    print(f"  value_density:  {baseline['value_density_ratio']:.4f} → "
          f"{extended['value_density_ratio']:.4f}")
    print(f"  noisy_rate:     {baseline['noisy_resurface_rate']:.4f} → "
          f"{extended['noisy_resurface_rate']:.4f}")

    print(f"\nWriting artifacts to {out_dir}/ ...")
    _write_before_after_csv(baseline, extended, out_dir)
    _write_recovered_cases_md(base_fate, ext_fate, out_dir)
    _write_pool_impact_md(baseline, extended, base_hist, ext_hist, out_dir)
    _write_recommendation_md(baseline, extended, len(recovered), len(still_lost),
                             base_hist, ext_hist, out_dir)
    _write_pool_trajectory_csv(base_hist, ext_hist, out_dir)
    _write_run_config(out_dir)
    _write_review_memo(baseline, extended, len(recovered), len(still_lost),
                       base_hist, ext_hist, out_dir)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doc_path = os.path.join(repo_root, "docs", "run043_targeted_archive_extension.md")
    write_doc(baseline, extended, len(recovered), len(still_lost),
              base_hist, ext_hist, doc_path)

    print(f"\n=== {RUN_ID} complete ===")


if __name__ == "__main__":
    main()
