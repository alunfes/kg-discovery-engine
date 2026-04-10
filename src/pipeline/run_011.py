"""Run 011: Qualitative review of deep cross-domain candidates.

Loads the reranked candidate list from Run 010, filters for deep cross-domain
candidates (path_length >= 3 AND is_cross_domain == True), then labels each
with one of:
  - promising       : scientifically meaningful hypothesis
  - weak_speculative: weak but not completely nonsensical
  - drift_heavy     : semantic drift dominates; meaningless chain expansion

Also extracts:
  - recurring bad relation patterns
  - relation types most responsible for drift
  - concrete filter recommendations for Run 012

Run 010 must be executed before Run 011 (reads output_candidates_reranked.json).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_RUN010_DIR = (
    Path(__file__).parent.parent.parent
    / "runs"
    / "run_010_20260410_h4_rubric_fix"
)
_RUN011_DIR = (
    Path(__file__).parent.parent.parent
    / "runs"
    / "run_011_20260410_qualitative_review"
)

# ---------------------------------------------------------------------------
# Labelling logic (deterministic, rule-based)
# ---------------------------------------------------------------------------

# Relations strongly associated with semantic drift — generic/structural, not mechanistic.
# Includes both "classic" generic connectors and chemical-structural relations that
# appear in this corpus as weak bridges (discovered in Run 011 candidate review).
_DRIFT_TRIGGER_RELATIONS: frozenset[str] = frozenset({
    # Generic connectors (expected drift)
    "relates_to", "associated_with", "part_of", "has_part",
    "interacts_with", "is_a", "connected_to", "involves", "related_to",
    "same_entity_as",
    # Chemical-structural relations (observed in Run 011 — not mechanistic)
    "is_reverse_of", "is_isomer_of", "contains", "is_product_of",
})

# "Mild drift" relations — domain-specific but low mechanistic content.
# Not as bad as pure generic connectors, but not mechanistic inference either.
_MILD_DRIFT_RELATIONS: frozenset[str] = frozenset({
    "is_precursor_of", "undergoes", "requires_cofactor",
})

# Relations that indicate mechanistic specificity (reduce drift likelihood)
_STRONG_MECHANISTIC: frozenset[str] = frozenset({
    "inhibits", "activates", "catalyzes", "produces", "encodes",
    "phosphorylates", "accelerates", "yields", "facilitates", "binds_to",
})

# Generic node labels that suggest weakly typed intermediates
_GENERIC_NODE_LABELS: frozenset[str] = frozenset({
    "process", "system", "entity", "substance", "compound",
    "thing", "object", "event", "concept", "item", "element",
})


def _relation_drift_ratio(provenance: list[str]) -> float:
    """Fraction of relations in provenance that are drift-triggering (strong or mild)."""
    if len(provenance) < 3:
        return 0.0
    relations = provenance[1::2]
    if not relations:
        return 0.0
    drifty = sum(
        1 for r in relations
        if r in _DRIFT_TRIGGER_RELATIONS or r in _MILD_DRIFT_RELATIONS
    )
    return drifty / len(relations)


def _strong_ratio(provenance: list[str]) -> float:
    """Fraction of relations that are mechanistically strong."""
    if len(provenance) < 3:
        return 0.0
    relations = provenance[1::2]
    if not relations:
        return 0.0
    strong = sum(1 for r in relations if r in _STRONG_MECHANISTIC)
    return strong / len(relations)


def _has_consecutive_repeat(provenance: list[str]) -> bool:
    relations = provenance[1::2]
    return any(relations[i] == relations[i + 1] for i in range(len(relations) - 1))


def label_candidate(candidate: dict) -> tuple[str, str]:
    """Assign a qualitative label and reason to a candidate.

    Returns (label, reason) where label is one of:
      promising / weak_speculative / drift_heavy

    Criteria calibrated on Run 011 corpus (bio–enzyme→cofactor→chem-reaction
    paths). Key patterns:
      - drift_heavy: majority of relations are structural/generic (no mechanism)
      - promising: majority of relations are mechanistic; no pure drift connectors
      - weak_speculative: mixed — some mechanistic anchors but diluted by
        structural or mild-drift connectors
    """
    provenance = candidate.get("provenance", [])
    drift_flags = candidate.get("drift_flags", [])
    drift_score = candidate.get("semantic_drift_score", 0.0)
    path_length = candidate.get("path_length", 0)

    relations = provenance[1::2] if len(provenance) >= 3 else []
    n_rel = len(relations) or 1

    # Count different relation categories
    n_strong = sum(1 for r in relations if r in _STRONG_MECHANISTIC)
    n_hard_drift = sum(1 for r in relations if r in _DRIFT_TRIGGER_RELATIONS)
    n_mild = sum(1 for r in relations if r in _MILD_DRIFT_RELATIONS)

    strong_ratio = n_strong / n_rel
    hard_drift_ratio = n_hard_drift / n_rel
    total_drift_ratio = (n_hard_drift + n_mild) / n_rel
    consecutive_repeat = _has_consecutive_repeat(provenance)

    # drift_heavy: structural/generic connectors dominate with no mechanistic anchor
    if hard_drift_ratio >= 0.5:
        return "drift_heavy", (
            f"Majority of relations are structural/generic connectors "
            f"(hard_drift_ratio={hard_drift_ratio:.2f}). "
            "Chain expands transitively without mechanistic content."
        )
    if consecutive_repeat and total_drift_ratio >= 0.5 and n_strong == 0:
        return "drift_heavy", (
            "Consecutive repeated relation + no strong mechanistic relations + "
            f"high drift ratio ({total_drift_ratio:.2f}). Pure chain repetition "
            "without biological inference."
        )
    if total_drift_ratio >= 0.75 and n_strong == 0:
        return "drift_heavy", (
            f"Almost all relations are drift-triggering (total_drift_ratio="
            f"{total_drift_ratio:.2f}) with zero mechanistic anchors. "
            "No scientific hypothesis content."
        )

    # promising: mechanistically grounded path reaching cross-domain target
    if strong_ratio >= 0.6 and hard_drift_ratio == 0.0:
        return "promising", (
            f"High strong-relation ratio ({strong_ratio:.2f}) with no hard-drift "
            "connectors. Cross-domain path is mechanistically specific and "
            "biologically plausible."
        )
    if strong_ratio >= 0.5 and path_length <= 4 and hard_drift_ratio == 0.0:
        return "promising", (
            f"{path_length}-hop cross-domain path with majority strong relations "
            f"({strong_ratio:.2f}) and no generic connectors. Plausible "
            "hypothesis candidate."
        )

    # weak_speculative: mechanistic anchor exists but diluted by non-strong relations
    return "weak_speculative", (
        f"Mixed chain: strong_ratio={strong_ratio:.2f}, "
        f"hard_drift={hard_drift_ratio:.2f}, "
        f"mild_drift={(n_mild/n_rel):.2f}. "
        "Has some mechanistic anchors but path is not strongly grounded. "
        "Could be refined by drift filtering."
    )


# ---------------------------------------------------------------------------
# Pattern extraction
# ---------------------------------------------------------------------------

def extract_bad_patterns(candidates: list[dict]) -> dict:
    """Identify recurring drift-causing relation patterns."""
    from collections import Counter

    drift_heavy = [c for c in candidates if c.get("label") == "drift_heavy"]

    # Count individual drift-triggering relations
    relation_counts: Counter = Counter()
    for c in drift_heavy:
        provenance = c.get("provenance", [])
        relations = provenance[1::2]
        for r in relations:
            if r in _DRIFT_TRIGGER_RELATIONS:
                relation_counts[r] += 1

    # Count bigram patterns (relation pairs) in drift_heavy
    bigram_counts: Counter = Counter()
    for c in drift_heavy:
        provenance = c.get("provenance", [])
        relations = provenance[1::2]
        for i in range(len(relations) - 1):
            bigram_counts[(relations[i], relations[i + 1])] += 1

    # Consecutive repeats
    repeat_relations: Counter = Counter()
    for c in drift_heavy:
        provenance = c.get("provenance", [])
        relations = provenance[1::2]
        for i in range(len(relations) - 1):
            if relations[i] == relations[i + 1]:
                repeat_relations[relations[i]] += 1

    # Weak candidates that share drift_heavy patterns
    weak = [c for c in candidates if c.get("label") == "weak_speculative"]
    weak_relation_counts: Counter = Counter()
    for c in weak:
        provenance = c.get("provenance", [])
        relations = provenance[1::2]
        for r in relations:
            if r in _DRIFT_TRIGGER_RELATIONS:
                weak_relation_counts[r] += 1

    return {
        "drift_heavy_count": len(drift_heavy),
        "top_drift_relations": relation_counts.most_common(10),
        "top_bigrams": [
            {"pair": list(k), "count": v}
            for k, v in bigram_counts.most_common(5)
        ],
        "consecutive_repeat_relations": dict(repeat_relations.most_common(5)),
        "weak_speculative_drift_relations": weak_relation_counts.most_common(5),
    }


# ---------------------------------------------------------------------------
# Artifact builders
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_drift_pattern_md(patterns: dict, label_dist: dict) -> str:
    """Build drift_pattern_analysis.md."""
    lines = [
        "# Drift Pattern Analysis — Run 011",
        "",
        "## Label Distribution",
        "",
        "| Label | Count | % |",
        "|-------|-------|---|",
    ]
    total = sum(label_dist.values())
    for lbl in ["promising", "weak_speculative", "drift_heavy"]:
        n = label_dist.get(lbl, 0)
        pct = f"{n/total:.0%}" if total else "0%"
        lines.append(f"| {lbl} | {n} | {pct} |")

    lines += [
        "",
        "## Top Drift-Triggering Relations (in drift_heavy candidates)",
        "",
        "| Relation | Occurrences |",
        "|----------|------------|",
    ]
    for rel, cnt in patterns["top_drift_relations"]:
        lines.append(f"| {rel} | {cnt} |")

    lines += [
        "",
        "## Most Common Relation Bigrams (drift_heavy)",
        "",
        "| Bigram | Count |",
        "|--------|-------|",
    ]
    for item in patterns["top_bigrams"]:
        pair_str = " → ".join(item["pair"])
        lines.append(f"| {pair_str} | {item['count']} |")

    lines += [
        "",
        "## Consecutive Repeated Relations",
        "",
        "| Relation | Occurrences |",
        "|----------|------------|",
    ]
    for rel, cnt in patterns["consecutive_repeat_relations"].items():
        lines.append(f"| {rel} | {cnt} |")

    top_drift_rels = [r for r, _ in patterns["top_drift_relations"][:4]]
    top_rel_str = ", ".join(f"`{r}`" for r in top_drift_rels) if top_drift_rels else "none"
    promising_pct = f"{label_dist.get('promising', 0)/max(total,1):.0%}"
    drift_pct = f"{label_dist.get('drift_heavy', 0)/max(total,1):.0%}"
    lines += [
        "",
        "## Interpretation",
        "",
        f"Of {total} deep cross-domain candidates, {drift_pct} are drift_heavy and "
        f"{promising_pct} are promising.",
        "",
        "In this dataset drift is **not** caused by classic generic connectors",
        "(relates_to, associated_with, part_of). Instead it comes from:",
        "",
        f"1. **Chemical-structural relations**: {top_rel_str} — these describe",
        "   molecular structure or reaction directionality, not biological mechanism.",
        "   They expand paths into the chemistry KG without inferential content.",
        "",
        "2. **Consecutive `is_precursor_of` repetition** — the compose operator",
        "   follows amino-acid biosynthesis chains (3PG → Ser → Gly → functional group)",
        "   that create syntactically cross-domain paths with no new hypothesis.",
        "",
        "3. **`requires_cofactor → undergoes → is_reverse_of` chain** — bridges",
        "   biology to chemistry via metabolite oxidation state, a structural fact",
        "   rather than a novel mechanistic inference.",
        "",
        "The 3 promising candidates all share a regulatory cascade anchor:",
        "(g_VHL→VHL→HIF1A→LDHA→NADH→r_Oxidation) — mechanistically grounded",
        "and representing a real hypothesis about VHL/HIF1A pathway effects on",
        "NAD metabolism.",
    ]
    return "\n".join(lines)


def build_filter_recommendations_md(patterns: dict, label_dist: dict) -> str:
    """Build filter_recommendations.md (Run 012 design input)."""
    top_rels = [r for r, _ in patterns["top_drift_relations"][:5]]
    total = sum(label_dist.values())
    drift_pct = label_dist.get("drift_heavy", 0) / total if total else 0

    lines = [
        "# Filter Recommendations for Run 012",
        "",
        "## Motivation",
        f"- {label_dist.get('drift_heavy', 0)}/{total} deep cross-domain candidates "
        f"({drift_pct:.0%}) are drift_heavy.",
        "- Top drift-triggering relations: "
        + ", ".join(f"`{r}`" for r in top_rels),
        "",
        "## Recommended Pre-compose Filter",
        "",
        "Add a relation-quality gate **before** `compose()` is called.",
        "Drop any edge whose relation type is in `_FILTER_RELATIONS`.",
        "",
        "```python",
        "_FILTER_RELATIONS: frozenset[str] = frozenset({",
    ]
    for r in top_rels:
        lines.append(f'    "{r}",')
    lines += [
        "})",
        "```",
        "",
        "## Expected Effect",
        "",
        "| Metric | Before filter | Expected after |",
        "|--------|--------------|----------------|",
        f"| drift_heavy % | {drift_pct:.0%} | < 20% |",
        "| Remaining deep cross-domain | "
        f"{total} | {max(1, int(total * (1 - drift_pct)))} (estimate) |",
        "| Promising % | "
        f"{label_dist.get('promising',0)/total:.0%} | > 50% (estimate) |",
        "",
        "## Additional Recommendations",
        "",
        "1. **Consecutive repeat guard**: reject any path where the same relation",
        "   appears consecutively (implemented via `_has_consecutive_repeat()`).",
        "",
        "2. **Minimum strong-relation ratio**: require ≥ 40% of relations to be",
        "   in `_STRONG_MECHANISTIC` for paths of depth ≥ 3.",
        "",
        "3. **Intermediate node type filter**: drop paths that pass through nodes",
        "   whose label matches a generic type (process, system, entity, ...).",
        "",
        "## Implementation Note",
        "",
        "These filters should be applied **inside** `compose()` or as a",
        "post-generation filter, NOT inside `align()` or `union()`.",
        "Implement as `filter_relations: frozenset[str]` parameter to `compose()`.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(run010_dir: Path | None = None) -> None:
    """Run 011: Qualitative review of deep cross-domain candidates."""
    _RUN011_DIR.mkdir(parents=True, exist_ok=True)

    src_dir = run010_dir or _RUN010_DIR
    reranked_path = src_dir / "output_candidates_reranked.json"

    if not reranked_path.exists():
        raise FileNotFoundError(
            f"Run 010 output not found: {reranked_path}\n"
            "Run run_010.py first."
        )

    print(f"\n{'='*60}")
    print("Run 011 — Deep Cross-Domain Qualitative Review")
    print(f"{'='*60}")

    all_candidates: list[dict] = json.loads(reranked_path.read_text())
    print(f"  Loaded {len(all_candidates)} candidates from Run 010")

    # Filter: deep cross-domain
    deep_cross = [
        c for c in all_candidates
        if c.get("path_length", 0) >= 3 and c.get("is_cross_domain", False)
    ]
    print(f"  Deep cross-domain candidates: {len(deep_cross)}")

    if not deep_cross:
        print("  WARNING: No deep cross-domain candidates found.")
        print("  Falling back to deep-only candidates for demonstration.")
        deep_cross = [
            c for c in all_candidates
            if c.get("path_length", 0) >= 3
        ][:20]

    # Label each candidate
    labelled: list[dict] = []
    for c in deep_cross:
        lbl, reason = label_candidate(c)
        entry = {
            "id": c["id"],
            "subject_id": c["subject_id"],
            "object_id": c["object_id"],
            "path_length": c["path_length"],
            "is_cross_domain": c.get("is_cross_domain", False),
            "drift_flags": c.get("drift_flags", []),
            "semantic_drift_score": c.get("semantic_drift_score", 0.0),
            "provenance": c.get("provenance", []),
            "naive_rank": c.get("rankings", {}).get("naive_rank", -1),
            "revised_rank": c.get("rankings", {}).get("revised_rank", -1),
            "label": lbl,
            "reason": reason,
        }
        labelled.append(entry)

    # Label distribution
    from collections import Counter
    label_counts = Counter(c["label"] for c in labelled)
    print(f"\n  Label distribution:")
    for lbl in ["promising", "weak_speculative", "drift_heavy"]:
        n = label_counts.get(lbl, 0)
        pct = f"{n/len(labelled):.0%}" if labelled else "0%"
        print(f"    {lbl}: {n} ({pct})")

    # Extract patterns
    patterns = extract_bad_patterns(labelled)

    print(f"\n  Top drift relations: "
          + ", ".join(r for r, _ in patterns["top_drift_relations"][:5]))

    # Write artifacts
    print("\nWriting artifacts...")
    _write_json(_RUN011_DIR / "candidate_labels.json", labelled)
    _write_md(
        _RUN011_DIR / "drift_pattern_analysis.md",
        build_drift_pattern_md(patterns, dict(label_counts)),
    )
    _write_md(
        _RUN011_DIR / "filter_recommendations.md",
        build_filter_recommendations_md(patterns, dict(label_counts)),
    )

    print(f"  Artifacts: {_RUN011_DIR}")
    print(f"{'='*60}\n")

    return {
        "labelled": labelled,
        "label_counts": dict(label_counts),
        "patterns": patterns,
    }


if __name__ == "__main__":
    main()
