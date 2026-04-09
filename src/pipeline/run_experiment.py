"""Main experiment runner.

Conditions:
  C1 - single-op baseline: compose-only on biology KG
  C2 - multi-op pipeline: align -> union -> compose -> difference -> evaluate
  C3 - direct baseline placeholder (template-based)

Run 003 additions:
  H2 - Noisy KG robustness: does the evaluator absorb noise from low-quality input?
  H4 - Provenance-aware scoring: does provenance_aware=True improve ranking quality?
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Allow running as script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.eval.scorer import EvaluationRubric, ScoredHypothesis, evaluate
from src.kg.toy_data import (
    build_bio_chem_bridge_kg,
    build_biology_kg,
    build_chemistry_kg,
    build_mixed_hop_kg,
    build_noisy_kg,
)
from src.pipeline.operators import align, compose, compose_cross_domain, difference, union


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

    alignment = align(kg1, kg2, threshold=0.4)
    merged_kg = union(kg1, kg2, alignment, name=f"union_{kg1_name}_{kg2_name}")

    counter: list[int] = [0]
    candidates_merged = compose(merged_kg, _counter=counter)

    diff_kg = difference(kg1, kg2, alignment, name=f"diff_{kg1_name}_{kg2_name}")
    candidates_diff = compose(diff_kg, _counter=counter)

    all_candidates = candidates_merged + candidates_diff
    rubric = EvaluationRubric()
    return evaluate(all_candidates, merged_kg, rubric)


def run_condition_c2_bridge() -> list[ScoredHypothesis]:
    """C2-bridge: multi-op pipeline on the explicit bio↔chem bridge KG (Run 003).

    Uses build_bio_chem_bridge_kg() which has cross-domain edges pre-wired,
    maximising the proportion of cross-domain hypotheses for H1 analysis.
    """
    bridge_kg = build_bio_chem_bridge_kg()
    candidates = compose(bridge_kg)
    rubric = EvaluationRubric()
    return evaluate(candidates, bridge_kg, rubric)


def run_condition_c3() -> list[ScoredHypothesis]:
    """C3: direct baseline placeholder — template-based hypothesis generation."""
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


# ---------------------------------------------------------------------------
# H2: Noisy KG robustness
# ---------------------------------------------------------------------------

def _mean_total(scored: list[ScoredHypothesis]) -> float:
    """Return mean total score across a list of scored hypotheses."""
    if not scored:
        return 0.0
    return sum(s.total_score for s in scored) / len(scored)


def run_h2_noise_robustness() -> dict:
    """H2: Evaluate whether the evaluator absorbs noise from low-quality KGs.

    Hypothesis: Even with 30% or 50% of edges removed, the evaluator's mean
    total score degrades by less than 20% compared to the clean KG.  This
    demonstrates that evaluation-layer strength matters more than perfect
    input data.

    Returns a dict with noise-level stats and a pass/fail verdict.
    """
    clean_kg = build_biology_kg()
    clean_candidates = compose(clean_kg)
    rubric = EvaluationRubric()
    clean_scored = evaluate(clean_candidates, clean_kg, rubric)
    clean_mean = _mean_total(clean_scored)

    noise_levels = {}
    for rate in (0.30, 0.50):
        noisy_kg = build_noisy_kg(noise_rate=rate, seed=42)
        noisy_candidates = compose(noisy_kg)
        noisy_scored = evaluate(noisy_candidates, noisy_kg, rubric)
        noisy_mean = _mean_total(noisy_scored)
        delta = noisy_mean - clean_mean
        degradation = abs(delta) / clean_mean if clean_mean > 0 else 0.0
        label = f"noise_{int(rate * 100)}pct"
        noise_levels[label] = {
            "noise_rate": rate,
            "candidate_count": len(noisy_scored),
            "mean_total": round(noisy_mean, 4),
            "delta_vs_clean": round(delta, 4),
            "degradation_ratio": round(degradation, 4),
        }

    # H2 passes if the 50% noise case degrades by less than 20%
    worst_degradation = max(v["degradation_ratio"] for v in noise_levels.values())
    h2_pass = worst_degradation < 0.20

    return {
        "clean_mean_total": round(clean_mean, 4),
        "clean_candidate_count": len(clean_scored),
        "noise_levels": noise_levels,
        "worst_degradation_ratio": round(worst_degradation, 4),
        "threshold": 0.20,
        "pass": h2_pass,
    }


# ---------------------------------------------------------------------------
# H4: Provenance-aware scoring
# ---------------------------------------------------------------------------

# Gold-standard ranking: manually curated top-10 hypothesis IDs by expected
# scientific quality (2-hop strong-relation paths rank highest).
# IDs are assigned by compose() counter and are deterministic.
_GOLD_STANDARD_TOP10_RELATIVE = [
    # These are expected to be near the top based on domain knowledge:
    # strong-relation 2-hop paths (inhibits/catalyzes/activates/produces/encodes)
    # We rank them by scientific plausibility, not by any computed score.
    "strong_2hop",
    "strong_2hop",
    "strong_2hop",
    "strong_2hop",
    "strong_2hop",
    "weak_3hop",
    "weak_3hop",
    "weak_3hop",
    "weak_3hop",
    "weak_3hop",
]


def _spearman_correlation(ranks_a: list[int], ranks_b: list[int]) -> float:
    """Compute Spearman rank correlation between two rank lists."""
    n = len(ranks_a)
    if n < 2:
        return 0.0
    d_sq = sum((a - b) ** 2 for a, b in zip(ranks_a, ranks_b))
    return 1.0 - (6.0 * d_sq) / (n * (n * n - 1))


def _provenance_hop_count(candidate) -> int:
    """Return the number of hops in a hypothesis provenance path."""
    path = candidate.provenance
    return max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0


def run_h4_provenance_aware() -> dict:
    """H4: provenance-aware evaluation improves ranking quality.

    Compares naive scoring (provenance_aware=False) against aware scoring
    (provenance_aware=True) using a gold-standard proxy: shorter provenance
    paths are scientifically preferable (more direct mechanistic evidence).

    Gold standard proxy: rank by (strong_relation_count DESC, hop_count ASC).
    H4 passes if spearman(aware_ranks, gold_ranks) > spearman(naive_ranks, gold_ranks).
    """
    from src.eval.scorer import _STRONG_RELATIONS  # noqa: PLC2701

    kg = build_biology_kg()
    candidates = compose(kg)

    if not candidates:
        return {"pass": False, "reason": "no candidates generated"}

    naive_rubric = EvaluationRubric(provenance_aware=False)
    aware_rubric = EvaluationRubric(provenance_aware=True)

    naive_scored = evaluate(candidates, kg, naive_rubric)
    aware_scored = evaluate(candidates, kg, aware_rubric)

    def _gold_key(cand) -> tuple:
        """Gold standard: prefer strong relations + short paths."""
        path = cand.provenance
        relations = path[1::2]
        strong_count = sum(1 for r in relations if r in _STRONG_RELATIONS)
        hops = _provenance_hop_count(cand)
        return (-strong_count, hops)

    sorted_by_gold = sorted(candidates, key=_gold_key)
    gold_rank = {c.id: i for i, c in enumerate(sorted_by_gold)}

    # Build rank lists aligned by candidate ID order
    cand_ids = [s.candidate.id for s in naive_scored]
    naive_ranks = list(range(len(cand_ids)))  # naive_scored is already sorted by score desc
    aware_id_to_rank = {s.candidate.id: i for i, s in enumerate(aware_scored)}
    aware_ranks = [aware_id_to_rank[cid] for cid in cand_ids]
    gold_ranks = [gold_rank[cid] for cid in cand_ids]

    spearman_naive = round(_spearman_correlation(naive_ranks, gold_ranks), 4)
    spearman_aware = round(_spearman_correlation(aware_ranks, gold_ranks), 4)

    h4_pass = spearman_aware > spearman_naive

    return {
        "candidate_count": len(candidates),
        "naive_mean_traceability": round(
            sum(s.traceability for s in naive_scored) / max(len(naive_scored), 1), 4
        ),
        "aware_mean_traceability": round(
            sum(s.traceability for s in aware_scored) / max(len(aware_scored), 1), 4
        ),
        "spearman_naive": spearman_naive,
        "spearman_aware": spearman_aware,
        "gold_proxy": "strong_relation_count_desc+hop_count_asc",
        "pass": h4_pass,
    }


# ---------------------------------------------------------------------------
# H3: Hypothesis-level cross-domain vs same-domain novelty
# ---------------------------------------------------------------------------

def _is_cross_domain_scored(scored_hyp: ScoredHypothesis, kg) -> bool:
    """Return True if the hypothesis spans different domains."""
    cand = scored_hyp.candidate
    src_node = kg.get_node(cand.subject_id)
    tgt_node = kg.get_node(cand.object_id)
    if src_node and tgt_node:
        return src_node.domain != tgt_node.domain
    # Fallback: parse from ID prefix
    subj_prefix = cand.subject_id.split(":")[0] if ":" in cand.subject_id else ""
    obj_prefix = cand.object_id.split(":")[0] if ":" in cand.object_id else ""
    return subj_prefix != obj_prefix and bool(subj_prefix) and bool(obj_prefix)


def evaluate_h3(c2_results: list[ScoredHypothesis], merged_kg) -> dict:
    """H3: cross-domain hypotheses have higher novelty than same-domain.

    Uses hypothesis-level comparison (Run 003 method), not condition-level average.
    """
    cross = [s for s in c2_results if _is_cross_domain_scored(s, merged_kg)]
    same = [s for s in c2_results if not _is_cross_domain_scored(s, merged_kg)]

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


# ---------------------------------------------------------------------------
# Run 004 additions
# ---------------------------------------------------------------------------

def run_condition_c2_xdomain(
    kg1_name: str = "biology",
    kg2_name: str = "chemistry",
) -> list[ScoredHypothesis]:
    """C2-xdomain: multi-op pipeline keeping only cross-domain candidates (Run 004).

    Same pipeline as C2 but compose_cross_domain() filters out same-domain
    hypotheses, isolating the cross-domain contribution for H1 analysis.
    """
    from src.kg.toy_data import get_all_toy_kgs
    kgs = get_all_toy_kgs()
    kg1, kg2 = kgs[kg1_name], kgs[kg2_name]
    alignment = align(kg1, kg2, threshold=0.4)
    merged_kg = union(kg1, kg2, alignment, name=f"union_{kg1_name}_{kg2_name}")
    counter: list[int] = [0]
    candidates = compose_cross_domain(merged_kg, _counter=counter)
    rubric = EvaluationRubric()
    return evaluate(candidates, merged_kg, rubric)


def run_h4_mixed_hop() -> dict:
    """H4: provenance-aware evaluation on a KG with mixed 2-hop and 3-hop paths.

    Uses build_mixed_hop_kg() which creates both short (2-hop same-domain)
    and long (3-hop cross-domain) hypotheses.

    Gold standard: shorter paths are preferable (hops ASC, then strong_count DESC).
    This is distinct from the Run 003 gold standard which prioritised strong_count.

    In naive mode, 3-hop cross-domain hypotheses outrank some 2-hop same-domain
    hypotheses (evidence_support + novelty bonus > plausibility penalty).
    In aware mode, the traceability penalty for 3-hop flips these to agree with gold.

    H4 passes if spearman(aware_ranks, gold) > spearman(naive_ranks, gold).
    """
    from src.eval.scorer import _STRONG_RELATIONS  # noqa: PLC2701

    kg = build_mixed_hop_kg()
    candidates = compose(kg, max_depth=5)  # max_depth=5 needed for 3-hop paths

    if not candidates:
        return {"pass": False, "reason": "no candidates generated"}

    naive_rubric = EvaluationRubric(provenance_aware=False)
    aware_rubric = EvaluationRubric(provenance_aware=True)

    naive_scored = evaluate(candidates, kg, naive_rubric)
    aware_scored = evaluate(candidates, kg, aware_rubric)

    def _gold_key(cand) -> tuple:
        """Gold standard: prefer shorter paths, then more strong relations."""
        path = cand.provenance
        relations = path[1::2]
        strong_count = sum(1 for r in relations if r in _STRONG_RELATIONS)
        hops = _provenance_hop_count(cand)
        return (hops, -strong_count)  # hops first: shorter = better

    sorted_by_gold = sorted(candidates, key=_gold_key)
    gold_rank = {c.id: i for i, c in enumerate(sorted_by_gold)}

    cand_ids = [s.candidate.id for s in naive_scored]
    naive_ranks = list(range(len(cand_ids)))
    aware_id_to_rank = {s.candidate.id: i for i, s in enumerate(aware_scored)}
    aware_ranks = [aware_id_to_rank[cid] for cid in cand_ids]
    gold_ranks = [gold_rank[cid] for cid in cand_ids]

    spearman_naive = round(_spearman_correlation(naive_ranks, gold_ranks), 4)
    spearman_aware = round(_spearman_correlation(aware_ranks, gold_ranks), 4)

    hop_dist = {}
    for c in candidates:
        h = _provenance_hop_count(c)
        hop_dist[h] = hop_dist.get(h, 0) + 1

    return {
        "candidate_count": len(candidates),
        "hop_distribution": hop_dist,
        "naive_mean_traceability": round(
            sum(s.traceability for s in naive_scored) / max(len(naive_scored), 1), 4
        ),
        "aware_mean_traceability": round(
            sum(s.traceability for s in aware_scored) / max(len(aware_scored), 1), 4
        ),
        "spearman_naive": spearman_naive,
        "spearman_aware": spearman_aware,
        "gold_proxy": "hop_count_asc+strong_relation_count_desc",
        "pass": spearman_aware > spearman_naive,
    }


def main() -> dict:
    """Run all conditions and return results dict."""
    from src.kg.toy_data import get_all_toy_kgs
    from src.pipeline.operators import align, union

    c1 = run_condition_c1()
    c2 = run_condition_c2()
    c3 = run_condition_c3()
    c2_bridge = run_condition_c2_bridge()
    c2_xdomain = run_condition_c2_xdomain()  # Run 004

    # Build merged KG for H3 domain lookup
    kgs = get_all_toy_kgs()
    alignment = align(kgs["biology"], kgs["chemistry"], threshold=0.4)
    merged_kg = union(
        kgs["biology"], kgs["chemistry"], alignment, name="union_biology_chemistry"
    )

    c1_summary = summarize(c1, "C1")
    c2_summary = summarize(c2, "C2")
    c2_bridge_summary = summarize(c2_bridge, "C2_bridge")
    c2_xdomain_summary = summarize(c2_xdomain, "C2_xdomain")  # Run 004

    h3_result = evaluate_h3(c2, merged_kg)
    h2_result = run_h2_noise_robustness()
    h4_result = run_h4_provenance_aware()
    h4_mixed_result = run_h4_mixed_hop()  # Run 004

    results = {
        "run_timestamp": datetime.now().isoformat(),
        "conditions": {
            "C1_single_op_baseline": c1_summary,
            "C2_multi_op_pipeline": c2_summary,
            "C2_bridge_cross_domain": c2_bridge_summary,
            "C2_xdomain_cross_only": c2_xdomain_summary,  # Run 004
            "C3_direct_baseline": summarize(c3, "C3"),
        },
        "h1_preliminary": {
            "c1_mean_total": c1_summary["mean_total"],
            "c2_mean_total": c2_summary["mean_total"],
            "c2_bridge_mean_total": c2_bridge_summary["mean_total"],
            "c2_xdomain_mean_total": c2_xdomain_summary["mean_total"],  # Run 004
            "c2_better_than_c1": c2_summary["mean_total"] >= c1_summary["mean_total"] * 1.10,
            "c2_xdomain_better_than_c1": (  # Run 004 strict cross-domain test
                c2_xdomain_summary["mean_total"] >= c1_summary["mean_total"] * 1.10
            ),
        },
        "h3_cross_domain_novelty": h3_result,
        "h2_noise_robustness": h2_result,
        "h4_provenance_aware": h4_result,
        "h4_mixed_hop": h4_mixed_result,  # Run 004 — meaningful H4 test
    }
    return results


if __name__ == "__main__":
    results = main()
    print(json.dumps(results, indent=2, ensure_ascii=False))
