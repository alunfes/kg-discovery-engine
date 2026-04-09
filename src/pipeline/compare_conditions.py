"""Compare all experimental conditions and print a summary table."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pipeline.run_experiment import main, summarize, run_condition_c1, run_condition_c2


def print_table(results: dict) -> None:
    """Print a comparison table to stdout."""
    conditions = results["conditions"]
    print("\n" + "=" * 70)
    print("KG Discovery Engine — Condition Comparison (Run 001)")
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

    # Cross-domain check (H3 preview)
    print("\nH3 preview — Cross-domain (bio+chem) vs Same-domain (bio+bio):")
    c2_cross = run_condition_c2("biology", "chemistry")
    c2_same = run_condition_c2("biology", "biology")
    cross_novelty = sum(s.novelty for s in c2_cross) / max(len(c2_cross), 1)
    same_novelty = sum(s.novelty for s in c2_same) / max(len(c2_same), 1)
    print(f"  Cross-domain novelty = {cross_novelty:.4f}")
    print(f"  Same-domain novelty  = {same_novelty:.4f}")
    h3_pass = cross_novelty >= same_novelty * 1.20
    print(f"  Result: {'PASS' if h3_pass else 'FAIL'}")


if __name__ == "__main__":
    results = main()
    print_table(results)
