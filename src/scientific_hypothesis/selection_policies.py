"""
Density-aware hypothesis selection policies for KG Discovery Engine.

Implements 6 concrete policies for selecting hypothesis candidates
from a pool with varying literature density characteristics.
"""
from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from typing import Any


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class DensityPolicy(ABC):
    """Abstract base for density-aware hypothesis selection policies."""

    name: str
    params: dict

    @abstractmethod
    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Select n candidates from pool.

        Each candidate must have: 'min_density', 'log_min_density', 'investigated'.

        Args:
            candidates: Pool of hypothesis dicts.
            n: Number of candidates to select.
            seed: Random seed for reproducibility.

        Returns:
            Selected list of up to n candidates.
        """
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> dict:
        """Return policy description with formula, hyperparams, strengths, failure_modes.

        Returns:
            Dict with keys: name, formula, hyperparams, strengths, failure_modes, use_case.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def weighted_sample_without_replacement(
    items: list[dict], weights: list[float], k: int, rng: random.Random
) -> list[dict]:
    """Weighted reservoir sampling without replacement (Efraimidis-Spirakis A-Res).

    Args:
        items: Items to sample from.
        weights: Non-negative weight per item (must be same length).
        k: Number of items to select.
        rng: Seeded Random instance.

    Returns:
        Up to k selected items.
    """
    if k <= 0:
        return []
    heap: list[tuple[float, int]] = []
    for i, w in enumerate(weights):
        if w <= 0:
            continue
        key = rng.random() ** (1.0 / w)
        if len(heap) < k:
            heap.append((key, i))
            if len(heap) == k:
                heap.sort()
        elif key > heap[0][0]:
            heap[0] = (key, i)
            heap.sort()
    selected_indices = [idx for _, idx in heap]
    return [items[i] for i in selected_indices]


# ---------------------------------------------------------------------------
# Policy 1: Uniform (baseline)
# ---------------------------------------------------------------------------

class UniformPolicy(DensityPolicy):
    """Baseline: random sample without replacement, P(select)=1/N."""

    name = "uniform"
    params: dict = {}

    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Uniformly random sample of n candidates."""
        rng = random.Random(seed)
        pool = list(candidates)
        rng.shuffle(pool)
        return pool[:n]

    def describe(self) -> dict:
        return {
            "name": self.name,
            "formula": "P(select_i) = 1/N for all i",
            "hyperparams": {},
            "strengths": [
                "Unbiased density distribution",
                "Simple to implement and interpret",
                "No hyperparameter tuning required",
            ],
            "failure_modes": [
                "Inherits density mismatch from pool composition",
                "Low-density candidates may dominate if pool is skewed",
                "Does not maximize investigability",
            ],
            "use_case": "Baseline comparison; unbiased coverage of pool distribution",
        }


# ---------------------------------------------------------------------------
# Policy 2: Hard Threshold
# ---------------------------------------------------------------------------

class HardThresholdPolicy(DensityPolicy):
    """Select only candidates with min_density >= tau; random within eligible."""

    name = "hard_threshold"

    def __init__(self, tau: float = 7500.0) -> None:
        self.params = {"tau": tau}
        self.tau = tau

    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Select n from candidates with min_density >= tau."""
        rng = random.Random(seed)
        eligible = [c for c in candidates if c.get("min_density", 0) >= self.tau]
        rng.shuffle(eligible)
        return eligible[:n]

    def describe(self) -> dict:
        return {
            "name": self.name,
            "formula": f"Select c iff min_density >= tau={self.tau}; uniform from eligible",
            "hyperparams": {"tau": self.tau},
            "strengths": [
                "Eliminates low-density failures entirely",
                "Maximizes expected investigability",
                "Interpretable hard cutoff",
            ],
            "failure_modes": [
                "Discards potentially valuable low-density discoveries",
                "Reduces pool size; may return fewer than n if pool is sparse",
                "Tau choice is binary — no gradient near boundary",
            ],
            "use_case": "Production pipelines where investigability is the primary KPI",
        }


# ---------------------------------------------------------------------------
# Policy 3: Soft Weighting
# ---------------------------------------------------------------------------

