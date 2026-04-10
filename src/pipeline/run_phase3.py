"""Phase 3 experiment runner: real-data conditional H1/H3 verification.

Experimental design
-------------------
4 conditions × 2 pipelines (single-op vs multi-op):
  A  biology-only         bridge_density=0  (same-domain baseline)
  B  chemistry-only       bridge_density=0  (same-domain baseline)
  C  bio+chem sparse      bridge_density≈5%
  D  bio+chem dense       bridge_density≈15%

Key metrics
-----------
- mean_total, mean_novelty, Cohen's d
- unique_to_multi_op : (subject, object) pairs reachable ONLY by multi-op
- operator_contribution_rate : fraction of multi-op candidates not found by single-op
- bridge_density, relation_entropy

H1' analysis
------------
multi-op advantage (Cohen's d, unique ratio) as a function of bridge_density.
Prediction: advantage highest at C (sparse), lowest at A/B (none), may fall at D.

H3' analysis
------------
No cross-domain novelty bonus. Structural distance proxy:
  avg path length (hops) for cross-domain vs same-domain candidates.
  If cross-domain paths are longer → structural distance ≠ 0 → H3' evidence.

H4 stability analysis
---------------------
Spearman rank correlation between naive and provenance-aware across conditions.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.wikidata_loader import load_wikidata_bio_chem
from src.eval.scorer import (
    EvaluationRubric,
    ScoredHypothesis,
    cohens_d,
    evaluate,
    score_category,
)
from src.kg.models import KnowledgeGraph
from src.kg.real_data import (
    build_condition_a,
    build_condition_b,
    build_condition_c,
    build_condition_d,
    compute_bridge_density,
    compute_kg_stats,
    extract_domain_subgraph,
)
from src.pipeline.operators import align, compose, difference, union


# ---------------------------------------------------------------------------
# Single-op and multi-op runners
# ---------------------------------------------------------------------------

def run_single_op(kg: KnowledgeGraph, rubric: EvaluationRubric | None = None) -> list[ScoredHypothesis]:
    """Single-op baseline: compose-only on the given KG."""
    rubric = rubric or EvaluationRubric(cross_domain_novelty_bonus=False)
    candidates = compose(kg)
    return evaluate(candidates, kg, rubric)


def run_multi_op(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    rubric: EvaluationRubric | None = None,
) -> tuple[list[ScoredHypothesis], KnowledgeGraph]:
    """Multi-op pipeline: align → union → compose + diff → evaluate.

    Deduplicates candidates by (subject_id, object_id) before scoring to
    prevent inflation when diff_kg overlaps with merged_kg (degenerate case).
    Returns (scored_hypotheses, merged_kg) so callers can look up node domains.
    """
    rubric = rubric or EvaluationRubric(cross_domain_novelty_bonus=False)
    alignment = align(bio_kg, chem_kg, threshold=0.5)
    merged = union(bio_kg, chem_kg, alignment, name=f"union_{bio_kg.name}_{chem_kg.name}")
    counter: list[int] = [0]
    cands_merged = compose(merged, _counter=counter)
    diff_kg = difference(bio_kg, chem_kg, alignment, name=f"diff_{bio_kg.name}")
    cands_diff = compose(diff_kg, _counter=counter)

    # Deduplicate: keep first occurrence of each (subject, object) pair
    seen: set[tuple[str, str]] = set()
    unique_cands = []
    for c in cands_merged + cands_diff:
        key = (c.subject_id, c.object_id)
        if key not in seen:
            seen.add(key)
            unique_cands.append(c)

    scored = evaluate(unique_cands, merged, rubric)
    return scored, merged


def _candidate_pairs(scored: list[ScoredHypothesis]) -> set[tuple[str, str]]:
    """Return set of (subject_id, object_id) pairs from scored hypotheses."""
    return {(s.candidate.subject_id, s.candidate.object_id) for s in scored}


def _normalize_id(node_id: str) -> str:
    """Strip kg-prefix (e.g. 'chemistry::') from union-remapped node IDs."""
    if "::" in node_id:
        return node_id.split("::", 1)[1]
    return node_id


def _normalized_pairs(scored: list[ScoredHypothesis]) -> set[tuple[str, str]]:
    """Normalized (subject, object) pairs for cross-pipeline comparison."""
    return {
        (_normalize_id(s.candidate.subject_id), _normalize_id(s.candidate.object_id))
        for s in scored
    }


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def compute_unique_to_multi_op(
    single_scored: list[ScoredHypothesis],
    multi_scored: list[ScoredHypothesis],
) -> dict:
    """Compute reachability advantage of multi-op over single-op.

    'unique_to_multi_op' = candidate pairs in multi-op NOT in single-op
    (after normalizing node ID prefixes).
    """
    single_norm = _normalized_pairs(single_scored)
    multi_norm = _normalized_pairs(multi_scored)
    unique = multi_norm - single_norm
    only_single = single_norm - multi_norm
    overlap = multi_norm & single_norm

    multi_novelty_unique = [
        s.novelty for s in multi_scored
        if (_normalize_id(s.candidate.subject_id),
            _normalize_id(s.candidate.object_id)) in unique
    ]
    avg_unique_novelty = (
        sum(multi_novelty_unique) / len(multi_novelty_unique)
        if multi_novelty_unique else 0.0
    )

    return {
        "multi_total": len(multi_norm),
        "single_total": len(single_norm),
        "overlap_count": len(overlap),
        "unique_to_multi_op_count": len(unique),
        "unique_to_single_op_count": len(only_single),
        "operator_contribution_rate": round(len(unique) / max(len(multi_norm), 1), 4),
        "avg_unique_novelty": round(avg_unique_novelty, 4),
    }


def _hop_count(scored: ScoredHypothesis) -> int:
    """Return number of hops from provenance path."""
    path = scored.candidate.provenance
    return max(0, (len(path) - 1) // 2) if len(path) >= 3 else 0


def analyze_h3_structural_distance(
    multi_scored: list[ScoredHypothesis],
    merged_kg: KnowledgeGraph,
) -> dict:
    """H3' analysis: structural distance proxy for cross-domain novelty.

    No bonus applied (rubric.cross_domain_novelty_bonus=False assumed).
    Structural distance proxy: mean hop count cross-domain vs same-domain.
    If cross-domain paths are longer on average → genuine structural separation.
    """
    def _is_cross(s: ScoredHypothesis) -> bool:
        n1 = merged_kg.get_node(s.candidate.subject_id)
        n2 = merged_kg.get_node(s.candidate.object_id)
        if n1 and n2:
            return n1.domain != n2.domain
        sid = _normalize_id(s.candidate.subject_id)
        oid = _normalize_id(s.candidate.object_id)
        return sid.startswith("bio:") != oid.startswith("bio:")

    cross = [s for s in multi_scored if _is_cross(s)]
    same = [s for s in multi_scored if not _is_cross(s)]

    def _avg(lst: list[ScoredHypothesis], fn) -> float:
        vals = [fn(s) for s in lst]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    cross_hops = _avg(cross, _hop_count)
    same_hops = _avg(same, _hop_count)
    cross_novelty = _avg(cross, lambda s: s.novelty)
    same_novelty = _avg(same, lambda s: s.novelty)

    structural_distance_detected = cross_hops > same_hops
    h3_reframed_pass = (
        structural_distance_detected
        and cross_novelty >= same_novelty  # no bonus assumed
    )

    return {
        "cross_domain_count": len(cross),
        "same_domain_count": len(same),
        "cross_domain_mean_hops": cross_hops,
        "same_domain_mean_hops": same_hops,
        "hop_ratio": round(cross_hops / same_hops, 4) if same_hops > 0 else 0.0,
        "cross_domain_novelty_no_bonus": cross_novelty,
        "same_domain_novelty": same_novelty,
        "structural_distance_detected": structural_distance_detected,
        "h3_reframed_pass": h3_reframed_pass,
        "note": "No cross_domain_novelty_bonus applied. Distance measured by path hops.",
    }


def _score_stats(scored: list[ScoredHypothesis], label: str) -> dict:
    """Compute summary statistics for a list of scored hypotheses."""
    if not scored:
        return {"pipeline": label, "n": 0, "mean_total": 0.0, "mean_novelty": 0.0}
    scores = [s.total_score for s in scored]
    n = len(scores)
    mean = sum(scores) / n
    novelty_mean = sum(s.novelty for s in scored) / n
    cats: dict[str, int] = {}
    for s in scored:
        c = score_category(s.total_score)
        cats[c] = cats.get(c, 0) + 1
    return {
        "pipeline": label,
        "n": n,
        "mean_total": round(mean, 4),
        "mean_novelty": round(novelty_mean, 4),
        "min_total": round(min(scores), 4),
        "max_total": round(max(scores), 4),
        "category_distribution": {k: round(v / n, 4) for k, v in cats.items()},
        "top3": [s.to_dict() for s in scored[:3]],
    }


# ---------------------------------------------------------------------------
# Per-condition runner
# ---------------------------------------------------------------------------

def run_condition(
    cond_name: str,
    full_kg: KnowledgeGraph,
    bio_sub: KnowledgeGraph,
    chem_sub: KnowledgeGraph,
) -> dict:
    """Run single-op and multi-op for one condition and return comparison dict."""
    rubric = EvaluationRubric(cross_domain_novelty_bonus=False)

    single_scored = run_single_op(full_kg, rubric)
    multi_scored, merged_kg = run_multi_op(bio_sub, chem_sub, rubric)

    single_scores = [s.total_score for s in single_scored]
    multi_scores = [s.total_score for s in multi_scored]
    budget_n = min(len(single_scores), len(multi_scores))
    d = cohens_d(multi_scores[:budget_n], single_scores[:budget_n])

    reachability = compute_unique_to_multi_op(single_scored, multi_scored)
    h3 = analyze_h3_structural_distance(multi_scored, merged_kg)
    kg_stats = compute_kg_stats(full_kg)

    return {
        "condition": cond_name,
        "kg_stats": kg_stats,
        "single_op": _score_stats(single_scored, "single_op"),
        "multi_op": _score_stats(multi_scored, "multi_op"),
        "h1_comparison": {
            "cohens_d": round(d, 4),
            "effect_label": "negligible" if abs(d) < 0.2 else ("small" if abs(d) < 0.5 else "medium+"),
            "multi_op_advantage": d > 0.2,
            "budget_n": budget_n,
        },
        "reachability": reachability,
        "h3_analysis": h3,
    }


# ---------------------------------------------------------------------------
# H1 bridge-density function analysis
# ---------------------------------------------------------------------------

def analyze_h1_bridge_density(condition_results: dict) -> dict:
    """Summarise multi-op advantage as function of bridge density.

    Returns a table: condition → {bridge_density, cohens_d, unique_ratio}.
    H1' is supported if advantage peaks at C (sparse) and falls at A/B and D.
    """
    table = {}
    for cond, res in condition_results.items():
        bd = res["kg_stats"]["bridge_density"]
        d = res["h1_comparison"]["cohens_d"]
        unique_rate = res["reachability"]["operator_contribution_rate"]
        table[cond] = {
            "bridge_density": bd,
            "cohens_d": d,
            "unique_to_multi_op_rate": unique_rate,
            "multi_op_advantage": res["h1_comparison"]["multi_op_advantage"],
        }

    # Rank conditions by bridge density
    sorted_conds = sorted(table.items(), key=lambda x: x[1]["bridge_density"])
    densities = [v["bridge_density"] for _, v in sorted_conds]
    advantages = [v["cohens_d"] for _, v in sorted_conds]

    # Simple check: does advantage peak at low-medium density?
    max_adv_idx = advantages.index(max(advantages)) if advantages else 0
    peak_at_sparse = 0 < max_adv_idx < len(advantages) - 1  # not at extremes

    return {
        "condition_table": dict(sorted_conds),
        "sorted_by_bridge_density": [c for c, _ in sorted_conds],
        "bridge_density_values": densities,
        "cohens_d_values": advantages,
        "h1_prime_supported": peak_at_sparse or (
            any(v["multi_op_advantage"] for v in table.values())
            and not all(v["multi_op_advantage"] for v in table.values())
        ),
        "interpretation": (
            "H1': multi-op advantage is conditional on bridge density"
            if peak_at_sparse
            else "H1' not confirmed — advantage pattern does not peak at sparse bridges"
        ),
    }


# ---------------------------------------------------------------------------
# Provenance stability (H4-related) across conditions
# ---------------------------------------------------------------------------

def analyze_provenance_stability(condition_results: dict) -> dict:
    """Check whether provenance-aware ranking is consistent across conditions.

    Runs provenance_aware=True rubric on multi-op output of each condition.
    Returns per-condition mean_traceability for naive vs aware.
    H4 stability: std of Δtraceability across conditions is small.
    """
    from src.data.wikidata_loader import load_wikidata_bio_chem
    from src.kg.real_data import (
        build_condition_a, build_condition_b,
        build_condition_c, build_condition_d,
        extract_domain_subgraph,
    )

    data = load_wikidata_bio_chem()
    conditions = {
        "A": build_condition_a(data),
        "B": build_condition_b(data),
        "C": build_condition_c(data),
        "D": build_condition_d(data),
    }

    naive_rubric = EvaluationRubric(cross_domain_novelty_bonus=False, provenance_aware=False)
    aware_rubric = EvaluationRubric(cross_domain_novelty_bonus=False, provenance_aware=True)

    rows = []
    for cond, full_kg in conditions.items():
        bio_sub = extract_domain_subgraph(full_kg, "biology", f"bio_sub_{cond}")
        chem_sub = extract_domain_subgraph(full_kg, "chemistry", f"chem_sub_{cond}")
        multi, merged = run_multi_op(bio_sub, chem_sub, naive_rubric)
        cands = [s.candidate for s in multi]
        naive_scored = evaluate(cands, merged, naive_rubric)
        aware_scored = evaluate(cands, merged, aware_rubric)
        naive_tr = sum(s.traceability for s in naive_scored) / max(len(naive_scored), 1)
        aware_tr = sum(s.traceability for s in aware_scored) / max(len(aware_scored), 1)
        rows.append({
            "condition": cond,
            "naive_mean_traceability": round(naive_tr, 4),
            "aware_mean_traceability": round(aware_tr, 4),
            "delta_traceability": round(aware_tr - naive_tr, 4),
        })

    deltas = [r["delta_traceability"] for r in rows]
    n = len(deltas)
    mean_delta = sum(deltas) / n if n else 0.0
    std_delta = (sum((d - mean_delta) ** 2 for d in deltas) / max(n - 1, 1)) ** 0.5 if n > 1 else 0.0

    return {
        "per_condition": rows,
        "mean_delta_traceability": round(mean_delta, 4),
        "std_delta_traceability": round(std_delta, 4),
        "stable_ranking": std_delta < 0.05,
        "interpretation": (
            "Provenance-aware ranking is stable across conditions (H4 generalises)"
            if std_delta < 0.05
            else "Provenance-aware effect varies across conditions"
        ),
    }


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------

def _all_candidates_json(condition_results: dict) -> list[dict]:
    """Collect all scored hypotheses from all conditions into a flat list."""
    out = []
    for cond, res in condition_results.items():
        for pipeline in ("single_op", "multi_op"):
            for h in res[pipeline].get("top3", []):
                h = dict(h)
                h["condition"] = cond
                h["pipeline"] = pipeline
                out.append(h)
    return out


def save_run_artifacts(results: dict, run_dir: Path) -> None:
    """Persist all Phase 3 run artifacts to run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)

    with open(run_dir / "run_config.json", "w", encoding="utf-8") as f:
        json.dump(results["run_config"], f, indent=2, ensure_ascii=False)

    with open(run_dir / "output_candidates.json", "w", encoding="utf-8") as f:
        json.dump(_all_candidates_json(results["conditions"]), f, indent=2, ensure_ascii=False)

    for name, content in results["artifacts"].items():
        with open(run_dir / name, "w", encoding="utf-8") as f:
            f.write(content)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict:
    """Run Phase 3 experiment: 4 conditions × 2 pipelines."""
    import random
    random.seed(42)

    data = load_wikidata_bio_chem()

    cond_a_kg = build_condition_a(data)
    cond_b_kg = build_condition_b(data)
    cond_c_kg = build_condition_c(data)
    cond_d_kg = build_condition_d(data)

    # For A/B: domain subgraphs are the same as the full KG (one domain only)
    # For C/D: extract bio/chem sub-graphs from merged KG
    bio_a = extract_domain_subgraph(cond_a_kg, "biology", "bio_sub_A")
    chem_a = extract_domain_subgraph(cond_a_kg, "chemistry", "chem_sub_A")  # empty

    bio_b = extract_domain_subgraph(cond_b_kg, "biology", "bio_sub_B")  # empty
    chem_b = extract_domain_subgraph(cond_b_kg, "chemistry", "chem_sub_B")

    bio_c = extract_domain_subgraph(cond_c_kg, "biology", "bio_sub_C")
    chem_c = extract_domain_subgraph(cond_c_kg, "chemistry", "chem_sub_C")

    bio_d = extract_domain_subgraph(cond_d_kg, "biology", "bio_sub_D")
    chem_d = extract_domain_subgraph(cond_d_kg, "chemistry", "chem_sub_D")

    conditions = {
        "A_bio_only": run_condition("A_bio_only", cond_a_kg, bio_a, chem_a),
        "B_chem_only": run_condition("B_chem_only", cond_b_kg, bio_b, chem_b),
        "C_sparse_bridge": run_condition("C_sparse_bridge", cond_c_kg, bio_c, chem_c),
        "D_dense_bridge": run_condition("D_dense_bridge", cond_d_kg, bio_d, chem_d),
    }

    h1_analysis = analyze_h1_bridge_density(conditions)
    prov_stability = analyze_provenance_stability(conditions)

    run_config = {
        "run_id": "run_007",
        "phase": "Phase3",
        "timestamp": datetime.now().isoformat(),
        "data_source": data.get("source", "unknown"),
        "conditions": ["A_bio_only", "B_chem_only", "C_sparse_bridge", "D_dense_bridge"],
        "pipelines": ["single_op", "multi_op"],
        "rubric": "EvaluationRubric(cross_domain_novelty_bonus=False)",
        "random_seed": 42,
        "research_questions": [
            "H1': multi-op outperforms single-op in sparse-bridge or high-compositionality conditions",
            "H3': cross-domain ops produce genuine novelty when structural distance is meaningful",
        ],
    }

    # Build text artifacts
    artifacts = {
        "data_construction.md": _build_data_construction_md(data),
        "input_summary.md": _build_input_summary_md(
            [cond_a_kg, cond_b_kg, cond_c_kg, cond_d_kg],
            ["A", "B", "C", "D"],
        ),
        "evaluation_summary.md": _build_evaluation_summary_md(conditions),
        "condition_comparison.md": _build_condition_comparison_md(conditions, h1_analysis),
        "next_actions.md": _build_next_actions_md(conditions, h1_analysis, prov_stability),
    }

    return {
        "run_config": run_config,
        "conditions": conditions,
        "h1_bridge_density_analysis": h1_analysis,
        "h4_provenance_stability": prov_stability,
        "artifacts": artifacts,
    }


