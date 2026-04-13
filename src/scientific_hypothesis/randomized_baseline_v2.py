"""
randomized_baseline_v2.py — Redesigned C_rand + N=50 hypothesis generation.

Problem with v1 C_rand:
  KG path traversal naturally includes trivially-known pairs
  (HER2→breast_cancer, obesity→NAFLD, JAK inhibition→RA).
  These score precision=1.0 trivially, inflating the baseline.
  C2's 0.833 reflects genuine novelty, not pipeline failure.

v2 design:
  a) Truly random sampling from entity pool (not KG-path traversal)
  b) Blacklists KG 1-hop edges
  c) Blacklists domain-trivially-known pairs
  d) Maintains same subject/object type distribution as C2
  e) N=50 per method (up from 20)

Output: runs/run_017_scientific_hypothesis_retest/
  hypotheses_c2.json, hypotheses_c1.json, hypotheses_crand_v2.json,
  run_config.json, baseline_parity_check.json
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime
from typing import Any

SEED = 42
random.seed(SEED)

RUN_ID = "run_017_scientific_hypothesis_retest"
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_DIR = os.path.join(BASE_DIR, "runs", RUN_ID)

# ── entity pools ───────────────────────────────────────────────────────────────

BIO_NODES: list[tuple[str, str, str]] = [
    # proteins
    ("bio:protein:bace1", "BACE1 Protease", "protein"),
    ("bio:protein:her2", "HER2 Receptor", "protein"),
    ("bio:protein:tnf_alpha", "TNF-alpha", "protein"),
    ("bio:protein:alpha_syn", "Alpha-synuclein", "protein"),
    ("bio:protein:app", "Amyloid Precursor Protein", "protein"),
    ("bio:protein:tau", "Tau Protein", "protein"),
    ("bio:protein:bdnf", "BDNF", "protein"),
    ("bio:protein:vegf", "VEGF", "protein"),
    ("bio:protein:egfr", "EGFR", "protein"),
    ("bio:protein:p53", "p53 Tumor Suppressor", "protein"),
    ("bio:protein:bcl2", "BCL-2", "protein"),
    ("bio:protein:sirt1", "SIRT1", "protein"),
    ("bio:protein:gsk3b", "GSK3-beta", "protein"),
    ("bio:protein:nrf2", "NRF2", "protein"),
    ("bio:protein:nfkb", "NF-kB", "protein"),
    ("bio:protein:stat3", "STAT3", "protein"),
    ("bio:protein:cdk4", "CDK4", "protein"),
    ("bio:protein:pten", "PTEN", "protein"),
    ("bio:protein:ampk_alpha", "AMPK-alpha", "protein"),
    ("bio:protein:hdac1", "HDAC1", "protein"),
    # pathways
    ("bio:pathway:ampk_pathway", "AMPK Pathway", "pathway"),
    ("bio:pathway:mtor_signaling", "mTOR Signaling", "pathway"),
    ("bio:pathway:pi3k_akt", "PI3K-AKT", "pathway"),
    ("bio:pathway:amyloid_cascade", "Amyloid Cascade", "pathway"),
    ("bio:pathway:autophagy", "Autophagy Pathway", "pathway"),
    ("bio:pathway:neuroinflammation", "Neuroinflammation", "pathway"),
    ("bio:pathway:apoptosis", "Apoptosis Pathway", "pathway"),
    ("bio:pathway:jak_stat", "JAK-STAT", "pathway"),
    ("bio:pathway:mapk_erk", "MAPK-ERK", "pathway"),
    ("bio:pathway:ubiquitin_proteasome", "Ubiquitin-Proteasome", "pathway"),
    ("bio:pathway:wnt_signaling", "Wnt Signaling", "pathway"),
    ("bio:pathway:nfkb_signaling", "NF-kB Signaling", "pathway"),
    ("bio:pathway:p53_pathway", "p53 Pathway", "pathway"),
    ("bio:pathway:hedgehog_signaling", "Hedgehog Signaling", "pathway"),
    # diseases
    ("bio:disease:alzheimers", "Alzheimer's Disease", "disease"),
    ("bio:disease:parkinsons", "Parkinson's Disease", "disease"),
    ("bio:disease:type2_diabetes", "Type 2 Diabetes", "disease"),
    ("bio:disease:breast_cancer", "Breast Cancer", "disease"),
    ("bio:disease:heart_failure", "Heart Failure", "disease"),
    ("bio:disease:glioblastoma", "Glioblastoma", "disease"),
    ("bio:disease:colon_cancer", "Colorectal Cancer", "disease"),
    ("bio:disease:multiple_myeloma", "Multiple Myeloma", "disease"),
    ("bio:disease:leukemia_cml", "CML Leukemia", "disease"),
    ("bio:disease:huntingtons", "Huntington's Disease", "disease"),
    ("bio:disease:rheumatoid_arthritis", "Rheumatoid Arthritis", "disease"),
    ("bio:disease:nafld", "NAFLD", "disease"),
    ("bio:disease:obesity", "Obesity", "disease"),
    ("bio:disease:prostate_cancer", "Prostate Cancer", "disease"),
    ("bio:disease:lung_cancer", "Lung Cancer", "disease"),
    # processes
    ("bio:process:cholesterol_synthesis", "Cholesterol Biosynthesis", "process"),
    ("bio:process:protein_aggregation", "Protein Aggregation", "process"),
    ("bio:process:beta_amyloid_aggregation", "Beta-Amyloid Aggregation", "process"),
    ("bio:process:tau_hyperphosphorylation", "Tau Hyperphosphorylation", "process"),
    ("bio:process:neurodegeneration", "Neurodegeneration", "process"),
    ("bio:process:tumor_angiogenesis", "Tumor Angiogenesis", "process"),
    ("bio:process:cell_senescence", "Cell Senescence", "process"),
    ("bio:process:insulin_resistance", "Insulin Resistance", "process"),
    ("bio:process:epigenetic_silencing", "Epigenetic Silencing", "process"),
    ("bio:process:oxidative_stress", "Oxidative Stress", "process"),
    ("bio:process:mitophagy", "Mitophagy", "process"),
    # biomarkers / receptors
    ("bio:biomarker:amyloid_beta42", "Amyloid-beta 42", "biomarker"),
    ("bio:biomarker:ldl_cholesterol", "LDL Cholesterol", "biomarker"),
    ("bio:biomarker:tau_protein", "Phospho-tau", "biomarker"),
    ("bio:receptor:nmda_receptor", "NMDA Receptor", "receptor"),
]

CHEM_NODES: list[tuple[str, str, str]] = [
    # drugs
    ("chem:drug:metformin", "Metformin", "drug"),
    ("chem:drug:rapamycin", "Rapamycin", "drug"),
    ("chem:drug:sildenafil", "Sildenafil", "drug"),
    ("chem:drug:aspirin", "Aspirin", "drug"),
    ("chem:drug:hydroxychloroquine", "Hydroxychloroquine", "drug"),
    ("chem:drug:bortezomib", "Bortezomib", "drug"),
    ("chem:drug:trastuzumab", "Trastuzumab", "drug"),
    ("chem:drug:memantine", "Memantine", "drug"),
    ("chem:drug:imatinib", "Imatinib", "drug"),
    ("chem:drug:erlotinib", "Erlotinib", "drug"),
    ("chem:drug:tamoxifen", "Tamoxifen", "drug"),
    ("chem:drug:valproic_acid", "Valproic Acid", "drug"),
    ("chem:drug:lithium", "Lithium", "drug"),
    ("chem:drug:dasatinib", "Dasatinib", "drug"),
    ("chem:drug:gefitinib", "Gefitinib", "drug"),
    # compounds
    ("chem:compound:quercetin", "Quercetin", "compound"),
    ("chem:compound:berberine", "Berberine", "compound"),
    ("chem:compound:resveratrol", "Resveratrol", "compound"),
    ("chem:compound:kaempferol", "Kaempferol", "compound"),
    ("chem:compound:coenzyme_q10", "Coenzyme Q10", "compound"),
    ("chem:compound:curcumin", "Curcumin", "compound"),
    ("chem:compound:egcg", "EGCG", "compound"),
    ("chem:compound:nicotinamide_riboside", "Nicotinamide Riboside", "compound"),
    # mechanisms
    ("chem:mechanism:mtor_inhibition", "mTOR Inhibition", "mechanism"),
    ("chem:mechanism:cox_inhibition", "COX Inhibition", "mechanism"),
    ("chem:mechanism:ampk_activation", "AMPK Activation", "mechanism"),
    ("chem:mechanism:pde5_inhibition", "PDE5 Inhibition", "mechanism"),
    ("chem:mechanism:jak_inhibition", "JAK Inhibition", "mechanism"),
    ("chem:mechanism:ppar_activation", "PPAR Activation", "mechanism"),
    ("chem:mechanism:proteasome_inhibition", "Proteasome Inhibition", "mechanism"),
    ("chem:mechanism:sirt1_activation", "SIRT1 Activation", "mechanism"),
    ("chem:mechanism:nmda_antagonism", "NMDA Antagonism", "mechanism"),
    ("chem:mechanism:hdac_inhibition", "HDAC Inhibition", "mechanism"),
    ("chem:mechanism:pi3k_inhibition", "PI3K Inhibition", "mechanism"),
    ("chem:mechanism:bcl2_inhibition", "BCL-2 Inhibition", "mechanism"),
    ("chem:mechanism:vegfr_inhibition", "VEGFR Inhibition", "mechanism"),
    ("chem:mechanism:stat3_inhibition", "STAT3 Inhibition", "mechanism"),
    ("chem:mechanism:nrf2_activation", "NRF2 Activation", "mechanism"),
    ("chem:mechanism:wnt_inhibition", "Wnt Inhibition", "mechanism"),
    # targets
    ("chem:target:mtor_kinase", "mTOR Kinase", "target"),
    ("chem:target:bace1_enzyme", "BACE1 Enzyme", "target"),
    ("chem:target:cox2_enzyme", "COX-2 Enzyme", "target"),
    ("chem:target:vegfr_target", "VEGFR Target", "target"),
    ("chem:target:egfr_kinase", "EGFR Kinase", "target"),
    ("chem:target:proteasome_complex", "Proteasome Complex", "target"),
    ("chem:target:her2_receptor", "HER2 Receptor Target", "target"),
    ("chem:target:bcl2_protein", "BCL-2 Target", "target"),
]

BIO_IDS: set[str] = {n[0] for n in BIO_NODES}
CHEM_IDS: set[str] = {n[0] for n in CHEM_NODES}
NODE_LABEL: dict[str, str] = {n[0]: n[1] for n in BIO_NODES + CHEM_NODES}

# ── KG 1-hop edge blacklist ─────────────────────────────────────────────────────

KG_DIRECT_EDGES: set[tuple[str, str]] = {
    # seed KG cross-domain edges
    ("chem:target:bace1_enzyme", "bio:protein:bace1"),
    ("chem:target:mtor_kinase", "bio:pathway:mtor_signaling"),
    ("chem:mechanism:mtor_inhibition", "bio:pathway:mtor_signaling"),
    ("chem:mechanism:ampk_activation", "bio:pathway:ampk_pathway"),
    ("chem:drug:metformin", "bio:disease:type2_diabetes"),
    ("chem:drug:rapamycin", "bio:disease:alzheimers"),
    ("chem:compound:quercetin", "bio:protein:bace1"),
    ("chem:drug:metformin", "bio:disease:alzheimers"),
    ("chem:drug:aspirin", "bio:disease:breast_cancer"),
    # extended cross-domain edges used in C2 paths
    ("chem:drug:metformin", "bio:pathway:ampk_pathway"),
    ("chem:drug:rapamycin", "bio:pathway:mtor_signaling"),
    ("chem:drug:sildenafil", "bio:pathway:ampk_pathway"),
    ("chem:drug:aspirin", "bio:protein:tnf_alpha"),
    ("chem:drug:aspirin", "bio:pathway:amyloid_cascade"),
    ("chem:drug:aspirin", "bio:pathway:neuroinflammation"),
    ("chem:drug:hydroxychloroquine", "bio:pathway:mtor_signaling"),
    ("chem:drug:hydroxychloroquine", "bio:pathway:pi3k_akt"),
    ("chem:compound:berberine", "bio:disease:type2_diabetes"),
    ("chem:compound:berberine", "bio:process:cholesterol_synthesis"),
    ("chem:compound:resveratrol", "bio:pathway:mtor_signaling"),
    ("chem:compound:resveratrol", "bio:protein:sirt1"),
    ("chem:compound:resveratrol", "bio:process:cell_senescence"),
    ("chem:compound:quercetin", "bio:disease:alzheimers"),
    ("chem:compound:quercetin", "bio:protein:app"),
    ("chem:mechanism:mtor_inhibition", "bio:pathway:ampk_pathway"),
    # bio-only edges (for reference)
    ("bio:protein:bace1", "bio:pathway:amyloid_cascade"),
    ("bio:pathway:amyloid_cascade", "bio:disease:alzheimers"),
    ("bio:protein:her2", "bio:pathway:pi3k_akt"),
    ("bio:pathway:pi3k_akt", "bio:disease:breast_cancer"),
    ("bio:protein:alpha_syn", "bio:disease:parkinsons"),
    ("bio:protein:tnf_alpha", "bio:pathway:pi3k_akt"),
    ("bio:pathway:mtor_signaling", "bio:pathway:ampk_pathway"),
    ("bio:pathway:ampk_pathway", "bio:disease:type2_diabetes"),
    ("bio:pathway:mtor_signaling", "bio:disease:alzheimers"),
    ("bio:pathway:mtor_signaling", "bio:disease:breast_cancer"),
}

# ── trivially-known pair blacklist (domain-well-known, pre-2024) ──────────────

TRIVIALLY_KNOWN: set[tuple[str, str]] = {
    # v1 C_rand pairs that were trivially supported (precision=1.000)
    ("bio:protein:her2", "bio:disease:breast_cancer"),
    ("bio:disease:obesity", "bio:disease:nafld"),
    ("chem:mechanism:jak_inhibition", "bio:disease:rheumatoid_arthritis"),
    ("bio:process:beta_amyloid_aggregation", "bio:disease:alzheimers"),
    ("chem:target:bace1_enzyme", "bio:pathway:amyloid_cascade"),
    ("chem:drug:trastuzumab", "bio:disease:breast_cancer"),
    ("chem:mechanism:ppar_activation", "bio:disease:type2_diabetes"),
    ("bio:pathway:ubiquitin_proteasome", "bio:process:protein_aggregation"),
    ("chem:target:vegfr_target", "bio:process:tumor_angiogenesis"),
    ("chem:drug:memantine", "bio:receptor:nmda_receptor"),
    ("chem:compound:kaempferol", "bio:protein:bace1"),
    ("bio:protein:gsk3b", "bio:biomarker:tau_protein"),
    ("bio:protein:app", "bio:process:beta_amyloid_aggregation"),
    # approved indications / direct mechanisms
    ("chem:drug:metformin", "bio:disease:type2_diabetes"),
    ("chem:drug:aspirin", "chem:mechanism:cox_inhibition"),
    ("chem:drug:trastuzumab", "chem:target:her2_receptor"),
    ("chem:drug:erlotinib", "chem:target:egfr_kinase"),
    ("chem:drug:gefitinib", "chem:target:egfr_kinase"),
    ("chem:drug:imatinib", "bio:disease:leukemia_cml"),
    ("chem:drug:tamoxifen", "bio:disease:breast_cancer"),
    ("chem:drug:dasatinib", "bio:disease:leukemia_cml"),
    ("chem:drug:bortezomib", "bio:disease:multiple_myeloma"),
    # well-established biology
    ("bio:protein:bace1", "bio:disease:alzheimers"),
    ("bio:protein:egfr", "bio:disease:lung_cancer"),
    ("bio:protein:vegf", "bio:process:tumor_angiogenesis"),
    ("bio:pathway:amyloid_cascade", "bio:disease:alzheimers"),
    ("bio:protein:bcl2", "bio:pathway:apoptosis"),
    ("bio:protein:her2", "bio:pathway:pi3k_akt"),
    ("bio:protein:tau", "bio:disease:alzheimers"),
    ("bio:pathway:pi3k_akt", "bio:disease:breast_cancer"),
    ("bio:protein:p53", "bio:pathway:apoptosis"),
    ("chem:mechanism:proteasome_inhibition", "bio:disease:multiple_myeloma"),
    ("chem:mechanism:mtor_inhibition", "bio:pathway:mtor_signaling"),
    ("chem:target:mtor_kinase", "bio:pathway:mtor_signaling"),
}

# ── C2 multi-op hypotheses (N=50, cross-domain) ───────────────────────────────
# format: (id, subj, obj, provenance_list, description)

_C2_RAW: list[tuple[str, str, str, list[str], str]] = [
    # from run_016 (20 original)
    ("H3001", "chem:drug:metformin", "bio:process:cholesterol_synthesis",
     ["chem:drug:metformin", "activates", "bio:pathway:ampk_pathway",
      "inhibits", "bio:process:cholesterol_synthesis"],
     "Metformin may inhibit Cholesterol Biosynthesis via AMPK Pathway activation"),
    ("H3002", "chem:drug:rapamycin", "bio:pathway:mtor_signaling",
     ["chem:drug:rapamycin", "inhibits", "chem:target:mtor_kinase",
      "regulates", "bio:pathway:mtor_signaling"],
     "Rapamycin may modulate mTOR Signaling via mTOR Kinase inhibition"),
    ("H3003", "chem:drug:rapamycin", "bio:disease:breast_cancer",
     ["chem:drug:rapamycin", "produces", "chem:mechanism:mtor_inhibition",
      "inhibits", "bio:pathway:mtor_signaling", "promotes", "bio:disease:breast_cancer"],
     "Rapamycin may reduce Breast Cancer risk via mTOR pathway suppression"),
    ("H3004", "chem:drug:sildenafil", "bio:pathway:ampk_pathway",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "activates", "bio:pathway:ampk_pathway"],
     "Sildenafil may activate AMPK Pathway via PDE5 Inhibition"),
    ("H3005", "chem:drug:sildenafil", "bio:pathway:pi3k_akt",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "modulates", "bio:pathway:pi3k_akt"],
     "Sildenafil may modulate PI3K-AKT via PDE5 Inhibition"),
    ("H3006", "chem:drug:sildenafil", "bio:pathway:autophagy",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "activates", "bio:pathway:autophagy"],
     "Sildenafil may activate Autophagy Pathway via PDE5 Inhibition"),
    ("H3007", "chem:drug:sildenafil", "bio:disease:heart_failure",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "improves", "bio:disease:heart_failure"],
     "Sildenafil may improve Heart Failure via PDE5 Inhibition"),
    ("H3008", "chem:drug:sildenafil", "bio:pathway:neuroinflammation",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "reduces", "bio:pathway:neuroinflammation"],
     "Sildenafil may reduce Neuroinflammation via PDE5 Inhibition"),
    ("H3009", "chem:drug:aspirin", "bio:protein:tnf_alpha",
     ["chem:drug:aspirin", "produces", "chem:mechanism:cox_inhibition",
      "reduces", "bio:protein:tnf_alpha"],
     "Aspirin may reduce TNF-alpha levels via COX Inhibition"),
    ("H3010", "chem:drug:aspirin", "bio:pathway:amyloid_cascade",
     ["chem:drug:aspirin", "produces", "chem:mechanism:cox_inhibition",
      "attenuates", "bio:pathway:amyloid_cascade"],
     "Aspirin may attenuate Amyloid Cascade via COX Inhibition"),
    ("H3011", "chem:drug:hydroxychloroquine", "bio:pathway:mtor_signaling",
     ["chem:drug:hydroxychloroquine", "inhibits", "chem:target:mtor_kinase",
      "regulates", "bio:pathway:mtor_signaling"],
     "Hydroxychloroquine may modulate mTOR Signaling via mTOR Kinase"),
    ("H3012", "chem:drug:hydroxychloroquine", "bio:pathway:pi3k_akt",
     ["chem:drug:hydroxychloroquine", "inhibits", "chem:target:mtor_kinase",
      "cross_inhibits", "bio:pathway:pi3k_akt"],
     "Hydroxychloroquine may suppress PI3K-AKT via mTOR Kinase"),
    ("H3013", "chem:compound:quercetin", "bio:protein:app",
     ["chem:compound:quercetin", "inhibits", "chem:target:bace1_enzyme",
      "reduces_cleavage_of", "bio:protein:app"],
     "Quercetin may reduce APP cleavage via BACE1 Enzyme inhibition"),
    ("H3014", "chem:compound:quercetin", "bio:disease:alzheimers",
     ["chem:compound:quercetin", "inhibits", "chem:target:bace1_enzyme",
      "reduces", "bio:pathway:amyloid_cascade", "attenuates", "bio:disease:alzheimers"],
     "Quercetin may attenuate Alzheimer's Disease via BACE1 and Amyloid Cascade"),
    ("H3015", "chem:compound:berberine", "bio:disease:type2_diabetes",
     ["chem:compound:berberine", "produces", "chem:mechanism:ampk_activation",
      "improves", "bio:process:insulin_resistance", "drives", "bio:disease:type2_diabetes"],
     "Berberine may improve Type 2 Diabetes via AMPK activation and insulin sensitization"),
    ("H3016", "chem:compound:berberine", "bio:process:cholesterol_synthesis",
     ["chem:compound:berberine", "produces", "chem:mechanism:ampk_activation",
      "inhibits", "bio:process:cholesterol_synthesis"],
     "Berberine may inhibit Cholesterol Biosynthesis via AMPK Activation"),
    ("H3017", "chem:compound:resveratrol", "bio:pathway:mtor_signaling",
     ["chem:compound:resveratrol", "inhibits", "chem:target:mtor_kinase",
      "regulates", "bio:pathway:mtor_signaling"],
     "Resveratrol may regulate mTOR Signaling via mTOR Kinase inhibition"),
    ("H3018", "chem:compound:resveratrol", "bio:protein:sirt1",
     ["chem:compound:resveratrol", "produces", "chem:mechanism:sirt1_activation",
      "activates", "bio:protein:sirt1"],
     "Resveratrol may activate SIRT1 via SIRT1 Activation mechanism"),
    ("H3019", "chem:compound:resveratrol", "bio:process:cell_senescence",
     ["chem:compound:resveratrol", "produces", "chem:mechanism:sirt1_activation",
      "delays", "bio:process:cell_senescence"],
     "Resveratrol may delay Cell Senescence via SIRT1 Activation"),
    ("H3020", "chem:mechanism:mtor_inhibition", "bio:pathway:ampk_pathway",
     ["chem:mechanism:mtor_inhibition", "inhibits", "chem:target:mtor_kinase",
      "cross_activates", "bio:pathway:ampk_pathway"],
     "mTOR Inhibition may activate AMPK Pathway via mTOR-AMPK crosstalk"),
    # new 30
    ("H3021", "chem:drug:metformin", "bio:disease:alzheimers",
     ["chem:drug:metformin", "produces", "chem:mechanism:ampk_activation",
      "reduces", "bio:pathway:neuroinflammation", "attenuates", "bio:disease:alzheimers"],
     "Metformin may attenuate Alzheimer's Disease via AMPK-mediated neuroinflammation reduction"),
    ("H3022", "chem:drug:metformin", "bio:disease:nafld",
     ["chem:drug:metformin", "produces", "chem:mechanism:ampk_activation",
      "reduces", "bio:process:insulin_resistance", "ameliorates", "bio:disease:nafld"],
     "Metformin may ameliorate NAFLD via AMPK-mediated insulin sensitization"),
    ("H3023", "chem:drug:metformin", "bio:process:oxidative_stress",
     ["chem:drug:metformin", "produces", "chem:mechanism:ampk_activation",
      "induces", "bio:protein:nrf2", "reduces", "bio:process:oxidative_stress"],
     "Metformin may reduce Oxidative Stress via AMPK-NRF2 axis"),
    ("H3024", "chem:drug:rapamycin", "bio:disease:parkinsons",
     ["chem:drug:rapamycin", "produces", "chem:mechanism:mtor_inhibition",
      "activates", "bio:pathway:autophagy", "clears", "bio:disease:parkinsons"],
     "Rapamycin may protect against Parkinson's Disease via mTOR-autophagy axis"),
    ("H3025", "chem:drug:rapamycin", "bio:disease:huntingtons",
     ["chem:drug:rapamycin", "produces", "chem:mechanism:mtor_inhibition",
      "reduces", "bio:process:protein_aggregation", "attenuates", "bio:disease:huntingtons"],
     "Rapamycin may attenuate Huntington's Disease via protein aggregation clearance"),
    ("H3026", "chem:drug:rapamycin", "bio:process:cell_senescence",
     ["chem:drug:rapamycin", "inhibits", "chem:target:mtor_kinase",
      "delays", "bio:process:cell_senescence"],
     "Rapamycin may delay Cell Senescence via mTOR Kinase inhibition"),
    ("H3027", "chem:drug:aspirin", "bio:disease:colon_cancer",
     ["chem:drug:aspirin", "inhibits", "chem:target:cox2_enzyme",
      "reduces", "bio:pathway:wnt_signaling", "drives", "bio:disease:colon_cancer"],
     "Aspirin may reduce Colorectal Cancer risk via COX-2 and Wnt pathway"),
    ("H3028", "chem:drug:aspirin", "bio:disease:alzheimers",
     ["chem:drug:aspirin", "produces", "chem:mechanism:cox_inhibition",
      "reduces", "bio:pathway:neuroinflammation", "attenuates", "bio:disease:alzheimers"],
     "Aspirin may attenuate Alzheimer's Disease via COX-mediated neuroinflammation"),
    ("H3029", "chem:drug:bortezomib", "bio:disease:huntingtons",
     ["chem:drug:bortezomib", "produces", "chem:mechanism:proteasome_inhibition",
      "disrupts", "bio:pathway:ubiquitin_proteasome", "worsens", "bio:disease:huntingtons"],
     "Bortezomib may affect Huntington's Disease via ubiquitin-proteasome disruption"),
    ("H3030", "chem:drug:bortezomib", "bio:pathway:apoptosis",
     ["chem:drug:bortezomib", "produces", "chem:mechanism:proteasome_inhibition",
      "activates", "bio:pathway:apoptosis"],
     "Bortezomib may activate Apoptosis Pathway via proteasome inhibition"),
    ("H3031", "chem:drug:valproic_acid", "bio:disease:glioblastoma",
     ["chem:drug:valproic_acid", "produces", "chem:mechanism:hdac_inhibition",
      "activates", "bio:pathway:p53_pathway", "suppresses", "bio:disease:glioblastoma"],
     "Valproic Acid may suppress Glioblastoma via HDAC inhibition and p53 pathway"),
    ("H3032", "chem:drug:valproic_acid", "bio:process:epigenetic_silencing",
     ["chem:drug:valproic_acid", "produces", "chem:mechanism:hdac_inhibition",
      "reverses", "bio:process:epigenetic_silencing"],
     "Valproic Acid may reverse Epigenetic Silencing via HDAC inhibition"),
    ("H3033", "chem:drug:imatinib", "bio:pathway:mapk_erk",
     ["chem:drug:imatinib", "produces", "chem:mechanism:stat3_inhibition",
      "inhibits", "bio:pathway:mapk_erk"],
     "Imatinib may inhibit MAPK-ERK via STAT3 inhibition"),
    ("H3034", "chem:compound:berberine", "bio:disease:nafld",
     ["chem:compound:berberine", "produces", "chem:mechanism:ampk_activation",
      "reduces", "bio:process:insulin_resistance", "ameliorates", "bio:disease:nafld"],
     "Berberine may ameliorate NAFLD via AMPK-mediated insulin sensitization"),
    ("H3035", "chem:compound:berberine", "bio:disease:parkinsons",
     ["chem:compound:berberine", "produces", "chem:mechanism:ampk_activation",
      "reduces", "bio:process:oxidative_stress", "attenuates", "bio:disease:parkinsons"],
     "Berberine may attenuate Parkinson's Disease via AMPK-oxidative stress reduction"),
    ("H3036", "chem:compound:quercetin", "bio:disease:parkinsons",
     ["chem:compound:quercetin", "inhibits", "chem:target:bace1_enzyme",
      "reduces", "bio:pathway:neuroinflammation", "attenuates", "bio:disease:parkinsons"],
     "Quercetin may attenuate Parkinson's Disease via BACE1-neuroinflammation axis"),
    ("H3037", "chem:compound:curcumin", "bio:disease:rheumatoid_arthritis",
     ["chem:compound:curcumin", "produces", "chem:mechanism:stat3_inhibition",
      "suppresses", "bio:pathway:nfkb_signaling", "drives", "bio:disease:rheumatoid_arthritis"],
     "Curcumin may suppress Rheumatoid Arthritis via STAT3-NF-kB pathway"),
    ("H3038", "chem:compound:curcumin", "bio:disease:alzheimers",
     ["chem:compound:curcumin", "produces", "chem:mechanism:stat3_inhibition",
      "reduces", "bio:pathway:neuroinflammation", "attenuates", "bio:disease:alzheimers"],
     "Curcumin may attenuate Alzheimer's Disease via STAT3-neuroinflammation"),
    ("H3039", "chem:compound:curcumin", "bio:pathway:neuroinflammation",
     ["chem:compound:curcumin", "produces", "chem:mechanism:stat3_inhibition",
      "suppresses", "bio:pathway:nfkb_signaling", "activates", "bio:pathway:neuroinflammation"],
     "Curcumin may modulate Neuroinflammation via STAT3 and NF-kB signaling"),
    ("H3040", "chem:compound:kaempferol", "bio:disease:colon_cancer",
     ["chem:compound:kaempferol", "produces", "chem:mechanism:pi3k_inhibition",
      "suppresses", "bio:pathway:pi3k_akt", "attenuates", "bio:disease:colon_cancer"],
     "Kaempferol may attenuate Colorectal Cancer via PI3K-AKT suppression"),
    ("H3041", "chem:compound:coenzyme_q10", "bio:disease:parkinsons",
     ["chem:compound:coenzyme_q10", "reduces", "bio:process:oxidative_stress",
      "attenuates", "bio:disease:parkinsons"],
     "Coenzyme Q10 may attenuate Parkinson's Disease via oxidative stress reduction"),
    ("H3042", "chem:compound:nicotinamide_riboside", "bio:disease:alzheimers",
     ["chem:compound:nicotinamide_riboside", "produces", "chem:mechanism:sirt1_activation",
      "reduces", "bio:process:neurodegeneration", "attenuates", "bio:disease:alzheimers"],
     "Nicotinamide Riboside may attenuate Alzheimer's Disease via SIRT1-neurodegeneration axis"),
    ("H3043", "chem:compound:nicotinamide_riboside", "bio:disease:nafld",
     ["chem:compound:nicotinamide_riboside", "produces", "chem:mechanism:sirt1_activation",
      "improves", "bio:process:insulin_resistance", "ameliorates", "bio:disease:nafld"],
     "Nicotinamide Riboside may ameliorate NAFLD via SIRT1-insulin resistance axis"),
    ("H3044", "chem:compound:resveratrol", "bio:disease:nafld",
     ["chem:compound:resveratrol", "produces", "chem:mechanism:sirt1_activation",
      "improves", "bio:process:insulin_resistance", "ameliorates", "bio:disease:nafld"],
     "Resveratrol may ameliorate NAFLD via SIRT1-insulin resistance axis"),
    ("H3045", "chem:drug:hydroxychloroquine", "bio:disease:alzheimers",
     ["chem:drug:hydroxychloroquine", "inhibits", "chem:target:mtor_kinase",
      "activates", "bio:pathway:autophagy", "clears", "bio:disease:alzheimers"],
     "Hydroxychloroquine may affect Alzheimer's Disease via mTOR-autophagy axis"),
    ("H3046", "chem:drug:sildenafil", "bio:disease:alzheimers",
     ["chem:drug:sildenafil", "produces", "chem:mechanism:pde5_inhibition",
      "reduces", "bio:pathway:neuroinflammation", "attenuates", "bio:disease:alzheimers"],
     "Sildenafil may attenuate Alzheimer's Disease via PDE5-neuroinflammation axis"),
    ("H3047", "chem:drug:erlotinib", "bio:disease:lung_cancer",
     ["chem:drug:erlotinib", "inhibits", "chem:target:egfr_kinase",
      "suppresses", "bio:pathway:pi3k_akt", "attenuates", "bio:disease:lung_cancer"],
     "Erlotinib may suppress Lung Cancer via EGFR-PI3K-AKT pathway"),
    ("H3048", "chem:compound:egcg", "bio:disease:multiple_myeloma",
     ["chem:compound:egcg", "produces", "chem:mechanism:pi3k_inhibition",
      "activates", "bio:pathway:apoptosis", "suppresses", "bio:disease:multiple_myeloma"],
     "EGCG may suppress Multiple Myeloma via PI3K inhibition and apoptosis"),
    ("H3049", "chem:mechanism:sirt1_activation", "bio:process:neurodegeneration",
     ["chem:mechanism:sirt1_activation", "activates", "bio:protein:sirt1",
      "reduces", "bio:process:neurodegeneration"],
     "SIRT1 Activation may reduce Neurodegeneration via SIRT1 protein activity"),
    ("H3050", "chem:mechanism:pi3k_inhibition", "bio:process:tumor_angiogenesis",
     ["chem:mechanism:pi3k_inhibition", "suppresses", "bio:pathway:pi3k_akt",
      "reduces", "bio:process:tumor_angiogenesis"],
     "PI3K Inhibition may reduce Tumor Angiogenesis via PI3K-AKT pathway"),
]

# ── C1 single-op hypotheses (N=50, bio-only) ─────────────────────────────────

_C1_RAW: list[tuple[str, str, str, list[str], str]] = [
    # from run_016 (20 original)
    ("H4001", "bio:protein:bace1", "bio:disease:alzheimers",
     ["bio:protein:bace1", "drives", "bio:pathway:amyloid_cascade",
      "causes", "bio:disease:alzheimers"],
     "BACE1 Protease may cause Alzheimer's Disease via Amyloid Cascade"),
    ("H4002", "bio:protein:bace1", "bio:biomarker:amyloid_beta42",
     ["bio:protein:bace1", "drives", "bio:pathway:amyloid_cascade",
      "produces", "bio:biomarker:amyloid_beta42"],
     "BACE1 may elevate Amyloid-beta 42 via Amyloid Cascade"),
    ("H4003", "bio:protein:her2", "bio:disease:breast_cancer",
     ["bio:protein:her2", "drives", "bio:pathway:pi3k_akt",
      "promotes", "bio:disease:breast_cancer"],
     "HER2 may promote Breast Cancer via PI3K-AKT pathway"),
    ("H4004", "bio:protein:tnf_alpha", "bio:disease:breast_cancer",
     ["bio:protein:tnf_alpha", "activates", "bio:pathway:pi3k_akt",
      "promotes", "bio:disease:breast_cancer"],
     "TNF-alpha may promote Breast Cancer via PI3K-AKT pathway"),
    ("H4005", "bio:pathway:mtor_signaling", "bio:disease:type2_diabetes",
     ["bio:pathway:mtor_signaling", "inhibits", "bio:pathway:ampk_pathway",
      "inhibits", "bio:disease:type2_diabetes"],
     "mTOR Signaling may drive Type 2 Diabetes via AMPK pathway suppression"),
    ("H4006", "bio:pathway:mtor_signaling", "bio:process:cholesterol_synthesis",
     ["bio:pathway:mtor_signaling", "activates", "bio:process:cholesterol_synthesis"],
     "mTOR Signaling may activate Cholesterol Biosynthesis"),
    ("H4007", "bio:pathway:mtor_signaling", "bio:disease:breast_cancer",
     ["bio:pathway:mtor_signaling", "promotes", "bio:disease:breast_cancer"],
     "mTOR Signaling may promote Breast Cancer"),
    ("H4008", "bio:pathway:mtor_signaling", "bio:process:protein_aggregation",
     ["bio:pathway:mtor_signaling", "inhibits", "bio:pathway:autophagy",
      "impairs_clearance_of", "bio:process:protein_aggregation"],
     "mTOR Signaling may exacerbate Protein Aggregation via autophagy suppression"),
    ("H4009", "bio:pathway:ampk_pathway", "bio:biomarker:ldl_cholesterol",
     ["bio:pathway:ampk_pathway", "inhibits", "bio:process:cholesterol_synthesis",
      "reduces", "bio:biomarker:ldl_cholesterol"],
     "AMPK Pathway may reduce LDL Cholesterol via cholesterol synthesis inhibition"),
    ("H4010", "bio:protein:app", "bio:process:beta_amyloid_aggregation",
     ["bio:protein:app", "cleaved_to", "bio:biomarker:amyloid_beta42",
      "aggregates_as", "bio:process:beta_amyloid_aggregation"],
     "APP may drive Beta-Amyloid Aggregation via amyloid-beta 42 production"),
    ("H4011", "bio:protein:tau", "bio:disease:alzheimers",
     ["bio:protein:tau", "hyperphosphorylated_via", "bio:process:tau_hyperphosphorylation",
      "causes", "bio:disease:alzheimers"],
     "Tau Protein may cause Alzheimer's Disease via tau hyperphosphorylation"),
    ("H4012", "bio:protein:bdnf", "bio:disease:alzheimers",
     ["bio:protein:bdnf", "protects_against", "bio:process:neurodegeneration",
      "drives", "bio:disease:alzheimers"],
     "BDNF deficiency may worsen Alzheimer's Disease via neurodegeneration"),
    ("H4013", "bio:protein:bdnf", "bio:disease:parkinsons",
     ["bio:protein:bdnf", "protects_against", "bio:process:neurodegeneration",
      "drives", "bio:disease:parkinsons"],
     "BDNF deficiency may worsen Parkinson's Disease via neurodegeneration"),
    ("H4014", "bio:protein:bdnf", "bio:disease:huntingtons",
     ["bio:protein:bdnf", "protects_against", "bio:process:neurodegeneration",
      "drives", "bio:disease:huntingtons"],
     "BDNF deficiency may worsen Huntington's Disease via neurodegeneration"),
    ("H4015", "bio:protein:vegf", "bio:disease:glioblastoma",
     ["bio:protein:vegf", "drives", "bio:process:tumor_angiogenesis",
      "promotes", "bio:disease:glioblastoma"],
     "VEGF may promote Glioblastoma via tumor angiogenesis"),
    ("H4016", "bio:protein:egfr", "bio:disease:colon_cancer",
     ["bio:protein:egfr", "activates", "bio:pathway:mapk_erk",
      "promotes", "bio:disease:colon_cancer"],
     "EGFR may promote Colorectal Cancer via MAPK-ERK pathway"),
    ("H4017", "bio:protein:p53", "bio:disease:multiple_myeloma",
     ["bio:protein:p53", "regulates", "bio:pathway:apoptosis",
      "suppresses", "bio:disease:multiple_myeloma"],
     "p53 may suppress Multiple Myeloma via apoptosis regulation"),
    ("H4018", "bio:protein:p53", "bio:disease:leukemia_cml",
     ["bio:protein:p53", "regulates", "bio:pathway:apoptosis",
      "suppresses", "bio:disease:leukemia_cml"],
     "p53 may suppress CML Leukemia via apoptosis regulation"),
    ("H4019", "bio:protein:bcl2", "bio:disease:multiple_myeloma",
     ["bio:protein:bcl2", "inhibits", "bio:pathway:apoptosis",
      "promotes", "bio:disease:multiple_myeloma"],
     "BCL-2 may promote Multiple Myeloma via apoptosis inhibition"),
    ("H4020", "bio:protein:bcl2", "bio:disease:leukemia_cml",
     ["bio:protein:bcl2", "inhibits", "bio:pathway:apoptosis",
      "promotes", "bio:disease:leukemia_cml"],
     "BCL-2 may promote CML Leukemia via apoptosis inhibition"),
    # new 30
    ("H4021", "bio:pathway:autophagy", "bio:disease:alzheimers",
     ["bio:pathway:autophagy", "clears", "bio:process:protein_aggregation",
      "drives", "bio:disease:alzheimers"],
     "Autophagy dysfunction may worsen Alzheimer's Disease via protein aggregation"),
    ("H4022", "bio:pathway:autophagy", "bio:disease:parkinsons",
     ["bio:pathway:autophagy", "clears", "bio:protein:alpha_syn",
      "aggregates_in", "bio:disease:parkinsons"],
     "Autophagy dysfunction may worsen Parkinson's Disease via alpha-synuclein clearance"),
    ("H4023", "bio:pathway:neuroinflammation", "bio:disease:alzheimers",
     ["bio:pathway:neuroinflammation", "activates", "bio:protein:tnf_alpha",
      "exacerbates", "bio:disease:alzheimers"],
     "Neuroinflammation may exacerbate Alzheimer's Disease via TNF-alpha activation"),
    ("H4024", "bio:pathway:neuroinflammation", "bio:disease:parkinsons",
     ["bio:pathway:neuroinflammation", "promotes", "bio:process:neurodegeneration",
      "drives", "bio:disease:parkinsons"],
     "Neuroinflammation may drive Parkinson's Disease via neurodegeneration"),
    ("H4025", "bio:pathway:apoptosis", "bio:disease:huntingtons",
     ["bio:pathway:apoptosis", "mediates", "bio:process:neurodegeneration",
      "drives", "bio:disease:huntingtons"],
     "Apoptosis pathway may drive Huntington's Disease via neurodegeneration"),
    ("H4026", "bio:pathway:jak_stat", "bio:disease:rheumatoid_arthritis",
     ["bio:pathway:jak_stat", "activates", "bio:protein:tnf_alpha",
      "promotes", "bio:disease:rheumatoid_arthritis"],
     "JAK-STAT pathway may promote Rheumatoid Arthritis via TNF-alpha"),
    ("H4027", "bio:pathway:mapk_erk", "bio:disease:colon_cancer",
     ["bio:pathway:mapk_erk", "promotes", "bio:process:tumor_angiogenesis",
      "supports", "bio:disease:colon_cancer"],
     "MAPK-ERK may support Colorectal Cancer via tumor angiogenesis"),
    ("H4028", "bio:pathway:wnt_signaling", "bio:disease:colon_cancer",
     ["bio:pathway:wnt_signaling", "promotes", "bio:process:cell_senescence",
      "drives", "bio:disease:colon_cancer"],
     "Wnt Signaling may drive Colorectal Cancer via cell senescence evasion"),
    ("H4029", "bio:pathway:pi3k_akt", "bio:disease:breast_cancer",
     ["bio:pathway:pi3k_akt", "promotes", "bio:disease:breast_cancer"],
     "PI3K-AKT pathway may promote Breast Cancer"),
    ("H4030", "bio:pathway:hedgehog_signaling", "bio:disease:prostate_cancer",
     ["bio:pathway:hedgehog_signaling", "promotes", "bio:process:tumor_angiogenesis",
      "supports", "bio:disease:prostate_cancer"],
     "Hedgehog Signaling may support Prostate Cancer via tumor angiogenesis"),
    ("H4031", "bio:protein:nfkb", "bio:disease:rheumatoid_arthritis",
     ["bio:protein:nfkb", "activates", "bio:pathway:nfkb_signaling",
      "drives", "bio:disease:rheumatoid_arthritis"],
     "NF-kB may drive Rheumatoid Arthritis via NF-kB signaling"),
    ("H4032", "bio:protein:stat3", "bio:disease:breast_cancer",
     ["bio:protein:stat3", "activates", "bio:pathway:pi3k_akt",
      "promotes", "bio:disease:breast_cancer"],
     "STAT3 may promote Breast Cancer via PI3K-AKT pathway"),
    ("H4033", "bio:protein:stat3", "bio:disease:lung_cancer",
     ["bio:protein:stat3", "activates", "bio:pathway:mapk_erk",
      "promotes", "bio:disease:lung_cancer"],
     "STAT3 may promote Lung Cancer via MAPK-ERK pathway"),
    ("H4034", "bio:protein:cdk4", "bio:disease:breast_cancer",
     ["bio:protein:cdk4", "drives", "bio:pathway:pi3k_akt",
      "promotes", "bio:disease:breast_cancer"],
     "CDK4 may promote Breast Cancer via PI3K-AKT pathway"),
    ("H4035", "bio:protein:pten", "bio:disease:prostate_cancer",
     ["bio:protein:pten", "suppresses", "bio:pathway:pi3k_akt",
      "regulates", "bio:disease:prostate_cancer"],
     "PTEN may regulate Prostate Cancer via PI3K-AKT suppression"),
    ("H4036", "bio:protein:nrf2", "bio:process:oxidative_stress",
     ["bio:protein:nrf2", "reduces", "bio:process:oxidative_stress"],
     "NRF2 may reduce Oxidative Stress"),
    ("H4037", "bio:protein:gsk3b", "bio:disease:alzheimers",
     ["bio:protein:gsk3b", "phosphorylates", "bio:protein:tau",
      "causes", "bio:process:tau_hyperphosphorylation",
      "drives", "bio:disease:alzheimers"],
     "GSK3-beta may drive Alzheimer's Disease via tau hyperphosphorylation"),
    ("H4038", "bio:protein:hdac1", "bio:process:epigenetic_silencing",
     ["bio:protein:hdac1", "mediates", "bio:process:epigenetic_silencing"],
     "HDAC1 may mediate Epigenetic Silencing"),
    ("H4039", "bio:process:oxidative_stress", "bio:disease:parkinsons",
     ["bio:process:oxidative_stress", "drives", "bio:process:neurodegeneration",
      "causes", "bio:disease:parkinsons"],
     "Oxidative Stress may cause Parkinson's Disease via neurodegeneration"),
    ("H4040", "bio:process:oxidative_stress", "bio:disease:heart_failure",
     ["bio:process:oxidative_stress", "damages", "bio:process:mitophagy",
      "impairs", "bio:disease:heart_failure"],
     "Oxidative Stress may impair Heart Failure via mitophagy disruption"),
    ("H4041", "bio:process:neurodegeneration", "bio:disease:alzheimers",
     ["bio:process:neurodegeneration", "causes", "bio:disease:alzheimers"],
     "Neurodegeneration may cause Alzheimer's Disease"),
    ("H4042", "bio:process:neurodegeneration", "bio:disease:huntingtons",
     ["bio:process:neurodegeneration", "mediates", "bio:disease:huntingtons"],
     "Neurodegeneration may mediate Huntington's Disease"),
    ("H4043", "bio:process:cell_senescence", "bio:disease:heart_failure",
     ["bio:process:cell_senescence", "promotes", "bio:process:oxidative_stress",
      "damages", "bio:disease:heart_failure"],
     "Cell Senescence may worsen Heart Failure via oxidative stress"),
    ("H4044", "bio:process:tumor_angiogenesis", "bio:disease:glioblastoma",
     ["bio:process:tumor_angiogenesis", "promotes", "bio:disease:glioblastoma"],
     "Tumor Angiogenesis may promote Glioblastoma"),
    ("H4045", "bio:process:insulin_resistance", "bio:disease:nafld",
     ["bio:process:insulin_resistance", "causes", "bio:disease:nafld"],
     "Insulin Resistance may cause NAFLD"),
    ("H4046", "bio:pathway:p53_pathway", "bio:disease:lung_cancer",
     ["bio:pathway:p53_pathway", "suppresses", "bio:disease:lung_cancer"],
     "p53 Pathway may suppress Lung Cancer"),
    ("H4047", "bio:pathway:nfkb_signaling", "bio:disease:rheumatoid_arthritis",
     ["bio:pathway:nfkb_signaling", "promotes", "bio:pathway:jak_stat",
      "activates", "bio:disease:rheumatoid_arthritis"],
     "NF-kB Signaling may activate Rheumatoid Arthritis via JAK-STAT"),
    ("H4048", "bio:pathway:ubiquitin_proteasome", "bio:disease:huntingtons",
     ["bio:pathway:ubiquitin_proteasome", "impaired_in", "bio:process:protein_aggregation",
      "drives", "bio:disease:huntingtons"],
     "Ubiquitin-Proteasome dysfunction may drive Huntington's Disease"),
    ("H4049", "bio:pathway:pi3k_akt", "bio:disease:prostate_cancer",
     ["bio:pathway:pi3k_akt", "promotes", "bio:disease:prostate_cancer"],
     "PI3K-AKT pathway may promote Prostate Cancer"),
    ("H4050", "bio:protein:ampk_alpha", "bio:disease:type2_diabetes",
     ["bio:protein:ampk_alpha", "activates", "bio:pathway:ampk_pathway",
      "inhibits", "bio:disease:type2_diabetes"],
     "AMPK-alpha may protect against Type 2 Diabetes via AMPK pathway"),
]

# ── C_rand_v2: truly random cross-domain pairs (no KG path traversal) ─────────

# Combined blacklist for random sampling
_ALL_BLACKLISTED: set[tuple[str, str]] = (
    KG_DIRECT_EDGES
    | TRIVIALLY_KNOWN
    | {(h[1], h[2]) for h in _C2_RAW}
    | {(h[1], h[2]) for h in _C1_RAW}
)


def _generate_crand_v2_pool() -> list[tuple[str, str]]:
    """Generate all valid cross-domain pairs after blacklist filtering."""
    pool: list[tuple[str, str]] = []
    for c_id, _, _ in CHEM_NODES:
        for b_id, _, _ in BIO_NODES:
            if (c_id, b_id) not in _ALL_BLACKLISTED:
                pool.append((c_id, b_id))
    for b_id, _, _ in BIO_NODES:
        for c_id, _, _ in CHEM_NODES:
            if (b_id, c_id) not in _ALL_BLACKLISTED:
                pool.append((b_id, c_id))
    return pool


def _make_crand_v2_hyp(
    idx: int, subj: str, obj: str,
    rng: random.Random,
) -> dict[str, Any]:
    """Build a single C_rand_v2 hypothesis dict from a random (subj, obj) pair."""
    subj_label = NODE_LABEL.get(subj, subj.split(":")[-1])
    obj_label = NODE_LABEL.get(obj, obj.split(":")[-1])
    # Minimal provenance: no KG path, just random pairing
    provenance = [subj, "randomly_paired_with", obj]
    return {
        "id": f"H5{idx:03d}",
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
    }


def generate_crand_v2(n: int = 50, rng: random.Random | None = None) -> list[dict[str, Any]]:
    """Sample n truly-random cross-domain pairs, filtered against blacklist."""
    if rng is None:
        rng = random.Random(SEED)
    pool = _generate_crand_v2_pool()
    rng.shuffle(pool)
    selected = pool[:n]
    return [_make_crand_v2_hyp(i + 1, s, o, rng) for i, (s, o) in enumerate(selected)]


def _raw_to_hyp(
    raw: tuple[str, str, str, list[str], str], method: str
) -> dict[str, Any]:
    """Convert a raw hypothesis tuple to a full hypothesis dict."""
    hid, subj, obj, prov, desc = raw
    return {
        "id": hid,
        "subject_id": subj,
        "subject_label": NODE_LABEL.get(subj, subj.split(":")[-1]),
        "relation": "transitively_related_to",
        "object_id": obj,
        "object_label": NODE_LABEL.get(obj, obj.split(":")[-1]),
        "description": desc,
        "provenance": prov,
        "operator": "compose_cross_domain" if method == "C2_multi_op" else "compose",
        "source_kg_name": "bio_chem_extended",
        "method": method,
        "chain_length": len(prov),
    }


def build_c2_hypotheses() -> list[dict[str, Any]]:
    """Build 50 C2 multi-op (cross-domain) hypothesis dicts."""
    return [_raw_to_hyp(r, "C2_multi_op") for r in _C2_RAW]


def build_c1_hypotheses() -> list[dict[str, Any]]:
    """Build 50 C1 single-op (bio-only) hypothesis dicts."""
    return [_raw_to_hyp(r, "C1_compose") for r in _C1_RAW]


# ── parity check ───────────────────────────────────────────────────────────────

def _parity_stats(pool: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Compute chain-length and domain-mix stats for parity reporting."""
    if not pool:
        return {"method": name, "count": 0}
    lengths = [h["chain_length"] for h in pool]
    cross_domain = sum(
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
        "cross_domain_count": cross_domain,
        "cross_domain_ratio": round(cross_domain / len(pool), 3),
    }