class SoftWeightingPolicy(DensityPolicy):
    """P(select_i) proportional to sigmoid(k*(log_density_i - log_tau))."""

    name = "soft_weighting"

    def __init__(self, k: float = 3.0, tau: float = 7500.0) -> None:
        self.params = {"k": k, "tau": tau}
        self.k = k
        self.tau = tau

    def _sigmoid(self, x: float) -> float:
        """Numerically stable sigmoid."""
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        e = math.exp(x)
        return e / (1.0 + e)

    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Weighted sample where weight = sigmoid(k*(log_d - log_tau))."""
        rng = random.Random(seed)
        log_tau = math.log10(self.tau) if self.tau > 0 else 0.0
        weights = [
            self._sigmoid(self.k * (c.get("log_min_density", 0.0) - log_tau))
            for c in candidates
        ]
        return weighted_sample_without_replacement(candidates, weights, n, rng)

    def describe(self) -> dict:
        return {
            "name": self.name,
            "formula": (
                f"w_i = sigmoid({self.k} * (log10(min_density_i) - log10({self.tau}))); "
                "sample without replacement proportional to w_i"
            ),
            "hyperparams": {"k": self.k, "tau": self.tau},
            "strengths": [
                "Smooth transition around threshold — no hard cutoff",
                "Retains some low-density exposure for novelty",
                "Differentiable weighting scheme",
            ],
            "failure_modes": [
                "Hyperparameter sensitivity (k controls sharpness)",
                "Implicit threshold — harder to audit than hard cutoff",
                "Very low-density candidates still get small but nonzero weight",
            ],
            "use_case": "Balanced exploration/exploitation when some low-density novelty is desired",
        }


# ---------------------------------------------------------------------------
# Policy 4: Two-Mode (Exploit + Explore)
# ---------------------------------------------------------------------------

class TwoModePolicy(DensityPolicy):
    """Explicit exploitation/exploration split by density threshold."""

    name = "two_mode"

    def __init__(self, lambda_exploit: float = 0.7, tau: float = 7500.0) -> None:
        self.params = {"lambda_exploit": lambda_exploit, "tau": tau}
        self.lambda_exploit = lambda_exploit
        self.tau = tau

    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Select floor(lambda*n) high-density + ceil((1-lambda)*n) low-density."""
        rng = random.Random(seed)
        high = [c for c in candidates if c.get("min_density", 0) >= self.tau]
        low = [c for c in candidates if c.get("min_density", 0) < self.tau]
        rng.shuffle(high)
        rng.shuffle(low)
        n_high = math.floor(self.lambda_exploit * n)
        n_low = math.ceil((1.0 - self.lambda_exploit) * n)
        selected = high[:n_high] + low[:n_low]
        return selected[:n]

    def describe(self) -> dict:
        return {
            "name": self.name,
            "formula": (
                f"n_high = floor({self.lambda_exploit}*n) from min_density >= {self.tau}; "
                f"n_low = ceil({1-self.lambda_exploit}*n) from min_density < {self.tau}"
            ),
            "hyperparams": {"lambda_exploit": self.lambda_exploit, "tau": self.tau},
            "strengths": [
                "Explicit exploration budget — interpretable",
                "Guarantees representation from both density regimes",
                "Lambda is a directly tunable dial",
            ],
            "failure_modes": [
                "Requires sufficient candidates in both pools",
                "Fixed ratio may not match pool composition",
                "Hard boundary at tau same as HardThreshold",
            ],
            "use_case": "Explicit trade-off between investigability and novelty retention",
        }


# ---------------------------------------------------------------------------
# Policy 5: Quartile Constrained
# ---------------------------------------------------------------------------

class QuantileConstrainedPolicy(DensityPolicy):
    """Divide into 4 quartiles by min_density; sample n//4 from each."""

    name = "quantile_constrained"

    def __init__(self, n_quartiles: int = 4) -> None:
        self.params = {"n_quartiles": n_quartiles}
        self.n_quartiles = n_quartiles

    def _quartile_boundaries(self, densities: list[float]) -> list[float]:
        """Compute n_quartiles-1 boundary values."""
        sorted_d = sorted(densities)
        m = len(sorted_d)
        bounds = []
        for q in range(1, self.n_quartiles):
            idx = int(m * q / self.n_quartiles)
            bounds.append(sorted_d[min(idx, m - 1)])
        return bounds

    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Sample approx n//n_quartiles from each density quartile."""
        rng = random.Random(seed)
        densities = [c.get("min_density", 0) for c in candidates]
        bounds = self._quartile_boundaries(densities)
        buckets: list[list[dict]] = [[] for _ in range(self.n_quartiles)]
        for c in candidates:
            d = c.get("min_density", 0)
            assigned = self.n_quartiles - 1
            for qi, b in enumerate(bounds):
                if d <= b:
                    assigned = qi
                    break
            buckets[assigned].append(c)
        base = n // self.n_quartiles
        remainder = n % self.n_quartiles
        selected: list[dict] = []
        for qi, bucket in enumerate(buckets):
            rng.shuffle(bucket)
            k = base + (1 if qi < remainder else 0)
            selected.extend(bucket[:k])
        return selected

    def describe(self) -> dict:
        return {
            "name": self.name,
            "formula": (
                f"Divide into {self.n_quartiles} quartiles by min_density; "
                "sample n//{self.n_quartiles} (+1 for first r buckets) from each"
            ),
            "hyperparams": {"n_quartiles": self.n_quartiles},
            "strengths": [
                "Guarantees density diversity across quartiles",
                "Prevents extreme density skew in selection",
                "Self-adapting boundaries — no manual tau",
            ],
            "failure_modes": [
                "May force selection from very sparse Q1 candidates",
                "Does not maximize investigability",
                "Boundaries depend on pool composition",
            ],
            "use_case": "Diversity-maximizing selection when density range is wide",
        }