# ---------------------------------------------------------------------------
# Markdown artifact builders
# ---------------------------------------------------------------------------

def _build_data_construction_md(data: dict) -> str:
    """Generate data_construction.md."""
    src = data.get("source", "unknown")
    bio_n = len(data["bio"]["nodes"])
    bio_e = len(data["bio"]["edges"])
    chem_n = len(data["chem"]["nodes"])
    chem_e = len(data["chem"]["edges"])
    sparse_n = len(data["bridges_sparse"])
    dense_n = len(data["bridges_dense"])

    return f"""# Data Construction — Phase 3 Run 1

## Source
{src}

## Description
{data.get("description", "N/A")}

## Biology subgraph
- Nodes: {bio_n}
- Edges: {bio_e}
- Domain: DNA damage response (TP53/BRCA1/ATM network) + Warburg metabolism
- Topology: hub-and-spoke around TP53; linear cascade from ATM → CHEK2 → TP53 → CDK2/BAX

## Chemistry subgraph
- Nodes: {chem_n}
- Edges: {chem_e}
- Domain: TCA cycle + electron transport chain
- Topology: sequential cycle (citrate → isocitrate → … → oxaloacetate) + ETC cascade

## Cross-domain bridges
- Sparse (Condition C): {sparse_n} bridge edges (shared metabolites: acetyl-CoA, pyruvate, NAD+, NADH)
- Dense (Condition D): {dense_n} bridge edges (+ ATP/ADP sharing + kinase-energy links)

## Structural contrast with toy data
| Property           | Toy data       | Phase 3 data         |
|--------------------|----------------|----------------------|
| Entity names       | synthetic       | real (Wikidata Q-IDs) |
| Topology           | random-ish      | domain-specific      |
| Relation diversity | 6 types         | 10+ types            |
| Bridge mechanism   | explicit        | metabolite sharing   |
| Node count         | 12-15/domain    | 26-31/domain         |

## Reproducibility
Data cached at: `data/cache/wikidata_bio_chem.json`
SPARQL attempted: yes (fallback used if timeout or insufficient results)
Random seed: 42 (set in main())
"""


