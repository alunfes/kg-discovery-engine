"""WS2: 5 augmentation-aware selection policies.

Policy A (Baseline):          Current shortest-path top-k
Policy B (Augmentation Quota): 15 augmented + 55 baseline slots
Policy C (Novelty Boost):     score = base_rank + α * novelty(path)
Policy D (Multi-bucket):      4 buckets: 35 short + 15 aug + 10 novelty + 10 exploratory
Policy E (Reranking Layer):   top-200 pool → greedy composite reranker → top-k

Each policy exposes a select() interface compatible with compose_diagnostics candidates.

Usage:
    from src.scientific_hypothesis.selection_policies_v2 import ALL_POLICIES, get_policy
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any

SEED = 42


# ---------------------------------------------------------------------------
# Augmentation tagging
# ---------------------------------------------------------------------------

def tag_augmented(
    candidates: list[dict],
    aug_edge_set: set[tuple[str, str]],
) -> None:
    """Tag each candidate dict with uses_augmented_edge in-place."""
    for c in candidates:
        path = c.get("path", [])
        c["uses_augmented_edge"] = any(
            (path[i], path[i + 1]) in aug_edge_set
            for i in range(len(path) - 1)
        )


# ---------------------------------------------------------------------------
# Novelty scoring
# ---------------------------------------------------------------------------

def novelty_score(c: dict) -> float:
    """Compute path novelty score (0.0–0.5).

    Components:
      +0.3  uses augmented edge
      +0.1  path_length >= 4
      +0.1  cross-domain (chem subject, bio object)
    """
    score = 0.0
    if c.get("uses_augmented_edge", False):
        score += 0.3
    if c.get("path_length", 0) >= 4:
        score += 0.1
    subj = c.get("subject_id", "")
    obj = c.get("object_id", "")
    cross = (subj.startswith("chem:") and obj.startswith("bio:")) or \
            (subj.startswith("bio:") and obj.startswith("chem:"))
    if cross:
        score += 0.1
    return score


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SelectionPolicy(ABC):
    """Abstract base for augmentation-aware selection policies."""

    name: str

    @abstractmethod
    def select(
        self,
        candidates: list[dict],
        k: int,
        aug_edge_set: set[tuple[str, str]],
        seed: int = SEED,
    ) -> list[dict]:
        """Select k candidates from pool.

        Args:
            candidates: Full pool of path candidate dicts (path, path_length,
                        path_weight, subject_id, object_id required).
            k: Target selection size.
            aug_edge_set: Set of (source_id, target_id) augmented edges.
            seed: Random seed (for stochastic policies).

        Returns:
            Selected list of up to k candidates.
        """
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Return human-readable policy description dict."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Shared utility: dedup by (subject, object) pair
# ---------------------------------------------------------------------------

def _dedup_pick(
    pool: list[dict],
    n: int,
    used: set[tuple[str, str]],
) -> list[dict]:
    """Pick up to n from pool without repeating (subject, object) pairs."""
    result: list[dict] = []
    for c in pool:
        key = (c["subject_id"], c["object_id"])
        if key not in used and len(result) < n:
            used.add(key)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Policy A: Baseline
# ---------------------------------------------------------------------------

class PolicyA(SelectionPolicy):
    """Policy A: Shortest-path top-k (current baseline)."""

    name = "A_baseline"

    def select(
        self,
        candidates: list[dict],
        k: int,
        aug_edge_set: set[tuple[str, str]],
        seed: int = SEED,
    ) -> list[dict]:
        """Sort by (path_length ASC, path_weight DESC), deduplicate, take top-k."""
        tag_augmented(candidates, aug_edge_set)
        ranked = sorted(candidates, key=lambda c: (c["path_length"], -c.get("path_weight", 0)))
        seen: set[tuple[str, str]] = set()
        return _dedup_pick(ranked, k, seen)

    def describe(self) -> dict[str, Any]:
        """Describe Policy A."""
        return {
            "name": self.name,
            "label": "Baseline (shortest-path top-k)",
            "formula": "sort(path_length ASC, path_weight DESC) → top-k",
            "augmented_quota": 0,
            "expected_augmented_inclusion": "~0 (displaced by shorter original paths)",
        }


# ---------------------------------------------------------------------------
# Policy B: Augmentation Quota
# ---------------------------------------------------------------------------

class PolicyB(SelectionPolicy):
    """Policy B: Reserve k_aug slots for augmented-edge paths."""

    name = "B_augmentation_quota"

    def __init__(self, k_aug: int = 15) -> None:
        """Initialize with augmentation quota."""
        self.k_aug = k_aug

    def select(
        self,
        candidates: list[dict],
        k: int,
        aug_edge_set: set[tuple[str, str]],
        seed: int = SEED,
    ) -> list[dict]:
        """Fill k_aug from augmented paths, remaining k-k_aug from non-augmented."""
        tag_augmented(candidates, aug_edge_set)
        ranked = sorted(candidates, key=lambda c: (c["path_length"], -c.get("path_weight", 0)))
        aug_pool = [c for c in ranked if c["uses_augmented_edge"]]
        non_aug_pool = [c for c in ranked if not c["uses_augmented_edge"]]
        used: set[tuple[str, str]] = set()
        selected_aug = _dedup_pick(aug_pool, self.k_aug, used)
        k_rest = k - len(selected_aug)
        selected_rest = _dedup_pick(non_aug_pool, k_rest, used)
        return (selected_rest + selected_aug)[:k]

    def describe(self) -> dict[str, Any]:
        """Describe Policy B."""
        return {
            "name": self.name,
            "label": f"Augmentation Quota ({self.k_aug} reserved slots)",
            "formula": f"top-{self.k_aug} augmented (shortest-path rank) + top-{70-self.k_aug} non-augmented",
            "augmented_quota": self.k_aug,
        }


# ---------------------------------------------------------------------------
# Policy C: Novelty Boost
# ---------------------------------------------------------------------------

class PolicyC(SelectionPolicy):
    """Policy C: score = base_rank_score + alpha * novelty(path)."""

    name = "C_novelty_boost"

    def __init__(self, alpha: float = 0.5) -> None:
        """Initialize with novelty boost coefficient alpha."""
        self.alpha = alpha

    def select(
        self,
        candidates: list[dict],
        k: int,
        aug_edge_set: set[tuple[str, str]],
        seed: int = SEED,
    ) -> list[dict]:
        """Compute composite score, deduplicate, take top-k by score."""
        tag_augmented(candidates, aug_edge_set)
        max_len = max((c.get("path_length", 1) for c in candidates), default=1)
        for c in candidates:
            base = 1.0 - (c.get("path_length", max_len) / max(max_len, 1))
            c["novelty_score"] = novelty_score(c)
            c["composite_score"] = round(base + self.alpha * c["novelty_score"], 4)
        ranked = sorted(candidates, key=lambda c: -c["composite_score"])
        seen: set[tuple[str, str]] = set()
        return _dedup_pick(ranked, k, seen)

    def describe(self) -> dict[str, Any]:
        """Describe Policy C."""
        return {
            "name": self.name,
            "label": "Novelty Boost (α=0.5)",
            "formula": "score = (1 - path_len/max_len) + 0.5 * novelty(path)",
            "alpha": self.alpha,
            "novelty_components": {
                "uses_augmented_edge": "+0.3",
                "path_length_ge_4": "+0.1",
                "cross_domain": "+0.1",
            },
        }


# ---------------------------------------------------------------------------
# Policy D: Multi-bucket
# ---------------------------------------------------------------------------

class PolicyD(SelectionPolicy):
    """Policy D: 4 non-overlapping buckets with augmentation guarantee."""

    name = "D_multi_bucket"

    def __init__(
        self,
        b1_n: int = 35,
        b2_n: int = 15,
        b3_n: int = 10,
        b4_n: int = 10,
    ) -> None:
        """Initialize with bucket sizes (must sum to k target)."""
        self.b1_n = b1_n   # shortest-path stable
        self.b2_n = b2_n   # augmented paths
        self.b3_n = b3_n   # high-novelty
        self.b4_n = b4_n   # exploratory (longer paths, mid-range weight)

    def select(
        self,
        candidates: list[dict],
        k: int,
        aug_edge_set: set[tuple[str, str]],
        seed: int = SEED,
    ) -> list[dict]:
        """Fill 4 buckets sequentially, no duplicate (subject, object) pairs."""
        tag_augmented(candidates, aug_edge_set)
        baseline = sorted(candidates, key=lambda c: (c["path_length"], -c.get("path_weight", 0)))
        used: set[tuple[str, str]] = set()

        b1 = _dedup_pick(baseline, self.b1_n, used)

        aug_pool = [c for c in baseline if c["uses_augmented_edge"]]
        b2 = _dedup_pick(aug_pool, self.b2_n, used)

        nov_pool = sorted(candidates, key=lambda c: -novelty_score(c))
        b3 = _dedup_pick(nov_pool, self.b3_n, used)

        max_w = max((c.get("path_weight", 0) for c in candidates), default=1.0)
        expl_pool = sorted(
            [c for c in candidates if c.get("path_length", 0) >= 3],
            key=lambda c: abs(c.get("path_weight", 0) / max(max_w, 1e-9) - 0.5),
        )
        b4 = _dedup_pick(expl_pool, self.b4_n, used)

        selected = b1 + b2 + b3 + b4
        if len(selected) < k:
            selected += _dedup_pick(baseline, k - len(selected), used)
        return selected[:k]

    def describe(self) -> dict[str, Any]:
        """Describe Policy D."""
        return {
            "name": self.name,
            "label": "Multi-bucket (4 buckets)",
            "buckets": {
                "b1_shortest": self.b1_n,
                "b2_augmented": self.b2_n,
                "b3_high_novelty": self.b3_n,
                "b4_mid_density_exploratory": self.b4_n,
            },
        }


# ---------------------------------------------------------------------------
# Policy E: Reranking Layer
# ---------------------------------------------------------------------------

class PolicyE(SelectionPolicy):
    """Policy E: Wide pool (top-200) + greedy composite reranker → top-k."""

    name = "E_reranking_layer"

    def __init__(
        self,
        pool_size: int = 200,
        w_quality: float = 0.4,
        w_density: float = 0.2,
        w_diversity: float = 0.2,
        w_aug: float = 0.2,
    ) -> None:
        """Initialize with pool size and reranker component weights."""
        self.pool_size = pool_size
        self.w_quality = w_quality
        self.w_density = w_density
        self.w_diversity = w_diversity
        self.w_aug = w_aug

    def _path_quality(self, c: dict, max_len: int, max_w: float) -> float:
        """Normalize path quality: short paths + high weight = higher score."""
        len_score = 1.0 - c.get("path_length", max_len) / max(max_len, 1)
        w_score = c.get("path_weight", 0) / max(max_w, 1e-9)
        return 0.6 * len_score + 0.4 * w_score

    def select(
        self,
        candidates: list[dict],
        k: int,
        aug_edge_set: set[tuple[str, str]],
        seed: int = SEED,
    ) -> list[dict]:
        """Stage 1: baseline top-pool_size; Stage 2: greedy reranker with diversity."""
        tag_augmented(candidates, aug_edge_set)
        baseline = sorted(candidates, key=lambda c: (c["path_length"], -c.get("path_weight", 0)))
        pool = baseline[:self.pool_size]

        max_len = max((c.get("path_length", 1) for c in pool), default=1)
        max_w = max((c.get("path_weight", 0) for c in pool), default=1.0)

        selected: list[dict] = []
        selected_pairs: set[tuple[str, str]] = set()
        sel_subjects: set[str] = set()
        sel_objects: set[str] = set()
        remaining = list(pool)

        while len(selected) < k and remaining:
            best_score = -float("inf")
            best_idx = 0
            for idx, c in enumerate(remaining):
                pair = (c["subject_id"], c["object_id"])
                if pair in selected_pairs:
                    continue
                pq = self._path_quality(c, max_len, max_w)
                dp = c.get("path_weight", 0) / max(max_w, 1e-9)
                s_rep = 1 if c["subject_id"] in sel_subjects else 0
                o_rep = 1 if c["object_id"] in sel_objects else 0
                div = -(s_rep * 0.5 + o_rep * 0.5)
                ab = 1.0 if c.get("uses_augmented_edge") else 0.0
                score = (
                    self.w_quality * pq
                    + self.w_density * dp
                    + self.w_diversity * div
                    + self.w_aug * ab
                )
                if score > best_score:
                    best_score = score
                    best_idx = idx
            chosen = remaining.pop(best_idx)
            pair = (chosen["subject_id"], chosen["object_id"])
            if pair not in selected_pairs:
                selected_pairs.add(pair)
                sel_subjects.add(chosen["subject_id"])
                sel_objects.add(chosen["object_id"])
                selected.append(chosen)

        return selected

    def describe(self) -> dict[str, Any]:
        """Describe Policy E."""
        return {
            "name": self.name,
            "label": f"Reranking Layer (pool={self.pool_size})",
            "pool_size": self.pool_size,
            "reranker_formula": (
                f"{self.w_quality}*path_quality + {self.w_density}*density_proxy "
                f"+ {self.w_diversity}*diversity_penalty + {self.w_aug}*aug_bonus"
            ),
            "reranker_weights": {
                "path_quality": self.w_quality,
                "density_proxy": self.w_density,
                "diversity_penalty": self.w_diversity,
                "augmented_bonus": self.w_aug,
            },
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_POLICIES: list[SelectionPolicy] = [
    PolicyA(),
    PolicyB(k_aug=15),
    PolicyC(alpha=0.5),
    PolicyD(b1_n=35, b2_n=15, b3_n=10, b4_n=10),
    PolicyE(pool_size=200),
]


def get_policy(name: str) -> SelectionPolicy:
    """Return policy instance by name."""
    for p in ALL_POLICIES:
        if p.name == name:
            return p
    raise ValueError(f"Unknown policy: {name!r}. Available: {[p.name for p in ALL_POLICIES]}")
