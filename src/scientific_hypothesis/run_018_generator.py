"""
run_018_generator.py — Investigability replication experiment hypothesis generation.

Generates N=70 per method (C2, C1, C_rand_v2) = 210 total hypotheses.

Design:
  - C2 (multi_op): 50 from run_017 + 20 new cross-domain hypotheses
  - C1 (single_op): 50 from run_017 + 20 new bio-only hypotheses
  - C_rand_v2: 70 truly random cross-domain pairs (same pool, same blacklist)

Purpose: Replicate SC-3r (investigability PASS, p=0.0007) with larger N.
NOT intended to rescue SC-1r (novel_supported_rate FAIL in run_017).

Constraints: Python stdlib only, seed=42.
Output: runs/run_018_investigability_replication/
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime
from typing import Any

SEED = 42
random.seed(SEED)

RUN_ID = "run_018_investigability_replication"
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_DIR = os.path.join(BASE_DIR, "runs", RUN_ID)

# ── import v2 pools ─────────────────────────────────────────────────────────────
# Re-use node pools and blacklists from randomized_baseline_v2
# (importing from same package)
import sys
sys.path.insert(0, BASE_DIR)

from src.scientific_hypothesis.randomized_baseline_v2 import (
    BIO_NODES, CHEM_NODES, NODE_LABEL,
    KG_DIRECT_EDGES, TRIVIALLY_KNOWN,
    _C2_RAW as _C2_RAW_50,
    _C1_RAW as _C1_RAW_50,
    _raw_to_hyp, _generate_crand_v2_pool,
)

# ── 20 new C2 hypotheses (H3051-H3070) ──────────────────────────────────────────

_C2_NEW_20: list[tuple[str, str, str, list[str], str]] = [
    ("H3051", "chem:drug:dasatinib", "bio:disease:alzheimers",
     ["chem:drug:dasatinib", "inhibits", "chem:target:bcl2_protein",
      "modulates", "bio:pathway:apoptosis", "reduces", "bio:disease:alzheimers"],
     "Dasatinib may reduce Alzheimer's Disease via BCL-2 and apoptosis modulation"),
    ("H3052", "chem:drug:dasatinib", "bio:process:cell_senescence",
     ["chem:drug:dasatinib", "inhibits", "chem:target:bcl2_protein",
      "clears", "bio:process:cell_senescence"],
     "Dasatinib may clear senescent cells via BCL-2 inhibition"),
    ("H3053", "chem:drug:lithium", "bio:disease:alzheimers",
     ["chem:drug:lithium", "inhibits", "chem:mechanism:wnt_inhibition",
      "activates", "bio:pathway:wnt_signaling",
      "reduces", "bio:process:tau_hyperphosphorylation",
      "attenuates", "bio:disease:alzheimers"],
     "Lithium may attenuate Alzheimer's Disease via Wnt pathway and tau reduction"),
    ("H3054", "chem:drug:lithium", "bio:disease:huntingtons",
     ["chem:drug:lithium", "activates", "bio:pathway:autophagy",
      "clears", "bio:process:protein_aggregation",
      "attenuates", "bio:disease:huntingtons"],
     "Lithium may attenuate Huntington's Disease via autophagy-mediated aggregation clearance"),
    ("H3055", "chem:compound:egcg", "bio:disease:alzheimers",
     ["chem:compound:egcg", "inhibits", "chem:target:bace1_enzyme",
      "reduces", "bio:pathway:amyloid_cascade",
      "attenuates", "bio:disease:alzheimers"],
     "EGCG may attenuate Alzheimer's Disease via BACE1 inhibition"),
    ("H3056", "chem:compound:egcg", "bio:pathway:neuroinflammation",
     ["chem:compound:egcg", "produces", "chem:mechanism:nrf2_activation",
      "suppresses", "bio:pathway:nfkb_signaling",
      "reduces", "bio:pathway:neuroinflammation"],
     "EGCG may reduce Neuroinflammation via NRF2-NF-kB axis"),
    ("H3057", "chem:compound:curcumin", "bio:disease:parkinsons",
     ["chem:compound:curcumin", "inhibits", "chem:mechanism:stat3_inhibition",
      "reduces", "bio:process:oxidative_stress",
      "attenuates", "bio:disease:parkinsons"],
     "Curcumin may attenuate Parkinson's Disease via STAT3-oxidative stress"),
    ("H3058", "chem:compound:curcumin", "bio:disease:glioblastoma",
     ["chem:compound:curcumin", "produces", "chem:mechanism:stat3_inhibition",
      "suppresses", "bio:pathway:pi3k_akt",
      "attenuates", "bio:disease:glioblastoma"],
     "Curcumin may suppress Glioblastoma via STAT3-PI3K-AKT axis"),
    ("H3059", "chem:mechanism:hdac_inhibition", "bio:disease:glioblastoma",
     ["chem:mechanism:hdac_inhibition", "reverses", "bio:process:epigenetic_silencing",
      "activates", "bio:pathway:p53_pathway",
      "suppresses", "bio:disease:glioblastoma"],
     "HDAC Inhibition may suppress Glioblastoma via epigenetic de-repression of p53"),
    ("H3060", "chem:mechanism:hdac_inhibition", "bio:process:neurodegeneration",
     ["chem:mechanism:hdac_inhibition", "activates", "bio:protein:bdnf",
      "reduces", "bio:process:neurodegeneration"],
     "HDAC Inhibition may reduce Neurodegeneration via BDNF upregulation"),
    ("H3061", "chem:drug:gefitinib", "bio:disease:breast_cancer",
     ["chem:drug:gefitinib", "inhibits", "chem:target:egfr_kinase",
      "suppresses", "bio:pathway:mapk_erk",
      "attenuates", "bio:disease:breast_cancer"],
     "Gefitinib may attenuate Breast Cancer via EGFR-MAPK-ERK suppression"),
    ("H3062", "chem:compound:berberine", "bio:disease:huntingtons",
     ["chem:compound:berberine", "produces", "chem:mechanism:ampk_activation",
      "activates", "bio:pathway:autophagy",
      "clears", "bio:disease:huntingtons"],
     "Berberine may attenuate Huntington's Disease via AMPK-autophagy axis"),
    ("H3063", "chem:compound:berberine", "bio:process:cell_senescence",
     ["chem:compound:berberine", "produces", "chem:mechanism:ampk_activation",
      "delays", "bio:process:cell_senescence"],
     "Berberine may delay Cell Senescence via AMPK activation"),
    ("H3064", "chem:mechanism:bcl2_inhibition", "bio:disease:leukemia_cml",
     ["chem:mechanism:bcl2_inhibition", "activates", "bio:pathway:apoptosis",
      "suppresses", "bio:disease:leukemia_cml"],
     "BCL-2 Inhibition may suppress CML Leukemia via apoptosis activation"),
    ("H3065", "chem:mechanism:vegfr_inhibition", "bio:disease:glioblastoma",
     ["chem:mechanism:vegfr_inhibition", "reduces", "bio:process:tumor_angiogenesis",
      "attenuates", "bio:disease:glioblastoma"],
     "VEGFR Inhibition may attenuate Glioblastoma via tumor angiogenesis suppression"),
    ("H3066", "chem:compound:kaempferol", "bio:disease:breast_cancer",
     ["chem:compound:kaempferol", "produces", "chem:mechanism:pi3k_inhibition",
      "suppresses", "bio:pathway:pi3k_akt",
      "attenuates", "bio:disease:breast_cancer"],
     "Kaempferol may attenuate Breast Cancer via PI3K-AKT suppression"),
    ("H3067", "chem:compound:resveratrol", "bio:disease:parkinsons",
     ["chem:compound:resveratrol", "produces", "chem:mechanism:sirt1_activation",
      "reduces", "bio:process:oxidative_stress",
      "attenuates", "bio:disease:parkinsons"],
     "Resveratrol may attenuate Parkinson's Disease via SIRT1-oxidative stress axis"),
    ("H3068", "chem:drug:sildenafil", "bio:disease:parkinsons",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "reduces", "bio:pathway:neuroinflammation",
      "attenuates", "bio:disease:parkinsons"],
     "Sildenafil may attenuate Parkinson's Disease via PDE5-neuroinflammation axis"),
    ("H3069", "chem:drug:hydroxychloroquine", "bio:disease:glioblastoma",
     ["chem:drug:hydroxychloroquine", "inhibits", "chem:target:mtor_kinase",
      "suppresses", "bio:pathway:pi3k_akt",
      "attenuates", "bio:disease:glioblastoma"],
     "Hydroxychloroquine may attenuate Glioblastoma via mTOR-PI3K-AKT suppression"),
    ("H3070", "chem:compound:coenzyme_q10", "bio:disease:heart_failure",
     ["chem:compound:coenzyme_q10", "reduces", "bio:process:oxidative_stress",
      "reduces", "bio:process:mitophagy",
      "improves", "bio:disease:heart_failure"],
     "Coenzyme Q10 may improve Heart Failure via oxidative stress and mitophagy"),
]

# ── 20 new C1 hypotheses (H4051-H4070) ──────────────────────────────────────────

_C1_NEW_20: list[tuple[str, str, str, list[str], str]] = [
    ("H4051", "bio:protein:ampk_alpha", "bio:disease:nafld",
     ["bio:protein:ampk_alpha", "activates", "bio:pathway:ampk_pathway",
      "reduces", "bio:process:insulin_resistance",
      "ameliorates", "bio:disease:nafld"],
     "AMPK-alpha may ameliorate NAFLD via AMPK-insulin resistance axis"),
    ("H4052", "bio:protein:sirt1", "bio:process:cell_senescence",
     ["bio:protein:sirt1", "deacetylates", "bio:protein:p53",
      "delays", "bio:process:cell_senescence"],
     "SIRT1 may delay Cell Senescence via p53 deacetylation"),
    ("H4053", "bio:protein:nrf2", "bio:disease:alzheimers",
     ["bio:protein:nrf2", "reduces", "bio:process:oxidative_stress",
      "attenuates", "bio:disease:alzheimers"],
     "NRF2 may attenuate Alzheimer's Disease via oxidative stress reduction"),
    ("H4054", "bio:protein:nrf2", "bio:disease:parkinsons",
     ["bio:protein:nrf2", "reduces", "bio:process:oxidative_stress",
      "protects", "bio:disease:parkinsons"],
     "NRF2 may protect against Parkinson's Disease via oxidative stress reduction"),
    ("H4055", "bio:pathway:mapk_erk", "bio:disease:prostate_cancer",
     ["bio:pathway:mapk_erk", "promotes", "bio:process:tumor_angiogenesis",
      "supports", "bio:disease:prostate_cancer"],
     "MAPK-ERK may support Prostate Cancer via tumor angiogenesis"),
    ("H4056", "bio:pathway:mapk_erk", "bio:disease:lung_cancer",
     ["bio:pathway:mapk_erk", "promotes", "bio:disease:lung_cancer"],
     "MAPK-ERK pathway may promote Lung Cancer"),
    ("H4057", "bio:pathway:jak_stat", "bio:disease:lung_cancer",
     ["bio:pathway:jak_stat", "activates", "bio:protein:stat3",
      "promotes", "bio:disease:lung_cancer"],
     "JAK-STAT may promote Lung Cancer via STAT3 activation"),
    ("H4058", "bio:pathway:hedgehog_signaling", "bio:disease:breast_cancer",
     ["bio:pathway:hedgehog_signaling", "activates", "bio:pathway:pi3k_akt",
      "promotes", "bio:disease:breast_cancer"],
     "Hedgehog Signaling may promote Breast Cancer via PI3K-AKT"),
    ("H4059", "bio:protein:hdac1", "bio:disease:glioblastoma",
     ["bio:protein:hdac1", "mediates", "bio:process:epigenetic_silencing",
      "silences", "bio:pathway:p53_pathway",
      "supports", "bio:disease:glioblastoma"],
     "HDAC1 may support Glioblastoma via epigenetic silencing of p53 pathway"),
    ("H4060", "bio:protein:gsk3b", "bio:disease:type2_diabetes",
     ["bio:protein:gsk3b", "inhibits", "bio:pathway:ampk_pathway",
      "promotes", "bio:disease:type2_diabetes"],
     "GSK3-beta may promote Type 2 Diabetes via AMPK pathway inhibition"),
    ("H4061", "bio:process:mitophagy", "bio:disease:parkinsons",
     ["bio:process:mitophagy", "clears", "bio:process:oxidative_stress",
      "protects_against", "bio:disease:parkinsons"],
     "Mitophagy dysfunction may worsen Parkinson's Disease via oxidative stress"),
    ("H4062", "bio:process:mitophagy", "bio:disease:heart_failure",
     ["bio:process:mitophagy", "maintains", "bio:process:cell_senescence",
      "reduces", "bio:disease:heart_failure"],
     "Mitophagy may protect against Heart Failure via senescent cell clearance"),
    ("H4063", "bio:pathway:ubiquitin_proteasome", "bio:disease:alzheimers",
     ["bio:pathway:ubiquitin_proteasome", "impaired_in", "bio:process:protein_aggregation",
      "drives", "bio:disease:alzheimers"],
     "Ubiquitin-Proteasome dysfunction may drive Alzheimer's Disease"),
    ("H4064", "bio:pathway:p53_pathway", "bio:disease:prostate_cancer",
     ["bio:pathway:p53_pathway", "suppresses", "bio:disease:prostate_cancer"],
     "p53 Pathway may suppress Prostate Cancer"),
    ("H4065", "bio:protein:cdk4", "bio:disease:prostate_cancer",
     ["bio:protein:cdk4", "promotes", "bio:disease:prostate_cancer"],
     "CDK4 may promote Prostate Cancer"),
    ("H4066", "bio:protein:pten", "bio:disease:breast_cancer",
     ["bio:protein:pten", "suppresses", "bio:pathway:pi3k_akt",
      "inhibits", "bio:disease:breast_cancer"],
     "PTEN may suppress Breast Cancer via PI3K-AKT inhibition"),
    ("H4067", "bio:protein:stat3", "bio:disease:glioblastoma",
     ["bio:protein:stat3", "activates", "bio:pathway:jak_stat",
      "promotes", "bio:disease:glioblastoma"],
     "STAT3 may promote Glioblastoma via JAK-STAT activation"),
    ("H4068", "bio:process:epigenetic_silencing", "bio:disease:lung_cancer",
     ["bio:process:epigenetic_silencing", "silences", "bio:protein:pten",
      "activates", "bio:pathway:pi3k_akt",
      "promotes", "bio:disease:lung_cancer"],
     "Epigenetic Silencing may promote Lung Cancer via PTEN silencing"),
    ("H4069", "bio:pathway:wnt_signaling", "bio:disease:prostate_cancer",
     ["bio:pathway:wnt_signaling", "activates", "bio:protein:cdk4",
      "promotes", "bio:disease:prostate_cancer"],
     "Wnt Signaling may promote Prostate Cancer via CDK4 activation"),
    ("H4070", "bio:process:tau_hyperphosphorylation", "bio:disease:parkinsons",
     ["bio:process:tau_hyperphosphorylation", "drives",
      "bio:process:protein_aggregation",
      "worsens", "bio:disease:parkinsons"],
     "Tau Hyperphosphorylation may worsen Parkinson's Disease via protein aggregation"),
]


# ── build functions ─────────────────────────────────────────────────────────────

def build_c2_70() -> list[dict[str, Any]]:
    """Build 70 C2 multi-op hypotheses (50 from run_017 + 20 new)."""
    raw_50 = list(_C2_RAW_50)
    raw_20 = list(_C2_NEW_20)
    all_raw = raw_50 + raw_20
    return [_raw_to_hyp(r, "C2_multi_op") for r in all_raw]


def build_c1_70() -> list[dict[str, Any]]:
    """Build 70 C1 single-op hypotheses (50 from run_017 + 20 new)."""
    raw_50 = list(_C1_RAW_50)
    raw_20 = list(_C1_NEW_20)
    all_raw = raw_50 + raw_20
    return [_raw_to_hyp(r, "C1_compose") for r in all_raw]


def build_crand_v2_70(rng: random.Random) -> list[dict[str, Any]]:
    """Build 70 C_rand_v2 hypotheses from the blacklisted pool."""
    # Extend blacklist to include new C2/C1 pairs
    extra_blacklist: set[tuple[str, str]] = {
        (r[1], r[2]) for r in _C2_NEW_20
    } | {
        (r[1], r[2]) for r in _C1_NEW_20
    }
    all_blacklisted = (
        KG_DIRECT_EDGES
        | TRIVIALLY_KNOWN
        | {(r[1], r[2]) for r in _C2_RAW_50}
        | {(r[1], r[2]) for r in _C1_RAW_50}
        | extra_blacklist
    )
    # Build fresh pool
    pool: list[tuple[str, str]] = []
    for c_id, _, _ in CHEM_NODES:
        for b_id, _, _ in BIO_NODES:
            if (c_id, b_id) not in all_blacklisted:
                pool.append((c_id, b_id))
    for b_id, _, _ in BIO_NODES:
        for c_id, _, _ in CHEM_NODES:
            if (b_id, c_id) not in all_blacklisted:
                pool.append((b_id, c_id))

    rng.shuffle(pool)
    selected = pool[:70]
    result: list[dict[str, Any]] = []
    for i, (subj, obj) in enumerate(selected):
        subj_label = NODE_LABEL.get(subj, subj.split(":")[-1])
        obj_label = NODE_LABEL.get(obj, obj.split(":")[-1])
        provenance = [subj, "randomly_paired_with", obj]
        result.append({
            "id": f"H5{i + 1:03d}",
            "subject_id": subj,
            "subject_label": subj_label,
            "relation": "randomly_paired_with",
            "object_id": obj,
            "object_label": obj_label,
            "description": (
                f"{subj_label} randomly paired with {obj_label} "
                "(no KG path — truly random cross-domain control)"
            ),
            "provenance": provenance,
            "operator": "random_v2",
            "source_kg_name": "random_entity_pool",
            "method": "C_rand_v2",
            "chain_length": len(provenance),
        })
    return result


# ── parity check ────────────────────────────────────────────────────────────────

def _parity_stats(pool: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Compute chain-length and domain-mix stats."""
    if not pool:
        return {"method": name, "count": 0}
    lengths = [h["chain_length"] for h in pool]
    cross = sum(
        1 for h in pool
        if (h["subject_id"].startswith("chem:") and h["object_id"].startswith("bio:"))
        or (h["subject_id"].startswith("bio:") and h["object_id"].startswith("chem:"))
    )
    return {
        "method": name,
        "count": len(pool),
        "avg_chain_length": round(sum(lengths) / len(lengths), 2),
        "min_chain_length": min(lengths),
        "max_chain_length": max(lengths),
        "cross_domain_count": cross,
        "cross_domain_ratio": round(cross / len(pool), 3),
    }