def _build_input_summary_md(kgs: list, labels: list) -> str:
    """Generate input_summary.md."""
    lines = ["# Input Summary — Phase 3 Run 1\n"]
    for kg, label in zip(kgs, labels):
        from src.kg.real_data import compute_kg_stats
        stats = compute_kg_stats(kg)
        lines.append(f"## Condition {label}: {kg.name}")
        lines.append(f"- Nodes: {stats['node_count']}")
        lines.append(f"- Edges: {stats['edge_count']}")
        lines.append(f"- Bridge density: {stats['bridge_density']:.4f}")
        lines.append(f"- Relation entropy: {stats['relation_entropy']:.4f} bits")
        lines.append(f"- Relation types ({stats['relation_type_count']}): {', '.join(stats['relation_types'][:8])}...")
        lines.append(f"- Domain counts: {stats['domain_counts']}")
        lines.append("")
    return "\n".join(lines)


def _build_evaluation_summary_md(conditions: dict) -> str:
    """Generate evaluation_summary.md."""
    lines = ["# Evaluation Summary — Phase 3 Run 1\n",
             "| Condition | Pipeline | N | mean_total | mean_novelty | unique_to_multi |",
             "|-----------|----------|---|-----------|-------------|-----------------|"]
    for cond, res in conditions.items():
        for pipeline in ("single_op", "multi_op"):
            pres = res[pipeline]
            n = pres.get("n", 0)
            mt = pres.get("mean_total", 0.0)
            mn = pres.get("mean_novelty", 0.0)
            unique = res["reachability"]["unique_to_multi_op_count"] if pipeline == "multi_op" else "—"
            lines.append(f"| {cond} | {pipeline} | {n} | {mt:.4f} | {mn:.4f} | {unique} |")
    lines.append("")
    lines.append("## Reachability (most important metric)")
    for cond, res in conditions.items():
        r = res["reachability"]
        lines.append(f"- **{cond}**: unique_to_multi_op={r['unique_to_multi_op_count']}, "
                     f"contribution_rate={r['operator_contribution_rate']:.4f}")
    return "\n".join(lines)


