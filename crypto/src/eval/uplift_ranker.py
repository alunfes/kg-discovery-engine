"""H3: Uplift-aware ranking.

Integrates four signals into a final uplift_aware_score:
  1. normalized_meta_score     (F2 within-branch z-score)
  2. conflict_adjusted_score   (G1 contradiction penalty applied)
  3. uplift_over_matched_baseline (G3 raw uplift vs comparator pool)
  4. complexity_adjusted_uplift (G3 uplift penalised by evidence count)

Default weights (sum to 1.0):
  norm_meta:       0.20
  conflict_adj:    0.30
  uplift_baseline: 0.30
  complexity_adj:  0.20

Scoring philosophy:
  - Boilerplate-strong hypotheses (high raw, near-zero uplift) are demoted.
  - Modest-raw hypotheses with strong baseline uplift are rescued.
  - border-case (soft_gated) hypotheses benefit if their uplift is high.
"""

# ---------------------------------------------------------------------------
# Default weights
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS: dict[str, float] = {
    "norm_meta": 0.20,
    "conflict_adj": 0.30,
    "uplift_baseline": 0.30,
    "complexity_adj": 0.20,
}


def _safe_get(d: dict, key: str, default: float = 0.0) -> float:
    """Get float from dict, returning default if missing or None."""
    v = d.get(key)
    return float(v) if v is not None else default