# ── I/O helpers ─────────────────────────────────────────────────────────────────

def _save_json(data: Any, path: str) -> None:
    """Write JSON to path, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


# ── main ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Generate 210 hypotheses (3 × 70) for run_018."""
    print(f"\n{'='*60}")
    print(f"  run_018_generator.py — investigability replication")
    print(f"  N=70 per method (C2/C1/C_rand_v2), seed={SEED}")
    print(f"  PURPOSE: SC-3r replication only. NOT SC-1r rescue.")
    print(f"{'='*60}")

    rng = random.Random(SEED)
    c2 = build_c2_70()
    c1 = build_c1_70()
    cr = build_crand_v2_70(rng)

    print(f"\n  C2:        {len(c2)} hypotheses")
    print(f"  C1:        {len(c1)} hypotheses")
    print(f"  C_rand_v2: {len(cr)} hypotheses")
    print(f"  Total:     {len(c2)+len(c1)+len(cr)}")

    os.makedirs(RUN_DIR, exist_ok=True)

    def p(fname: str) -> str:
        return os.path.join(RUN_DIR, fname)

    _save_json({"run_id": RUN_ID, "method": "C2_multi_op",
                "count": len(c2), "hypotheses": c2},
               p("hypotheses_c2.json"))
    _save_json({"run_id": RUN_ID, "method": "C1_compose",
                "count": len(c1), "hypotheses": c1},
               p("hypotheses_c1.json"))
    _save_json({"run_id": RUN_ID, "method": "C_rand_v2",
                "count": len(cr), "hypotheses": cr},
               p("hypotheses_crand_v2.json"))

    parity = {
        "C2": _parity_stats(c2, "C2_multi_op"),
        "C1": _parity_stats(c1, "C1_compose"),
        "C_rand_v2": _parity_stats(cr, "C_rand_v2"),
    }
    _save_json(parity, p("baseline_parity_check.json"))

    cfg = {
        "run_id": RUN_ID,
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Investigability replication: N=70 per method "
            "(50 from run_017 + 20 new). "
            "Purpose: replicate SC-3r (investigability PASS, p=0.0007). "
            "NOT intended to rescue SC-1r."
        ),
        "seed": SEED,
        "n_per_method": 70,
        "total": len(c2) + len(c1) + len(cr),
        "pre_registration": "configs/investigability_registry.json",
        "methods": {
            "C2_multi_op": {
                "description": "Multi-op cross-domain pipeline (align→compose)",
                "n": len(c2),
                "run_017_carry": 50,
                "new_018": 20,
            },
            "C1_compose": {
                "description": "Single-op bio-only compose",
                "n": len(c1),
                "run_017_carry": 50,
                "new_018": 20,
            },
            "C_rand_v2": {
                "description": "Truly random cross-domain pairs (blacklisted)",
                "n": len(cr),
                "run_017_carry": 50,
                "new_018": 20,
            },
        },
    }
    _save_json(cfg, p("run_config.json"))

    print(f"\n  C2 cross-domain ratio:  {parity['C2']['cross_domain_ratio']}")
    print(f"  C1 cross-domain ratio:  {parity['C1']['cross_domain_ratio']}")
    print(f"  CR cross-domain ratio:  {parity['C_rand_v2']['cross_domain_ratio']}")
    print(f"\n  Artifacts saved to {RUN_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
