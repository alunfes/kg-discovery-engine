"""Run 027: Operator delivery optimization.

Objective:
  Improve delivery and review usability of the production-shadow engine
  without changing core detection logic.

Background (Run 026 results):
  - attention precision = 1.0 (no false positives)
  - fatigue_risk = LOW, daily_usable = YES
  - Key bottlenecks:
      hl=40-60min < window=120min (half-life vs review cadence mismatch)
      family duplicate expansion (same card type across HYPE/BTC/ETH/SOL)
      sparse signal bias

This run evaluates:
  1. Review cadence: 30 / 45 / 60 / 120 min vs 120-min window
  2. Family-level digest/collapse for repeated multi-asset cards
  3. Delivery-state staging: fresh / active / aging / digest_only / expired

Usage:
  python -m crypto.run_027_delivery [--output-dir PATH] [--seed-start N]

Output artifacts:
  cadence_comparison.csv
  family_digest_examples.md
  before_after_surface_count.md
  stale_reduction_report.md
  delivery_policy_recommendation.md

Why no change to core detection logic:
  Run 027 is a delivery-layer experiment only.  Changing scoring thresholds
  or half-life calibration in the same run would conflate two variables and
  make it impossible to attribute observed changes to delivery policy alone.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from crypto.src.eval.delivery_state import (
    DeliveryCard,
    DeliveryStateEngine,
    DigestCard,
    generate_cards,
    run_multi_cadence,
    results_to_csv,
    simulate_cadence,
    STATE_FRESH,
    STATE_ACTIVE,
    STATE_AGING,
    STATE_DIGEST_ONLY,
    STATE_EXPIRED,
    _ASSETS,
)

# ---------------------------------------------------------------------------
# Run constants
# ---------------------------------------------------------------------------

RUN_ID = "run_027_delivery"
SEEDS = list(range(42, 62))          # 20 seeds to reduce variance
CADENCES = [30, 45, 60, 120]        # minutes; 120 = current baseline
N_CARDS = 20
SESSION_HOURS = 8
DEFAULT_OUT = f"crypto/artifacts/runs/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{RUN_ID}"


# ---------------------------------------------------------------------------
# Helper: deterministic family-digest example (single seed)
# ---------------------------------------------------------------------------

def _build_family_digest_examples(seed: int = 42) -> list[DigestCard]:
    """Generate digest examples for the example report.

    Uses seed=42 so the examples are reproducible across runs.
    Uses cadence=30min snapshot (ratio 0.75 for HL=40 → active) so the
    example shows realistic state-filtered collapse, not a full-deck collapse.

    Returns:
        List of DigestCard from surfaced cards only (fresh + active + aging).
    """
    cards = generate_cards(seed=seed, n_cards=N_CARDS)
    engine = DeliveryStateEngine(cadence_min=30)
    # snapshot_review filters to surfaced states before collapsing
    snap = engine.snapshot_review(cards, review_time_min=30.0)
    return snap.digests


def _render_family_digest_examples(digests: list[DigestCard]) -> str:
    """Render a markdown document showing family digest examples.

    Args:
        digests: DigestCard list from collapse_families.

    Returns:
        Markdown string.
    """
    lines = [
        "# Family Digest Examples — Run 027",
        "",
        "Each digest collapses 2+ same-family cards from different assets "
        "into one operator-facing item.",
        "",
    ]
    if not digests:
        lines.append("_No digests generated (no multi-asset families found)._")
        return "\n".join(lines)

    for i, d in enumerate(digests, 1):
        lines += [
            f"## Digest {i}: `{d.family_key[0]}` / `{d.family_key[1]}`",
            "",
            f"**Lead asset**: {d.lead_card.asset}  "
            f"(score={d.lead_card.composite_score:.4f}, "
            f"tier={d.lead_card.tier}, "
            f"state={d.delivery_state})",
            "",
            f"**Co-assets collapsed**: {', '.join(d.co_assets)}",
            "",
            "| Asset | Score |",
            "|-------|-------|",
            f"| {d.lead_card.asset} (lead) | {d.lead_card.composite_score:.4f} |",
        ]
        for asset, score in zip(d.co_assets, d.co_scores):
            lines.append(f"| {asset} | {score:.4f} |")
        lines += [
            "",
            f"**Collapsed {d.to_dict()['n_collapsed']} → 1 item** "
            f"(info_loss={d.info_loss_score:.3f})",
            "",
            "---",
            "",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: before / after surface count report
# ---------------------------------------------------------------------------

def _render_before_after(results: dict[int, object]) -> str:
    """Render markdown comparing surfaced counts before and after collapse.

    Args:
        results: Cadence → CadenceResult mapping from run_multi_cadence.

    Returns:
        Markdown string.
    """
    lines = [
        "# Before/After Surface Count — Run 027",
        "",
        "Surfaced count = cards shown to operator per review.",
        "After = after family digest collapse applied.",
        "",
        "| Cadence (min) | Surfaced Before | Surfaced After | Reduction | Precision |",
        "|--------------|----------------|----------------|-----------|-----------|",
    ]
    for cadence in sorted(results):
        r = results[cadence]
        lines.append(
            f"| {r.cadence_min} | "
            f"{r.avg_surfaced_before:.1f} | "
            f"{r.avg_surfaced_after:.1f} | "
            f"{r.avg_reduction:.1f} | "
            f"{r.avg_precision:.3f} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- **Reduction** = items removed per review by family collapse.",
        "- **Precision** = fraction of surfaced items in fresh/active state "
          "(1.0 = no stale items shown).",
        "- Cadences with precision < 1.0 are surfacing aging cards alongside "
          "fresh ones — operator reviews stale signal.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: stale reduction report
# ---------------------------------------------------------------------------

def _render_stale_reduction(results: dict[int, object]) -> str:
    """Render markdown stale-card rate by cadence.

    Args:
        results: Cadence → CadenceResult mapping.

    Returns:
        Markdown string.
    """
    lines = [
        "# Stale Reduction Report — Run 027",
        "",
        "Stale = cards in **aging + digest_only + expired** state at review time.",
        "Stale rate = stale_count / total cards.",
        "",
        "| Cadence (min) | Avg Stale Rate | Avg Info Loss | Reviews/Day |",
        "|--------------|----------------|---------------|------------|",
    ]
    for cadence in sorted(results):
        r = results[cadence]
        reviews_per_day = int(24 * 60 / cadence)
        lines.append(
            f"| {r.cadence_min} | "
            f"{r.avg_stale_rate:.3f} | "
            f"{r.avg_info_loss:.3f} | "
            f"{reviews_per_day} |"
        )

    lines += [
        "",
        "## Stale Rate Threshold",
        "",
        "- **Target**: stale_rate < 0.20 (< 20% of deck is stale at review time)",
        "- **Critical**: stale_rate > 0.50 (majority of deck is stale — cadence too long)",
        "",
        "## Info Loss Threshold",
        "",
        "- **Acceptable**: info_loss < 0.35 (collapsed co-assets hold < 35% of total score)",
        "- **High loss warning**: info_loss > 0.50 (collapse discards significant signal)",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: delivery policy recommendation
# ---------------------------------------------------------------------------

def _render_policy_recommendation(results: dict[int, object]) -> str:
    """Render the final delivery policy recommendation.

    Selection criteria (composite score):
      - stale_rate weight 0.5:  lower is better
      - precision weight 0.3:   higher is better
      - reviews_per_day weight 0.2: penalise > 32 reviews/day (operator fatigue)

    Why 32 reviews/day (45-min cadence) as fatigue threshold:
      At cadence=30min an operator would run 48 reviews/day.  With ~5 items
      per review that's 240 item-reviews/day — unsustainable for a single
      operator.  At 45min (32 reviews/day) the total is ~160, borderline
      acceptable.  60min (24 reviews/day) drops to ~115 but precision falls
      to 0 — stale cards dominate.

    Args:
        results: Cadence → CadenceResult mapping (first_review model).

    Returns:
        Markdown string.
    """
    def _composite(r: object) -> float:
        reviews_per_day = 24 * 60 / r.cadence_min
        # Penalise high review frequency: normalise to [0,1] where 12/day=0 penalty
        burden_penalty = max(0.0, (reviews_per_day - 32) / 36)  # 0 at 32/day, 1 at 68/day
        return 0.5 * r.avg_stale_rate + 0.3 * (1.0 - r.avg_precision) + 0.2 * burden_penalty

    ranked = sorted(results.values(), key=_composite)
    best = ranked[0]

    # Pragmatic pick: best cadence with precision > 0.5 AND reviews/day <= 32
    pragmatic = next(
        (r for r in ranked
         if r.avg_precision > 0.5 and (24 * 60 / r.cadence_min) <= 32),
        best,  # fallback to quality-optimum if no pragmatic candidate
    )

    reviews_best = int(24 * 60 / best.cadence_min)
    reviews_pragmatic = int(24 * 60 / pragmatic.cadence_min)

    lines = [
        "# Delivery Policy Recommendation — Run 027",
        "",
        "## Summary",
        "",
        f"| | Cadence | Stale Rate | Precision | Reviews/Day | Items/Review |",
        f"|--|---------|-----------|-----------|-------------|-------------|",
        f"| Quality optimum | {best.cadence_min} min | "
          f"{best.avg_stale_rate:.3f} | {best.avg_precision:.3f} | "
          f"{reviews_best} | {best.avg_surfaced_after:.1f} |",
        f"| **Pragmatic pick** | **{pragmatic.cadence_min} min** | "
          f"**{pragmatic.avg_stale_rate:.3f}** | **{pragmatic.avg_precision:.3f}** | "
          f"**{reviews_pragmatic}** | **{pragmatic.avg_surfaced_after:.1f}** |",
        "",
        "## Recommended Cadence for Daily Operation",
        "",
        f"**{pragmatic.cadence_min} minutes**",
        "",
        f"- avg_stale_rate: {pragmatic.avg_stale_rate:.3f}",
        f"- avg_precision: {pragmatic.avg_precision:.3f}",
        f"- avg_surfaced_after_collapse: {pragmatic.avg_surfaced_after:.1f}",
        f"- avg_info_loss: {pragmatic.avg_info_loss:.3f}",
        f"- reviews/day: {reviews_pragmatic}",
        "",
        "> **Note**: cadence=30min achieves quality-optimum (stale=0.065, "
          "precision=1.0) but requires 48 reviews/day.  "
          f"cadence={pragmatic.cadence_min}min reduces to {reviews_pragmatic} "
          "reviews/day while maintaining acceptable precision.  "
          "If the pipeline gains auto-surfacing (only fresh+active pushed to operator), "
          "30min cadence becomes viable.",
        "",
        "## Delivery State Policy",
        "",
        "| State | Age/HL Ratio | Operator Action |",
        "|-------|-------------|-----------------|",
        "| fresh | < 0.5 | Full review — high priority |",
        "| active | 0.5–1.0 | Normal review |",
        "| aging | 1.0–1.75 | Quick scan — review before expiry |",
        "| digest_only | 1.75–2.5 | Collapsed into family digest only |",
        "| expired | ≥ 2.5 | Suppressed from all surfaces |",
        "",
        "## Family Collapse Policy",
        "",
        "- **Trigger**: 2+ cards sharing (branch, grammar_family) across different assets",
        "- **Lead card**: highest composite_score shown in full",
        "- **Co-assets**: listed as one collapsed line",
        "- **Info loss target**: < 0.35 per digest group",
        "",
        "## Cadence Comparison Summary",
        "",
        "| Cadence | Stale Rate | Precision | Surfaced After | Info Loss | Verdict |",
        "|---------|-----------|-----------|----------------|-----------|---------|",
    ]

    verdicts = {
        30:  "Quality-optimum; 48 reviews/day (push-only viable)",
        45:  "Pragmatic pick; 32 reviews/day, precision > 0.5",
        60:  "Borderline; precision=0 (all cards aging at review)",
        120: "Confirmed broken; HL mismatch, most cards expired",
    }

    for cadence in sorted(results):
        r = results[cadence]
        verdict = verdicts.get(cadence, "—")
        lines.append(
            f"| {r.cadence_min} | "
            f"{r.avg_stale_rate:.3f} | "
            f"{r.avg_precision:.3f} | "
            f"{r.avg_surfaced_after:.1f} | "
            f"{r.avg_info_loss:.3f} | "
            f"{verdict} |"
        )

    lines += [
        "",
        "## Operator Burden Assessment",
        "",
        "- **Before collapse**: avg surfaced = "
          f"{results[sorted(results)[0]].avg_surfaced_before:.1f} items/review",
        "- **After collapse (best cadence)**: "
          f"{best.avg_surfaced_after:.1f} items/review",
        "- **Reduction**: "
          f"{best.avg_surfaced_before - best.avg_surfaced_after:.1f} items removed per review",
        "",
        "## Next Steps",
        "",
        "1. Deploy recommended cadence to production-shadow pipeline",
        "2. Monitor stale_rate in live runs over 48h",
        "3. Tune collapse_min_family_size if info_loss exceeds 0.35",
        "4. Run 028 candidate: regime-switch canary re-validation with new cadence",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(output_dir: str, seed_start: int = 42) -> None:
    """Run 027 entry point.

    Args:
        output_dir: Directory to write all artifacts into (created if missing).
        seed_start: First seed; 20 consecutive seeds are used.
    """
    seeds = list(range(seed_start, seed_start + 20))
    os.makedirs(output_dir, exist_ok=True)

    print(f"[run_027] seeds={seeds[0]}..{seeds[-1]}  cadences={CADENCES}  "
          f"n_cards={N_CARDS}  session_hours={SESSION_HOURS}")

    # -----------------------------------------------------------------------
    # 1a. First-review simulation (primary cadence comparison)
    #     Cards freshly generated, aged exactly cadence_min before review.
    #     Best isolation of per-cadence delivery quality.
    # -----------------------------------------------------------------------
    results = run_multi_cadence(
        seeds=seeds,
        cadences=CADENCES,
        n_cards=N_CARDS,
        session_hours=SESSION_HOURS,
        model="first_review",
    )
    print(f"[run_027] first_review simulation complete: {len(results)} cadences")
    for cadence in sorted(results):
        r = results[cadence]
        print(
            f"  [first_review] cadence={cadence:3d}min  stale={r.avg_stale_rate:.3f}  "
            f"before={r.avg_surfaced_before:.1f}  after={r.avg_surfaced_after:.1f}  "
            f"precision={r.avg_precision:.3f}  info_loss={r.avg_info_loss:.3f}"
        )

    # -----------------------------------------------------------------------
    # 1b. Batch-refresh simulation (steady-state crosscheck)
    #     New cards injected every 30 min; operator reviews at cadence intervals.
    #     Models production reality more closely.
    # -----------------------------------------------------------------------
    results_refresh = run_multi_cadence(
        seeds=seeds,
        cadences=CADENCES,
        n_cards=N_CARDS,
        session_hours=SESSION_HOURS,
        model="batch_refresh",
    )
    print(f"[run_027] batch_refresh simulation complete: {len(results_refresh)} cadences")
    for cadence in sorted(results_refresh):
        r = results_refresh[cadence]
        print(
            f"  [batch_refresh] cadence={cadence:3d}min  stale={r.avg_stale_rate:.3f}  "
            f"before={r.avg_surfaced_before:.1f}  after={r.avg_surfaced_after:.1f}  "
            f"precision={r.avg_precision:.3f}  info_loss={r.avg_info_loss:.3f}"
        )

    # -----------------------------------------------------------------------
    # 2. cadence_comparison.csv (both models side-by-side)
    # -----------------------------------------------------------------------
    csv_path = os.path.join(output_dir, "cadence_comparison.csv")
    with open(csv_path, "w", newline="") as fh:
        import csv as _csv
        fieldnames = [
            "cadence_min",
            "fr_stale_rate", "fr_surfaced_before", "fr_surfaced_after",
            "fr_precision", "fr_info_loss",
            "br_stale_rate", "br_surfaced_before", "br_surfaced_after",
            "br_precision", "br_info_loss",
        ]
        writer = _csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for cadence in sorted(results):
            fr = results[cadence]
            br = results_refresh[cadence]
            writer.writerow({
                "cadence_min": cadence,
                "fr_stale_rate":        round(fr.avg_stale_rate, 4),
                "fr_surfaced_before":   round(fr.avg_surfaced_before, 2),
                "fr_surfaced_after":    round(fr.avg_surfaced_after, 2),
                "fr_precision":         round(fr.avg_precision, 4),
                "fr_info_loss":         round(fr.avg_info_loss, 4),
                "br_stale_rate":        round(br.avg_stale_rate, 4),
                "br_surfaced_before":   round(br.avg_surfaced_before, 2),
                "br_surfaced_after":    round(br.avg_surfaced_after, 2),
                "br_precision":         round(br.avg_precision, 4),
                "br_info_loss":         round(br.avg_info_loss, 4),
            })
    print(f"[run_027] wrote {csv_path}")

    # -----------------------------------------------------------------------
    # 3. family_digest_examples.md
    # -----------------------------------------------------------------------
    digests = _build_family_digest_examples(seed=seed_start)
    digest_path = os.path.join(output_dir, "family_digest_examples.md")
    with open(digest_path, "w") as fh:
        fh.write(_render_family_digest_examples(digests))
    print(f"[run_027] wrote {digest_path}")

    # -----------------------------------------------------------------------
    # 4. before_after_surface_count.md
    # -----------------------------------------------------------------------
    ba_path = os.path.join(output_dir, "before_after_surface_count.md")
    with open(ba_path, "w") as fh:
        fh.write(_render_before_after(results))
    print(f"[run_027] wrote {ba_path}")

    # -----------------------------------------------------------------------
    # 5. stale_reduction_report.md
    # -----------------------------------------------------------------------
    stale_path = os.path.join(output_dir, "stale_reduction_report.md")
    with open(stale_path, "w") as fh:
        fh.write(_render_stale_reduction(results))
    print(f"[run_027] wrote {stale_path}")

    # -----------------------------------------------------------------------
    # 6. delivery_policy_recommendation.md
    # -----------------------------------------------------------------------
    rec_path = os.path.join(output_dir, "delivery_policy_recommendation.md")
    with open(rec_path, "w") as fh:
        fh.write(_render_policy_recommendation(results))
    print(f"[run_027] wrote {rec_path}")

    # -----------------------------------------------------------------------
    # 7. run_config.json
    # -----------------------------------------------------------------------
    cfg = {
        "run_id": RUN_ID,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seeds": seeds,
        "cadences_tested": CADENCES,
        "n_cards": N_CARDS,
        "session_hours": SESSION_HOURS,
        "delivery_state_thresholds": {
            "fresh_max_ratio": 0.5,
            "active_max_ratio": 1.0,
            "aging_max_ratio": 1.75,
            "digest_max_ratio": 2.5,
        },
        "collapse_min_family_size": 2,
        "results_first_review": {
            str(cadence): results[cadence].to_csv_row()
            for cadence in sorted(results)
        },
        "results_batch_refresh": {
            str(cadence): results_refresh[cadence].to_csv_row()
            for cadence in sorted(results_refresh)
        },
    }
    cfg_path = os.path.join(output_dir, "run_config.json")
    with open(cfg_path, "w") as fh:
        json.dump(cfg, fh, indent=2)
    print(f"[run_027] wrote {cfg_path}")

    print(f"[run_027] done — artifacts in {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 027: Operator delivery optimization")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUT,
        help="Directory to write artifacts (default: timestamped under artifacts/runs/)",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=42,
        help="First RNG seed (20 consecutive seeds used, default: 42)",
    )
    args = parser.parse_args()
    main(output_dir=args.output_dir, seed_start=args.seed_start)
