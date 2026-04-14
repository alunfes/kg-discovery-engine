"""WS2: Evidence score definitions for evidence-aware ranking (P4).

Defines edge-level and three path-level evidence scoring variants:
  e_path_min      — bottleneck: min edge evidence score
  e_path_avg      — mean across all edges
  e_path_weighted — positional decay (earlier edges weighted more)

All functions operate on pre-fetched feature dicts (no live API calls here).

Usage:
    from src.scientific_hypothesis.evidence_scoring import score_candidate
"""
from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Edge-level score
# ---------------------------------------------------------------------------

def e_edge(pubmed_count: int) -> float:
    """Compute edge evidence score from raw PubMed co-occurrence count (≤2023).

    e_edge(u, v) = log10(pubmed_count(u AND v, ≤2023) + 1)

    Args:
        pubmed_count: Non-negative integer co-occurrence count.

    Returns:
        Non-negative float. Range [0, ~5] for typical counts.
    """
    return math.log10(max(0, pubmed_count) + 1)


# ---------------------------------------------------------------------------
# Path-level score variants
# ---------------------------------------------------------------------------

def e_path_min(edge_literature_counts: list[int]) -> float:
    """Bottleneck path score: minimum edge evidence score across the path.

    Penalises paths with any literature-sparse edge. A single low-coverage
    edge collapses the path score even if other edges are well-supported.

    Args:
        edge_literature_counts: Per-edge PubMed co-occurrence counts (≤2023).

    Returns:
        Float evidence score [0, ~5].
    """
    if not edge_literature_counts:
        return 0.0
    return e_edge(min(edge_literature_counts))


def e_path_avg(edge_literature_counts: list[int]) -> float:
    """Average path score: mean of per-edge evidence scores.

    Smooths over bottleneck edges; does not hard-penalise sparse edges.

    Args:
        edge_literature_counts: Per-edge PubMed co-occurrence counts (≤2023).

    Returns:
        Float evidence score [0, ~5].
    """
    if not edge_literature_counts:
        return 0.0
    return sum(e_edge(c) for c in edge_literature_counts) / len(edge_literature_counts)


def e_path_weighted(edge_literature_counts: list[int]) -> float:
    """Positional-decay path score: earlier edges weighted more heavily.

    w_i = 1 / (i + 1), then normalised so weights sum to 1.
    Rationale: path start (subject node) is the manipulable entity; its
    direct evidence linkage matters most for experimental feasibility.

    Args:
        edge_literature_counts: Per-edge PubMed co-occurrence counts (≤2023).

    Returns:
        Float evidence score [0, ~5].
    """
    if not edge_literature_counts:
        return 0.0
    weights = [1.0 / (i + 1) for i in range(len(edge_literature_counts))]
    total_w = sum(weights)
    return sum(w * e_edge(c) for w, c in zip(weights, edge_literature_counts)) / total_w


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------

def score_candidate(candidate: dict[str, Any]) -> dict[str, float]:
    """Compute all three evidence scores for a feature-enriched candidate.

    Expects the candidate to have 'edge_literature_counts' set by path_features.py.

    Args:
        candidate: Dict with at minimum 'edge_literature_counts' (list[int]).

    Returns:
        Dict with keys: e_score_min, e_score_avg, e_score_weighted.
    """
    counts = candidate.get("edge_literature_counts", [])
    return {
        "e_score_min": round(e_path_min(counts), 6),
        "e_score_avg": round(e_path_avg(counts), 6),
        "e_score_weighted": round(e_path_weighted(counts), 6),
    }


def attach_evidence_scores(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach all three evidence scores to each candidate in-place.

    Args:
        candidates: List of feature-enriched candidate dicts.

    Returns:
        Same list with e_score_min/avg/weighted added to each entry.
    """
    for c in candidates:
        c.update(score_candidate(c))
    return candidates