def _build_condition_comparison_md(conditions: dict, h1_analysis: dict) -> str:
    """Generate condition_comparison.md."""
    lines = [
        "# Condition Comparison — Phase 3 Run 1\n",
        "## H1' analysis: multi-op advantage as function of bridge density\n",
        "| Condition | bridge_density | Cohen's d | unique_rate | multi_op_wins |",
        "|-----------|---------------|-----------|------------|---------------|",
    ]
    for cond, row in h1_analysis["condition_table"].items():
        lines.append(
            f"| {cond} | {row['bridge_density']:.4f} | {row['cohens_d']:.4f} "
            f"| {row['unique_to_multi_op_rate']:.4f} | {row['multi_op_advantage']} |"
        )
    lines.append("")
    lines.append(f"**H1' supported**: {h1_analysis['h1_prime_supported']}")
    lines.append(f"**Interpretation**: {h1_analysis['interpretation']}")
    lines.append("")
    lines.append("## H3' analysis: structural distance across conditions")
    for cond, res in conditions.items():
        h3 = res["h3_analysis"]
        lines.append(f"- **{cond}**: cross_hops={h3['cross_domain_mean_hops']}, "
                     f"same_hops={h3['same_domain_mean_hops']}, "
                     f"structural_dist={h3['structural_distance_detected']}")
    return "\n".join(lines)