# ---------------------------------------------------------------------------
# Policy 6: Diversity Guarded
# ---------------------------------------------------------------------------

class DiversityGuardedPolicy(DensityPolicy):
    """Hard floor on density + greedy diversity maximization in log-density space."""

    name = "diversity_guarded"

    def __init__(self, tau_floor: float = 3500.0, diversity_weight: float = 0.5) -> None:
        self.params = {"tau_floor": tau_floor, "diversity_weight": diversity_weight}
        self.tau_floor = tau_floor
        self.diversity_weight = diversity_weight

    def select(self, candidates: list[dict], n: int, seed: int = 42) -> list[dict]:
        """Apply floor, then greedily maximize density diversity."""
        rng = random.Random(seed)
        eligible = [c for c in candidates if c.get("min_density", 0) >= self.tau_floor]
        if not eligible:
            return []
        log_densities = [c.get("log_min_density", 0.0) for c in eligible]
        max_log = max(log_densities) if log_densities else 1.0
        min_log = min(log_densities) if log_densities else 0.0
        span = max_log - min_log if max_log != min_log else 1.0
        remaining = list(range(len(eligible)))
        rng.shuffle(remaining)
        selected_logs: list[float] = []
        selected: list[dict] = []
        for _ in range(min(n, len(eligible))):
            best_idx, best_score = None, -1.0
            for i in remaining:
                log_d = log_densities[i]
                norm_log = (log_d - min_log) / span
                if selected_logs:
                    dist = min(abs(log_d - s) for s in selected_logs) / span
                else:
                    dist = 1.0
                dw = self.diversity_weight
                score = dw * dist + (1.0 - dw) * norm_log
                if score > best_score:
                    best_score = score
                    best_idx = i
            if best_idx is None:
                break
            selected.append(eligible[best_idx])
            selected_logs.append(log_densities[best_idx])
            remaining.remove(best_idx)
        return selected

    def describe(self) -> dict:
        return {
            "name": self.name,
            "formula": (
                f"Filter min_density >= {self.tau_floor}; greedy: "
                f"score_i = {self.diversity_weight}*min_dist_to_selected + "
                f"{1-self.diversity_weight}*norm_log_density"
            ),
            "hyperparams": {
                "tau_floor": self.tau_floor,
                "diversity_weight": self.diversity_weight,
            },
            "strengths": [
                "Maximizes density spread in selected set",
                "Avoids clustering at high-density ceiling",
                "Floor prevents extreme low-density failures",
            ],
            "failure_modes": [
                "Greedy algorithm — not globally optimal",
                "Computationally heavier (O(n*k) vs O(n))",
                "Floor may still admit borderline failures near tau_floor",
            ],
            "use_case": "Maximize density diversity while maintaining minimum quality floor",
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

POLICY_REGISTRY: dict[str, type[DensityPolicy]] = {
    "uniform": UniformPolicy,
    "hard_threshold": HardThresholdPolicy,
    "soft_weighting": SoftWeightingPolicy,
    "two_mode": TwoModePolicy,
    "quantile_constrained": QuantileConstrainedPolicy,
    "diversity_guarded": DiversityGuardedPolicy,
}


def get_policy(name: str, **kwargs: Any) -> DensityPolicy:
    """Instantiate a policy by name with optional hyperparameter overrides.

    Args:
        name: Policy name from POLICY_REGISTRY.
        **kwargs: Hyperparameter overrides passed to policy constructor.

    Returns:
        Instantiated DensityPolicy.

    Raises:
        KeyError: If name not in registry.
    """
    cls = POLICY_REGISTRY[name]
    return cls(**kwargs) if kwargs else cls()


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # Sample candidates with density fields
    sample_candidates = [
        {"id": f"H{i}", "min_density": d, "log_min_density": round(math.log10(d), 4),
         "investigated": int(d >= 7500), "description": f"Hypothesis {i}"}
        for i, d in enumerate([200, 500, 1200, 3000, 5500, 7500, 9000, 15000,
                                25000, 40000, 70000, 120000, 200000], start=1)
    ]

    print(f"Pool size: {len(sample_candidates)}")
    print(f"min_density range: "
          f"{min(c['min_density'] for c in sample_candidates)} – "
          f"{max(c['min_density'] for c in sample_candidates)}")
    print()

    policies = [
        UniformPolicy(),
        HardThresholdPolicy(tau=7500),
        SoftWeightingPolicy(k=3.0, tau=7500),
        TwoModePolicy(lambda_exploit=0.7, tau=7500),
        QuantileConstrainedPolicy(n_quartiles=4),
        DiversityGuardedPolicy(tau_floor=3500, diversity_weight=0.5),
    ]

    n_select = 6
    for policy in policies:
        selected = policy.select(sample_candidates, n_select, seed=42)
        densities = [c["min_density"] for c in selected]
        print(f"[{policy.name}] selected={len(selected)} densities={densities}")
        desc = policy.describe()
        print(f"  formula: {desc['formula']}")
        print()
