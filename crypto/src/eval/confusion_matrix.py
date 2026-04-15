"""I3: Grammar confusion matrix.

Aggregates reroute records and suppression log entries to build three matrices
showing where branch grammar is most often misidentified or confused:

  1. original_branch × rerouted_branch matrix (primary confusion map)
  2. contradiction_type × rerouted_branch (which contradiction triggers which reroute)
  3. contradiction_location × rerouted_branch (chain proximity pattern)

Why a confusion matrix (not just summary counts):
  Summary counts hide asymmetry. Knowing that beta_reversion→positioning_unwind
  happens at proximity 0.85 (near-terminal) is more useful than knowing "12
  reroutes happened" — it tells us the grammar distinguisher is failing at the
  claim boundary, not in evidence gathering.

Inputs:
  reroute_candidates   — H2 reroute candidate list (original_branch, reroute_candidate_branch, ...)
  suppression_log      — chain grammar suppression log (chain, pair, reason, detail)
  contradiction_metrics — G1 per-card contradiction metrics (for severity/location context)
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Chain → contradiction_type mapping
# ---------------------------------------------------------------------------

_CHAIN_CONTRADICTION_TYPE: dict[str, str] = {
    "beta_reversion_no_funding_oi": "funding_oi_block",
    "beta_reversion_weak_premium": "premium_block",
    "beta_reversion_transient_aggr": "aggression_block",
    "positioning_unwind_funding_pressure": "funding_pressure_block",
    "positioning_unwind_oi_crowding": "oi_crowding_block",
    "positioning_unwind_premium_compress": "premium_compress_block",
}

# Chain → location label (which structural node the contradiction hits)
_CHAIN_LOCATION: dict[str, str] = {
    "beta_reversion_no_funding_oi": "terminal_gate",     # blocks recoupling node
    "beta_reversion_weak_premium": "mid_chain",          # premium check mid-path
    "beta_reversion_transient_aggr": "entry_evidence",   # aggression at chain start
    "positioning_unwind_funding_pressure": "funding_node",
    "positioning_unwind_oi_crowding": "oi_node",
    "positioning_unwind_premium_compress": "premium_node",
}


def _branch_from_chain(chain: str) -> str:
    """Map chain name to originating branch."""
    if "beta_reversion" in chain:
        return "beta_reversion"
    if "positioning_unwind" in chain:
        return "positioning_unwind"
    return "other"


def _contradiction_type(chain: str, detail: str) -> str:
    """Resolve contradiction type from chain name and detail string."""
    return _CHAIN_CONTRADICTION_TYPE.get(chain, f"other:{chain[:30]}")


def _contradiction_location(chain: str) -> str:
    """Structural location of the contradiction within the chain."""
    return _CHAIN_LOCATION.get(chain, "unknown")


# ---------------------------------------------------------------------------
# Matrix builders
# ---------------------------------------------------------------------------

def _increment(matrix: dict[str, dict[str, int]], row: str, col: str) -> None:
    """Increment matrix[row][col] by 1.

    Why two-step: Python evaluates the RHS before the LHS target is resolved,
    so a one-liner like `matrix.setdefault(row, {})[col] = matrix[row].get(...)`
    would raise KeyError because matrix[row] is accessed on the RHS before
    setdefault has a chance to insert the key.
    """
    matrix.setdefault(row, {})
    matrix[row][col] = matrix[row].get(col, 0) + 1


def build_branch_reroute_matrix(
    reroute_candidates: list[dict],
) -> dict[str, dict[str, int]]:
    """Matrix: original_branch → rerouted_branch → count.

    Each reroute record contributes one cell to the matrix.
    Confidence-weighted is NOT used here; the matrix shows raw frequency so
    that rare but high-confidence reroutes are not inflated.
    """
    matrix: dict[str, dict[str, int]] = {}
    for r in reroute_candidates:
        orig = r.get("original_branch", "unknown")
        dest = r.get("reroute_candidate_branch", "unknown")
        _increment(matrix, orig, dest)
    return matrix


def build_contradiction_type_matrix(
    reroute_candidates: list[dict],
    suppression_log: list[dict],
) -> dict[str, dict[str, int]]:
    """Matrix: contradiction_type × rerouted_branch → count.

    Joins reroute records with suppression log to identify which type of
    contradiction (funding_oi_block, premium_block, etc.) most often causes
    which reroute target branch.

    Why join on pair+branch (not card_id):
      Suppression log entries don't carry card_id — they are per-pair,
      per-chain grammar events. We join on pair+originating_branch.
    """
    # Build pair+branch → contradiction_type mapping from suppression log
    pair_branch_types: dict[tuple[str, str], list[str]] = {}
    for entry in suppression_log:
        if entry.get("reason") != "contradictory_evidence":
            continue
        chain = entry.get("chain", "")
        pair = entry.get("pair", "")
        orig_branch = _branch_from_chain(chain)
        c_type = _contradiction_type(chain, entry.get("detail", ""))
        pair_branch_types.setdefault((pair, orig_branch), []).append(c_type)

    matrix: dict[str, dict[str, int]] = {}
    for r in reroute_candidates:
        orig_branch = r.get("original_branch", "unknown")
        dest_branch = r.get("reroute_candidate_branch", "unknown")
        # Extract pair from original_title (reuse pair RE)
        import re as _re
        m = _re.search(r"\(([A-Z]+)[,/]([A-Z]+)\)", r.get("original_title", ""))
        pair = f"{m.group(1)}/{m.group(2)}" if m else ""
        types = pair_branch_types.get((pair, orig_branch), ["unknown"])
        for c_type in types:
            _increment(matrix, c_type, dest_branch)
    return matrix


def build_location_reroute_matrix(
    reroute_candidates: list[dict],
    suppression_log: list[dict],
) -> dict[str, dict[str, int]]:
    """Matrix: contradiction_location × rerouted_branch → count.

    Shows which structural location (terminal_gate, mid_chain, entry_evidence,
    funding_node, etc.) most often triggers reroutes to each branch.
    """
    # Build pair+branch → location list from suppression log
    import re as _re
    pair_branch_locations: dict[tuple[str, str], list[str]] = {}
    for entry in suppression_log:
        if entry.get("reason") != "contradictory_evidence":
            continue
        chain = entry.get("chain", "")
        pair = entry.get("pair", "")
        orig_branch = _branch_from_chain(chain)
        loc = _contradiction_location(chain)
        pair_branch_locations.setdefault((pair, orig_branch), []).append(loc)

    matrix: dict[str, dict[str, int]] = {}
    for r in reroute_candidates:
        orig_branch = r.get("original_branch", "unknown")
        dest_branch = r.get("reroute_candidate_branch", "unknown")
        m = _re.search(r"\(([A-Z]+)[,/]([A-Z]+)\)", r.get("original_title", ""))
        pair = f"{m.group(1)}/{m.group(2)}" if m else ""
        locations = pair_branch_locations.get((pair, orig_branch), ["unknown"])
        for loc in locations:
            _increment(matrix, loc, dest_branch)
    return matrix


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_confusion_matrix(
    reroute_candidates: list[dict],
    suppression_log: list[dict],
    contradiction_metrics: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """I3: Build all three grammar confusion matrices.

    Args:
        reroute_candidates: H2 reroute candidate list.
        suppression_log: Chain grammar suppression log.
        contradiction_metrics: Optional G1 per-card metrics (not currently used
            in matrix computation, reserved for future severity-weighted variant).

    Returns:
        Dict with:
          branch_reroute_matrix      — original → rerouted frequency
          contradiction_type_matrix  — c_type → rerouted frequency
          location_reroute_matrix    — location → rerouted frequency
          dominant_confusion_pairs   — top-5 most frequent branch→branch transitions
          interpretation             — human-readable summary lines
    """
    br_matrix = build_branch_reroute_matrix(reroute_candidates)
    ct_matrix = build_contradiction_type_matrix(reroute_candidates, suppression_log)
    loc_matrix = build_location_reroute_matrix(reroute_candidates, suppression_log)

    # Find dominant confusion pairs (original → rerouted, sorted by count)
    dominant: list[dict] = []
    for orig, dests in br_matrix.items():
        for dest, count in dests.items():
            dominant.append({"from": orig, "to": dest, "count": count})
    dominant.sort(key=lambda d: d["count"], reverse=True)

    # Build interpretation lines
    interp: list[str] = []
    if dominant:
        top = dominant[0]
        interp.append(
            f"Most common grammar confusion: {top['from']} → {top['to']} "
            f"({top['count']} reroutes)"
        )
    for ct, dests in sorted(ct_matrix.items()):
        top_dest = max(dests, key=dests.get, default=None)
        if top_dest:
            interp.append(
                f"  {ct} most often reroutes to {top_dest} (n={dests[top_dest]})"
            )
    for loc, dests in sorted(loc_matrix.items()):
        top_dest = max(dests, key=dests.get, default=None)
        if top_dest:
            interp.append(
                f"  contradiction at {loc} most often reroutes to {top_dest}"
            )

    return {
        "branch_reroute_matrix": br_matrix,
        "contradiction_type_matrix": ct_matrix,
        "location_reroute_matrix": loc_matrix,
        "dominant_confusion_pairs": dominant[:5],
        "interpretation": interp,
    }
