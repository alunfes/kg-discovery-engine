"""Operator pipeline runner for trading-domain KG discovery."""

from __future__ import annotations

from src.kg.models import KnowledgeGraph, HypothesisCandidate
from src.pipeline.operators import align, union, compose, difference


def deduplicate_candidates(
    candidates: list[HypothesisCandidate],
) -> list[HypothesisCandidate]:
    """Remove duplicate candidates by (subject_id, relation, object_id).

    Keeps the first occurrence in input order.
    """
    seen: set[tuple[str, str, str]] = set()
    result: list[HypothesisCandidate] = []
    for c in candidates:
        key = (c.subject_id, c.relation, c.object_id)
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def run_align_compose_pipeline(
    kg_source: KnowledgeGraph,
    kg_target: KnowledgeGraph,
    max_depth: int = 3,
) -> list[HypothesisCandidate]:
    """Run align -> union -> compose pipeline on two KGs.

    Steps:
    1. Align kg_source and kg_target to find shared semantic nodes.
    2. Union them into a merged KG.
    3. Compose the merged KG to generate hypothesis candidates.

    Returns all candidates from the merged KG.
    """
    alignment = align(kg_source, kg_target, threshold=0.5)
    merged_name = f"{kg_source.name}+{kg_target.name}"
    merged = union(kg_source, kg_target, alignment=alignment, name=merged_name)
    return compose(merged, max_depth=max_depth)


def run_compose_with_difference(
    kg_base: KnowledgeGraph,
    kg_contrast: KnowledgeGraph,
    max_depth: int = 3,
) -> list[HypothesisCandidate]:
    """Run align -> difference -> compose to find regime-specific hypotheses.

    Steps:
    1. Align kg_base and kg_contrast.
    2. Extract difference (base - contrast) to isolate unique structure.
    3. Compose the difference KG.

    Returns hypotheses unique to kg_base not in kg_contrast.
    """
    alignment = align(kg_base, kg_contrast, threshold=0.5)
    diff_name = f"{kg_base.name}-{kg_contrast.name}"
    diff_kg = difference(kg_base, kg_contrast, alignment=alignment, name=diff_name)
    return compose(diff_kg, max_depth=max_depth)


def run_full_pipeline(
    kgs: dict[str, KnowledgeGraph],
    max_depth: int = 3,
) -> list[HypothesisCandidate]:
    """Run the full multi-KG discovery pipeline.

    Pipeline:
    1. Compose each KG individually (intra-domain).
    2. Align + union microstructure + cross_asset -> compose (cross-domain bridge).
    3. Align + union execution + regime -> compose (execution-regime).
    4. Regime - microstructure difference -> compose (regime-specific isolation).

    Returns all candidates from all pipelines, deduplicated by
    (subject_id, relation, object_id).
    """
    all_candidates: list[HypothesisCandidate] = []

    # Step 1: intra-domain compose for each KG
    for kg in kgs.values():
        all_candidates.extend(compose(kg, max_depth=max_depth))

    # Step 2: cross-domain bridge — microstructure + cross_asset
    if "microstructure" in kgs and "cross_asset" in kgs:
        bridge_candidates = run_align_compose_pipeline(
            kgs["microstructure"], kgs["cross_asset"], max_depth=max_depth
        )
        all_candidates.extend(bridge_candidates)

    # Step 3: execution-regime bridge
    if "execution" in kgs and "regime" in kgs:
        exec_regime_candidates = run_align_compose_pipeline(
            kgs["execution"], kgs["regime"], max_depth=max_depth
        )
        all_candidates.extend(exec_regime_candidates)

    # Step 4: regime-specific isolation (regime - microstructure)
    if "regime" in kgs and "microstructure" in kgs:
        regime_specific = run_compose_with_difference(
            kgs["regime"], kgs["microstructure"], max_depth=max_depth
        )
        all_candidates.extend(regime_specific)

    return deduplicate_candidates(all_candidates)