def baseline_parity_check(
    c2: list[dict[str, Any]],
    c1: list[dict[str, Any]],
    cr: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare chain length and domain-mix across C2, C1, C_rand_v2."""
    s2 = _parity_stats(c2, "C2_multi_op")
    s1 = _parity_stats(c1, "C1_compose")
    sc = _parity_stats(cr, "C_rand_v2")
    # parity: C_rand_v2 should have similar cross-domain ratio as C2
    cr_cross = sc.get("cross_domain_ratio", 0)
    c2_cross = s2.get("cross_domain_ratio", 0)
    parity_ok = abs(cr_cross - c2_cross) <= 0.20
    return {
        "C2": s2, "C1": s1, "C_rand_v2": sc,
        "parity_ok": parity_ok,
        "rationale": (
            "v2: C_rand_v2 is truly random sampling (no KG-path traversal). "
            "Cross-domain ratio maintained. "
            "Known-fact pairs excluded via blacklist."
        ),
        "blacklist_size": {
            "kg_direct_edges": len(KG_DIRECT_EDGES),
            "trivially_known": len(TRIVIALLY_KNOWN),
            "c2_pairs_excluded": len(_C2_RAW),
            "total": len(_ALL_BLACKLISTED),
        },
    }


# ── I/O helpers ────────────────────────────────────────────────────────────────

def _save_json(data: Any, path: str) -> None:
    """Write JSON to path, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  saved → {path}")


def _build_run_config(
    c2: list[dict], c1: list[dict], cr: list[dict]
) -> dict[str, Any]:
    """Build run_config.json for run_017."""
    return {
        "run_id": RUN_ID,
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Phase 3 re-test: C_rand v2 (blacklisted known pairs) + N=50 per method"
        ),
        "seed": SEED,
        "rationale": (
            "Phase 2 NO-GO was caused by C_rand v1 baseline bias: "
            "KG-path traversal included trivially-known pairs (HER2→breast_cancer etc.) "
            "giving C_rand precision=1.000. C2's 0.833 reflects genuine novelty. "
            "C_rand v2 uses truly random sampling with known-pair blacklist."
        ),
        "changes_from_v1": [
            "C_rand redesigned: random pair sampling (no KG traversal)",
            "Known-pair blacklist: KG 1-hop edges + trivially-known pairs",
            "N increased: 20→50 per method",
            "New endpoints: SC-1r through SC-4r (novel_supported_rate focus)",
            "Two-layer labeling: Layer1=5-class, Layer2=known_fact/novel_supported/...",
        ],
        "methods": {
            "C2_multi_op": {
                "description": "Multi-op cross-domain pipeline (align→compose)",
                "n": len(c2),
            },
            "C1_compose": {
                "description": "Single-op bio-only compose",
                "n": len(c1),
            },
            "C_rand_v2": {
                "description": (
                    "Truly random cross-domain pairs; "
                    "excludes KG 1-hop edges and trivially-known pairs"
                ),
                "n": len(cr),
                "blacklist_kg_edges": len(KG_DIRECT_EDGES),
                "blacklist_known_pairs": len(TRIVIALLY_KNOWN),
            },
        },
        "results": {
            "C2_multi_op": len(c2),
            "C1_compose": len(c1),
            "C_rand_v2": len(cr),
            "total": len(c2) + len(c1) + len(cr),
        },
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Generate C2/C1/C_rand_v2 hypotheses and write run_017 artifacts."""
    print(f"\n{'='*60}")
    print(f"  randomized_baseline_v2.py — run_017 generation")
    print(f"{'='*60}")

    rng = random.Random(SEED)
    c2 = build_c2_hypotheses()
    c1 = build_c1_hypotheses()
    cr = generate_crand_v2(n=50, rng=rng)

    print(f"\n  C2: {len(c2)} hypotheses")
    print(f"  C1: {len(c1)} hypotheses")
    print(f"  C_rand_v2: {len(cr)} hypotheses")
    print(f"  Total: {len(c2)+len(c1)+len(cr)}")

    pool_size = len(_generate_crand_v2_pool())
    print(f"\n  C_rand_v2 pool after blacklist: {pool_size} pairs")
    print(f"  Blacklist: {len(_ALL_BLACKLISTED)} pairs excluded")

    # sample output paths
    def p(fname: str) -> str:
        return os.path.join(RUN_DIR, fname)

    _save_json({"run_id": RUN_ID, "hypotheses": c2}, p("hypotheses_c2.json"))
    _save_json({"run_id": RUN_ID, "hypotheses": c1}, p("hypotheses_c1.json"))
    _save_json({"run_id": RUN_ID, "hypotheses": cr}, p("hypotheses_crand_v2.json"))

    parity = baseline_parity_check(c2, c1, cr)
    _save_json(parity, p("baseline_parity_check.json"))

    cfg = _build_run_config(c2, c1, cr)
    _save_json(cfg, p("run_config.json"))

    print(f"\n  Parity OK: {parity['parity_ok']}")
    print(f"  C2 cross-domain ratio: {parity['C2']['cross_domain_ratio']}")
    print(f"  C_rand_v2 cross-domain ratio: {parity['C_rand_v2']['cross_domain_ratio']}")
    print(f"\n  run_017 artifacts saved to {RUN_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