def _normalize_to_unit(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a dict of floats to [0, 1]."""
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    span = hi - lo
    if span < 1e-9:
        return {k: 0.5 for k in values}
    return {k: round((v - lo) / span, 4) for k, v in values.items()}


def _card_branch(tags: list[str]) -> str:
    """Canonical branch label from card tags."""
    tag_set = set(tags)
    if "E1" in tag_set or "beta_reversion" in tag_set:
        return "beta_reversion"
    if "E2" in tag_set or "positioning_unwind" in tag_set:
        return "positioning_unwind"
    if "E4" in tag_set or "null_baseline" in tag_set:
        return "null_baseline"
    return "other"


def _build_score_vectors(
    cards: list,
    contradiction_metrics: dict,
    meta_scores: dict,
    baseline_pool: dict,
) -> dict[str, dict]:
    """Build per-card score vectors for the four uplift-aware components.

    Returns dict: card_id → {norm_meta, conflict_adj, uplift_baseline, complexity_adj}.
    """
    pool_items = {
        d["card_id"]: d for d in baseline_pool.get("top_uplift", [])
    } if baseline_pool else {}
    global_baseline = _safe_get(baseline_pool or {}, "global_baseline_score", 0.62)

    vectors: dict[str, dict] = {}
    for card in cards:
        cid = card.card_id
        cm = contradiction_metrics.get(cid, {})
        conflict_score = _safe_get(cm, "net_support_minus_contradiction",
                                   card.composite_score)
        meta = meta_scores.get(cid, card.composite_score)
        pool_item = pool_items.get(cid, {})
        raw_uplift = _safe_get(pool_item, "uplift_over_matched_baseline",
                               card.composite_score - global_baseline)
        comp_adj = _safe_get(pool_item, "complexity_adjusted_uplift", raw_uplift)
        vectors[cid] = {
            "norm_meta": float(meta),
            "conflict_adj": float(conflict_score),
            "uplift_baseline": float(raw_uplift),
            "complexity_adj": float(comp_adj),
        }
    return vectors


def _compute_uplift_aware_score(
    vec: dict,
    norm_vec: dict,
    weights: dict,
) -> float:
    """Weighted sum of normalized uplift-aware components.

    Args:
        vec: Raw component values (for sign-correct uplift).
        norm_vec: Min-max-normalized component values.
        weights: Per-component weights (must sum to 1.0).

    Returns:
        Float in [0, 1].
    """
    score = (
        weights["norm_meta"] * norm_vec.get("norm_meta", 0.5)
        + weights["conflict_adj"] * norm_vec.get("conflict_adj", 0.5)
        + weights["uplift_baseline"] * norm_vec.get("uplift_baseline", 0.5)
        + weights["complexity_adj"] * norm_vec.get("complexity_adj", 0.5)
    )
    return round(min(1.0, max(0.0, score)), 4)


def compute_uplift_aware_ranking(
    cards: list,
    contradiction_metrics: dict,
    meta_scores: dict,
    baseline_pool: dict,
    top_k: int,
    weights: dict | None = None,
) -> dict:
    """H3: Compute uplift-aware final ranking integrating all four signals.

    Args:
        cards: HypothesisCard list.
        contradiction_metrics: G1 per-card contradiction metrics.
        meta_scores: F2 card_id → meta_score mapping.
        baseline_pool: G3 matched_baseline_pool dict.
        top_k: k for top-k statistics.
        weights: Optional override for component weights.

    Returns:
        Dict with uplift_ranked_cards, uplift_aware_summary,
        rescued_hypotheses, demoted_hypotheses.
    """
    w = {**_DEFAULT_WEIGHTS, **(weights or {})}
    vectors = _build_score_vectors(cards, contradiction_metrics, meta_scores, baseline_pool)

    # Normalize each component across the card set
    component_normed: dict[str, dict] = {}
    for comp in ["norm_meta", "conflict_adj", "uplift_baseline", "complexity_adj"]:
        raw_vals = {cid: v[comp] for cid, v in vectors.items()}
        component_normed[comp] = _normalize_to_unit(raw_vals)

    # Compute final uplift_aware_score per card
    ranked_entries: list[dict] = []
    for card in cards:
        cid = card.card_id
        norm_vec = {c: component_normed[c].get(cid, 0.5) for c in component_normed}
        ua_score = _compute_uplift_aware_score(vectors[cid], norm_vec, w)
        ranked_entries.append({
            "card_id": cid,
            "title": card.title[:70],
            "branch": _card_branch(card.tags),
            "raw_score": card.composite_score,
            "norm_meta_score": round(vectors[cid]["norm_meta"], 4),
            "conflict_adjusted_score": round(vectors[cid]["conflict_adj"], 4),
            "uplift_over_matched_baseline": round(vectors[cid]["uplift_baseline"], 4),
            "complexity_adjusted_uplift": round(vectors[cid]["complexity_adj"], 4),
            "uplift_aware_score": ua_score,
            "is_soft_gated": "soft_gated" in getattr(card, "tags", []),
        })

    raw_ranked = sorted(cards, key=lambda c: c.composite_score, reverse=True)
    raw_rank_map = {c.card_id: i + 1 for i, c in enumerate(raw_ranked)}
    ua_sorted = sorted(ranked_entries, key=lambda d: d["uplift_aware_score"], reverse=True)
    for i, entry in enumerate(ua_sorted):
        entry["uplift_aware_rank"] = i + 1
        entry["raw_rank"] = raw_rank_map.get(entry["card_id"], 0)
        entry["rank_delta"] = entry["raw_rank"] - entry["uplift_aware_rank"]

    raw_top_k_ids = {c.card_id for i, c in enumerate(raw_ranked) if i < top_k}
    ua_top_k_ids = {d["card_id"] for d in ua_sorted[:top_k]}
    rescued = [d for d in ua_sorted[:top_k] if d["card_id"] not in raw_top_k_ids]
    demoted = [d for d in ua_sorted if d["raw_rank"] <= top_k
               and d["card_id"] not in ua_top_k_ids]
    demoted.sort(key=lambda d: d["rank_delta"])

    return {
        "uplift_ranked_cards": ua_sorted,
        "uplift_aware_summary": {
            "n_rescued": len(rescued),
            "n_demoted": len(demoted),
            "n_top_k_changed": len(raw_top_k_ids.symmetric_difference(ua_top_k_ids)) // 2,
            "mean_ua_score": round(
                sum(d["uplift_aware_score"] for d in ranked_entries) / max(len(ranked_entries), 1),
                4,
            ),
            "weights": w,
        },
        "rescued_hypotheses": rescued[:5],
        "demoted_hypotheses": demoted[:5],
    }
