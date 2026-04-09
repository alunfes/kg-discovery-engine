"""Compare all experimental conditions and print a summary table."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pipeline.run_experiment import (
    main,
    run_condition_c1,
    run_condition_c2,
    summarize,
)


def evaluate_h3_hypothesis_level(c2_results: list) -> dict:
    """Evaluate H3 at the hypothesis level (cross vs same domain).

    Compares mean novelty of cross-domain hypotheses directly against
    mean novelty of same-domain hypotheses within the same C2 run.
    This avoids conflation from mixed-type condition averages.
    """
    cross = [s for s in c2_results if _is_cross_domain(s)]
    same = [s for s in c2_results if not _is_cross_domain(s)]

    cross_novelty = sum(s.novelty for s in cross) / max(len(cross), 1)
    same_novelty = sum(s.novelty for s in same) / max(len(same), 1)

    ratio = cross_novelty / same_novelty if same_novelty > 0 else 0.0
    h3_pass = ratio >= 1.20

    return {
        "method": "hypothesis_level",
        "cross_domain_count": len(cross),
        "same_domain_count": len(same),
        "cross_domain_novelty": round(cross_novelty, 4),
        "same_domain_novelty": round(same_novelty, 4),
        "ratio": round(ratio, 4),
        "threshold": 1.20,
        "pass": h3_pass,
    }


def _is_cross_domain(scored_hyp: object) -> bool:
    """Return True if the hypothesis spans two different domains."""
    cand = scored_hyp.candidate
    subj_domain = getattr(cand, "subject_domain", None)
    obj_domain = getattr(cand, "object_domain", None)
    if subj_domain is not None and obj_domain is not None:
        return subj_domain != obj_domain
    # Fallback: parse domain from subject/object IDs (e.g. "bio:protein_A")
    subj_prefix = cand.subject_id.split(":")[0] if ":" in cand.subject_id else ""
    obj_prefix = cand.object_id.split(":")[0] if ":" in cand.object_id else ""
    return subj_prefix != obj_prefix and bool(subj_prefix) and bool(obj_prefix)


def print_table(results: dict) -> None:
    """Print a comparison table to stdout."""
    conditions = results["conditions"]
    print("\n" + "=" * 70)
    print("KG Discovery Engine — Condition Comparison (Run 003)")
    print("=" * 70)

    header = f"{'Condition':<30} {'N':>5} {'Total':>8} {'Plaus':>8} {'Novel':>8}"
    print(header)
    print("-" * 70)

    for key, stats in conditions.items():
        row = (
            f"{stats['condition']:<30} "
            f"{stats['count']:>5} "
            f"{stats.get('mean_total', 0):>8.4f} "
            f"{stats.get('mean_plausibility', 0):>8.4f} "
            f"{stats.get('mean_novelty', 0):>8.4f}"
        )
        print(row)

    print("=" * 70)

    # H1 check
    h1 = results["h1_preliminary"]
    print(f"\nH1 check — C2 ≥ C1 × 1.10:")
    print(f"  C1 mean total = {h1['c1_mean_total']:.4f}")
    print(f"  C2 mean total = {h1['c2_mean_total']:.4f}")
    verdict = "PASS" if h1["c2_better_than_c1"] else "FAIL"
    print(f"  Result: {verdict}")

    # H3 — hypothesis-level comparison (Run 003 method)
    print("\nH3 — Hypothesis-level: cross-domain novelty vs same-domain novelty:")
    c2_results = run_condition_c2("biology", "chemistry")
    h3 = evaluate_h3_hypothesis_level(c2_results)
    print(f"  Cross-domain hypotheses: {h3['cross_domain_count']} (novelty={h3['cross_domain_novelty']:.4f})")
    print(f"  Same-domain hypotheses:  {h3['same_domain_count']} (novelty={h3['same_domain_novelty']:.4f})")
    print(f"  Ratio: {h3['ratio']:.4f} (threshold: {h3['threshold']})")
    print(f"  Result: {'PASS' if h3['pass'] else 'FAIL'}")

    # H3 — legacy condition-level comparison (for reference)
    print("\nH3 legacy — Condition-level (bio+chem) vs (bio+bio):")
    c2_same_cond = run_condition_c2("biology", "biology")
    cross_cond_novelty = sum(s.novelty for s in c2_results) / max(len(c2_results), 1)
    same_cond_novelty = sum(s.novelty for s in c2_same_cond) / max(len(c2_same_cond), 1)
    h3_legacy = cross_cond_novelty >= same_cond_novelty * 1.20
    print(f"  bio+chem novelty = {cross_cond_novelty:.4f}")
    print(f"  bio+bio novelty  = {same_cond_novelty:.4f}")
    print(f"  Result: {'PASS' if h3_legacy else 'FAIL'} (legacy method, for reference only)")

    # H2 check
    if "h2_noise_robustness" in results:
        h2 = results["h2_noise_robustness"]
        print("\nH2 check — Noisy KG degradation:")
        for label, stats in h2["noise_levels"].items():
            print(f"  {label}: mean_total={stats['mean_total']:.4f} (Δ={stats['delta_vs_clean']:+.4f})")
        print(f"  Result: {'PASS' if h2['pass'] else 'FAIL'} — evaluator absorbs noise")

    # H4 check
    if "h4_provenance_aware" in results:
        h4 = results["h4_provenance_aware"]
        print("\nH4 check — Provenance-aware scoring:")
        print(f"  Naive traceability:    {h4['naive_mean_traceability']:.4f}")
        print(f"  Aware traceability:    {h4['aware_mean_traceability']:.4f}")
        print(f"  Spearman correlation (aware vs gold): {h4.get('spearman_aware', 'N/A')}")
        print(f"  Spearman correlation (naive vs gold): {h4.get('spearman_naive', 'N/A')}")
        print(f"  Result: {'PASS' if h4['pass'] else 'FAIL'}")


if __name__ == "__main__":
    results = main()
    print_table(results)
