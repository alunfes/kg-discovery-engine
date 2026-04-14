"""WS3: Ranking function implementations R1–R5 (P4 evidence-aware ranking).

Five ranking strategies for compose-path candidates:

  R1 (Baseline)      — shortest-path + path_weight (current system)
  R2 (Evidence-only) — e_score_min only
  R3 (Struct+Evid)   — 0.4 * structure + 0.6 * evidence
  R4 (Full hybrid)   — 0.3 * structure + 0.4 * evidence + 0.2 * novelty + 0.1 * density
  R5 (Conservative)  — baseline − penalty(low_evidence)

All functions take a list of feature-enriched candidates and return a new sorted
list with a 'rank' field and the ranking's 'score' field attached.

Usage:
    from src.scientific_hypothesis.ranking_functions import RANKERS, apply_ranker
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Normalisation helpers (min-max, called per-batch)
# ---------------------------------------------------------------------------

def _minmax(values: list[float]) -> list[float]:
    """Normalise values to [0, 1] using min-max scaling.

    Returns the original list unchanged if all values are equal.
    """
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _safe_norm(candidates: list[dict], key: str) -> list[float]:
    """Extract and min-max normalise a numeric field from candidates."""
    vals = [float(c.get(key, 0.0)) for c in candidates]
    return _minmax(vals)


# ---------------------------------------------------------------------------
# R1 — Baseline: path_length (ASC) + path_weight (DESC)
# ---------------------------------------------------------------------------

def rank_r1(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """R1 Baseline: current shortest-path + weight ranking.

    score = 1.0 / path_length + 0.1 * log_path_weight
    Lower path_length → higher score; tie-broken by path_weight.

    Args:
        candidates: Feature-enriched candidate list.

    Returns:
        New sorted list with 'score_r1' and 'rank' fields.
    """
    ranked = []
    for c in candidates:
        pl = max(1, c.get("path_length", 1))
        pw = max(1e-9, c.get("path_weight", 1.0))
        score = 1.0 / pl + 0.1 * math.log10(pw + 1e-9)
        ranked.append({**c, "score_r1": round(score, 8)})
    ranked.sort(key=lambda x: -x["score_r1"])
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# R2 — Evidence-only: e_score_min
# ---------------------------------------------------------------------------

def rank_r2(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """R2 Evidence-only: rank purely by minimum edge evidence score.

    score = e_score_min  (= log10(min_edge_literature + 1))

    Args:
        candidates: Feature-enriched candidate list with e_score_min.

    Returns:
        New sorted list with 'score_r2' and 'rank' fields.
    """
    ranked = [{**c, "score_r2": round(float(c.get("e_score_min", 0.0)), 8)}
              for c in candidates]
    ranked.sort(key=lambda x: -x["score_r2"])
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# R3 — Structure + Evidence: 0.4 * structure_norm + 0.6 * evidence_norm
# ---------------------------------------------------------------------------

def rank_r3(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """R3 Structure + Evidence hybrid (40/60 split).

    structure_norm  = normalised (1.0 / path_length)
    evidence_norm   = normalised e_score_min

    score = 0.4 * structure_norm + 0.6 * evidence_norm

    Args:
        candidates: Feature-enriched candidate list.

    Returns:
        New sorted list with 'score_r3' and 'rank' fields.
    """
    struct_raw = [1.0 / max(1, c.get("path_length", 1)) for c in candidates]
    evid_raw = [float(c.get("e_score_min", 0.0)) for c in candidates]
    struct_norm = _minmax(struct_raw)
    evid_norm = _minmax(evid_raw)

    ranked = []
    for c, s, e in zip(candidates, struct_norm, evid_norm):
        score = 0.4 * s + 0.6 * e
        ranked.append({**c, "score_r3": round(score, 8)})
    ranked.sort(key=lambda x: -x["score_r3"])
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# R4 — Full hybrid: 0.3 * struct + 0.4 * evid + 0.2 * novelty + 0.1 * density
# ---------------------------------------------------------------------------

def rank_r4(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """R4 Full hybrid (structure/evidence/novelty/density).

    structure  = normalised (1.0 / path_length)
    evidence   = normalised e_score_min
    novelty    = normalised cross_domain_ratio
    density    = normalised log_min_edge_lit  (same as evidence here; kept separate
                 to preserve the design distinction: density = PubMed hit count as
                 KG weight proxy, evidence = co-occurrence for investigability)

    score = 0.3 * struct + 0.4 * evid + 0.2 * novelty + 0.1 * density

    Note: density uses avg_edge_literature (KG structural density proxy) rather
    than e_score_min to avoid double-counting evidence.

    Args:
        candidates: Feature-enriched candidate list.

    Returns:
        New sorted list with 'score_r4' and 'rank' fields.
    """
    struct_raw = [1.0 / max(1, c.get("path_length", 1)) for c in candidates]
    evid_raw = [float(c.get("e_score_min", 0.0)) for c in candidates]
    novelty_raw = [float(c.get("cross_domain_ratio", 0.0)) for c in candidates]
    # density proxy: avg_edge_literature captures local KG richness
    density_raw = [math.log10(float(c.get("avg_edge_literature", 0.0)) + 1)
                   for c in candidates]

    struct_norm = _minmax(struct_raw)
    evid_norm = _minmax(evid_raw)
    novelty_norm = _minmax(novelty_raw)
    density_norm = _minmax(density_raw)

    ranked = []
    for c, s, e, n, d in zip(candidates, struct_norm, evid_norm, novelty_norm, density_norm):
        score = 0.3 * s + 0.4 * e + 0.2 * n + 0.1 * d
        ranked.append({**c, "score_r4": round(score, 8)})
    ranked.sort(key=lambda x: -x["score_r4"])
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# R5 — Conservative: R1 baseline − penalty(low_evidence)
# ---------------------------------------------------------------------------

def rank_r5(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """R5 Conservative: baseline score penalised for literature-sparse paths.

    penalty = max(0, threshold − e_score_min) * lambda_
    threshold = median e_score_min across all candidates
    lambda_   = 0.5

    score = score_r1 − penalty

    Rationale: preserves structural ordering but demotes paths whose bottleneck
    edge falls below the population median evidence level.

    Args:
        candidates: Feature-enriched candidate list (must have score_r1 or path data).

    Returns:
        New sorted list with 'score_r5' and 'rank' fields.
    """
    lambda_ = 0.5

    # Compute R1 scores if not present
    r1_scores = [
        1.0 / max(1, c.get("path_length", 1))
        + 0.1 * math.log10(max(1e-9, c.get("path_weight", 1.0)) + 1e-9)
        for c in candidates
    ]
    e_scores = [float(c.get("e_score_min", 0.0)) for c in candidates]
    threshold = statistics.median(e_scores)

    ranked = []
    for c, r1, e in zip(candidates, r1_scores, e_scores):
        penalty = max(0.0, threshold - e) * lambda_
        score = r1 - penalty
        ranked.append({**c, "score_r5": round(score, 8), "r5_penalty": round(penalty, 8)})
    ranked.sort(key=lambda x: -x["score_r5"])
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    return ranked


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

RANKERS: dict[str, Callable[[list[dict]], list[dict]]] = {
    "R1_baseline": rank_r1,
    "R2_evidence_only": rank_r2,
    "R3_struct_evidence": rank_r3,
    "R4_full_hybrid": rank_r4,
    "R5_conservative": rank_r5,
}


def apply_ranker(
    name: str,
    candidates: list[dict[str, Any]],
    top_k: int = 70,
) -> list[dict[str, Any]]:
    """Apply a named ranking function and return top-k candidates.

    Args:
        name: Ranker name (key in RANKERS).
        candidates: Full feature-enriched candidate list.
        top_k: Number of top candidates to return.

    Returns:
        List of at most top_k candidates, sorted by descending score.

    Raises:
        KeyError: If name is not in RANKERS.
    """
    ranker = RANKERS[name]
    ranked = ranker(candidates)
    return ranked[:top_k]