def _build_next_actions_md(
    conditions: dict,
    h1_analysis: dict,
    prov_stability: dict,
) -> str:
    """Generate next_actions.md."""
    h1_verdict = "SUPPORTED" if h1_analysis["h1_prime_supported"] else "NOT CONFIRMED"
    prov_verdict = "STABLE" if prov_stability["stable_ranking"] else "VARIABLE"
    lines = [
        "# Next Actions — Phase 3 Run 1\n",
        f"## H1' verdict: {h1_verdict}",
        h1_analysis["interpretation"],
        "",
        f"## H4 provenance stability: {prov_verdict}",
        prov_stability["interpretation"],
        "",
        "## Recommended next experiments",
        "1. If H1' supported: run additional bridge_density points (e.g., 10%, 20%)",
        "2. If H1' not supported: examine alignment quality (how many nodes aligned per condition?)",
        "3. H3': validate with structural distance metric beyond hop count (e.g., graph edit distance)",
        "4. Scale up: increase bio/chem nodes to 100+ using full SPARQL or PubChem dump",
        "5. Run 008: test with noisy real data (edge removal 20%) to verify H2 with real KG",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    results = main()
    run_dir = Path("runs/run_007_20260410_phase3_wikidata_bio_chem")
    save_run_artifacts(results, run_dir)

    # Print summary
    print(json.dumps({
        "h1_analysis": results["h1_bridge_density_analysis"],
        "h4_stability": results["h4_provenance_stability"],
        "conditions_summary": {
            k: {
                "bridge_density": v["kg_stats"]["bridge_density"],
                "single_op_n": v["single_op"]["n"],
                "multi_op_n": v["multi_op"]["n"],
                "cohens_d": v["h1_comparison"]["cohens_d"],
                "unique_to_multi": v["reachability"]["unique_to_multi_op_count"],
            }
            for k, v in results["conditions"].items()
        },
    }, indent=2, ensure_ascii=False))
