"""Main experiment runner.

Conditions:
  C1 - single-op baseline: compose-only on biology KG
  C2 - multi-op pipeline: align -> union -> compose -> difference -> evaluate
  C3 - direct baseline placeholder (template-based)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Allow running as script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.eval.scorer import EvaluationRubric, ScoredHypothesis, evaluate
from src.kg.toy_data import build_biology_kg, build_chemistry_kg
from src.pipeline.operators import align, compose, difference, union


def run_condition_c1(seed_kg_name: str = "biology") -> list[ScoredHypothesis]:
    """C1: single-op baseline — compose-only on one KG."""
    from src.kg.toy_data import get_all_toy_kgs
    kg = get_all_toy_kgs()[seed_kg_name]
    candidates = compose(kg)
    rubric = EvaluationRubric()
    return evaluate(candidates, kg, rubric)


def run_condition_c2(
    kg1_name: str = "biology",
    kg2_name: str = "chemistry",
) -> list[ScoredHypothesis]:
    """C2: multi-op pipeline — align -> union -> compose -> difference -> evaluate."""
    from src.kg.toy_data import get_all_toy_kgs
    kgs = get_all_toy_kgs()
    kg1 = kgs[kg1_name]
    kg2 = kgs[kg2_name]

    # Step 1: align
    alignment = align(kg1, kg2, threshold=0.4)

    # Step 2: union
    merged_kg = union(kg1, kg2, alignment, name=f"union_{kg1_name}_{kg2_name}")

    # Step 3: compose on merged KG
    counter: list[int] = [0]
    candidates_merged = compose(merged_kg, _counter=counter)

    # Step 4: difference (kg1-unique nodes as additional seed)
    diff_kg = difference(kg1, kg2, alignment, name=f"diff_{kg1_name}_{kg2_name}")
    candidates_diff = compose(diff_kg, _counter=counter)

    all_candidates = candidates_merged + candidates_diff

    # Step 5: evaluate
    rubric = EvaluationRubric()
    return evaluate(all_candidates, merged_kg, rubric)


def run_condition_c3() -> list[ScoredHypothesis]:
    """C3: direct baseline placeholder — template-based hypothesis generation."""
    # Placeholder: returns empty list in v0
    return []


def summarize(scored: list[ScoredHypothesis], label: str) -> dict:
    """Compute summary statistics for scored hypotheses."""
    if not scored:
        return {
            "condition": label,
            "count": 0,
            "mean_total": 0.0,
            "mean_plausibility": 0.0,
            "mean_novelty": 0.0,
        }
    n = len(scored)
    return {
        "condition": label,
        "count": n,
        "mean_total": round(sum(s.total_score for s in scored) / n, 4),
        "mean_plausibility": round(sum(s.plausibility for s in scored) / n, 4),
        "mean_novelty": round(sum(s.novelty for s in scored) / n, 4),
        "mean_testability": round(sum(s.testability for s in scored) / n, 4),
        "mean_traceability": round(sum(s.traceability for s in scored) / n, 4),
        "top5": [s.to_dict() for s in scored[:5]],
    }


def main() -> dict:
    """Run all conditions and return results dict."""
    c1 = run_condition_c1()
    c2 = run_condition_c2()
    c3 = run_condition_c3()

    results = {
        "run_timestamp": datetime.now().isoformat(),
        "conditions": {
            "C1_single_op_baseline": summarize(c1, "C1"),
            "C2_multi_op_pipeline": summarize(c2, "C2"),
            "C3_direct_baseline": summarize(c3, "C3"),
        },
        "h1_preliminary": {
            "c1_mean_total": summarize(c1, "C1")["mean_total"],
            "c2_mean_total": summarize(c2, "C2")["mean_total"],
            "c2_better_than_c1": summarize(c2, "C2")["mean_total"]
            >= summarize(c1, "C1")["mean_total"] * 1.10,
        },
    }
    return results


if __name__ == "__main__":
    results = main()
    print(json.dumps(results, indent=2, ensure_ascii=False))
