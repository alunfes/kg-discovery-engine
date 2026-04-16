<<<<<<< HEAD
"""Build P9 KG: neurotransmitter bridge family (domain-agnostic validation).

P9 hypothesis: the multi-domain-crossing design principle (P7-P8) generalizes beyond
oxidative stress to any chemistry-domain bridge family with:
  (1) bio→chem incoming edges from existing biology nodes
  (2) chem→bio outgoing edges to literature-rich disease endpoints

P9 adds 5 neurotransmitter chemistry nodes and 3 new disease biology nodes.
Bridge mechanism (same as P7/P8):
  biology_node → produces/depletes → chem:NT → affects → biology_disease
=======
"""Build P9 KG: neurotransmitter (NT) bridge family for domain-transfer test.

P9 hypothesis: the design principle discovered via oxidative-stress bridges
(high-cdr + 2024-2025 literature coverage) generalises to an entirely different
molecular family — classical neurotransmitters.

P8 ROS family (7 nodes, already in P8 KG):
  reactive_oxygen_species, glutathione,
  superoxide_dismutase, catalase, heme_oxygenase_1, nrf2, malondialdehyde

P9 adds 5 neurotransmitter nodes:
  dopamine, serotonin, norepinephrine, acetylcholine, gaba

All 5 follow the same bridge mechanism:
  chem(nt_node) receives bio→chem edges  (biological processes regulate them)
  chem(nt_node) sends   chem→bio edges   (node affects diseases / processes)
>>>>>>> claude/zealous-matsumoto

Usage:
    python -m src.scientific_hypothesis.build_p9_kg
"""
from __future__ import annotations

import json
import os
from typing import Any

<<<<<<< HEAD
from src.scientific_hypothesis.build_p7_kg import (
    load_base_kg,
    _merge_nodes,
    _merge_edges,
    _node_domain_from_id,
    build_p7_kg_data,
)
from src.scientific_hypothesis.build_p8_kg import build_p8_kg_data
=======
from src.scientific_hypothesis.build_p8_kg import (
    build_p8_from_base,
    _merge_nodes,
    _merge_edges,
    _node_domain_from_id,
    P7_METABOLITE_IDS,
    P8_METABOLITE_IDS,
)
>>>>>>> claude/zealous-matsumoto

P9_KG_PATH = os.path.join(os.path.dirname(__file__), "bio_chem_kg_p9.json")

# ---------------------------------------------------------------------------
<<<<<<< HEAD
# P9 neurotransmitter chemistry nodes
# All placed in chemistry domain to enable multi-crossing paths.
# Bridge mechanism: bio_node → depletes/releases → chem:NT → affects → bio_disease
# ---------------------------------------------------------------------------

_P9_NT_NODES: list[dict[str, Any]] = [
    {"id": "chem:neurotransmitter:dopamine",
     "label": "Dopamine",
     "domain": "chemistry",
     "attributes": {"type": "neurotransmitter", "class": "catecholamine",
                    "bridge_role": "dopaminergic-Parkinson-schizophrenia axis"}},
    {"id": "chem:neurotransmitter:serotonin",
     "label": "Serotonin (5-HT)",
     "domain": "chemistry",
     "attributes": {"type": "neurotransmitter", "class": "monoamine",
                    "bridge_role": "serotonergic-depression-Alzheimer axis"}},
    {"id": "chem:neurotransmitter:gaba",
     "label": "GABA (γ-aminobutyric acid)",
     "domain": "chemistry",
     "attributes": {"type": "neurotransmitter", "class": "inhibitory_amino_acid",
                    "bridge_role": "GABAergic-epilepsy-neurodegeneration axis"}},
    {"id": "chem:neurotransmitter:glutamate",
     "label": "Glutamate",
     "domain": "chemistry",
     "attributes": {"type": "neurotransmitter", "class": "excitatory_amino_acid",
                    "bridge_role": "excitotoxicity-neurodegeneration-Alzheimer axis"}},
    {"id": "chem:neurotransmitter:acetylcholine",
     "label": "Acetylcholine",
     "domain": "chemistry",
     "attributes": {"type": "neurotransmitter", "class": "cholinergic",
                    "bridge_role": "cholinergic-Alzheimer-neuroinflammation axis"}},
]

# New biology disease nodes (NT-specific endpoints)
_P9_NEW_DISEASE_NODES: list[dict[str, Any]] = [
    {"id": "bio:disease:major_depression",
     "label": "Major Depressive Disorder",
     "domain": "biology",
     "attributes": {"type": "psychiatric_disease", "category": "mood_disorder"}},
    {"id": "bio:disease:schizophrenia",
     "label": "Schizophrenia",
     "domain": "biology",
     "attributes": {"type": "psychiatric_disease", "category": "psychotic_disorder"}},
    {"id": "bio:disease:epilepsy",
     "label": "Epilepsy",
     "domain": "biology",
     "attributes": {"type": "neurological_disease", "category": "seizure_disorder"}},
]

# PubMed search terms for P9 nodes
P9_ENTITY_TERMS: dict[str, str] = {
    "chem:neurotransmitter:dopamine": "dopamine",
    "chem:neurotransmitter:serotonin": "serotonin",
    "chem:neurotransmitter:gaba": "GABA",
    "chem:neurotransmitter:glutamate": "glutamate",
    "chem:neurotransmitter:acetylcholine": "acetylcholine",
    "bio:disease:major_depression": "major depressive disorder",
    "bio:disease:schizophrenia": "schizophrenia",
    "bio:disease:epilepsy": "epilepsy",
}

# IDs of P9 NT chemistry bridge nodes
P9_NT_IDS: list[str] = [
    "chem:neurotransmitter:dopamine",
    "chem:neurotransmitter:serotonin",
    "chem:neurotransmitter:gaba",
    "chem:neurotransmitter:glutamate",
    "chem:neurotransmitter:acetylcholine",
]

# ---------------------------------------------------------------------------
# P9 bio→chem edges (biology depletes/produces/releases NT)
# Sources: biology nodes with existing chem-incoming edges in base KG.
# Verified reachable sources: neuroinflammation (3), dopamine_synthesis (1),
# apoptosis (3), nfkb_pathway (2), mitochondrial_dysfunction (1), oxidative_stress (2)
# ---------------------------------------------------------------------------

_P9_BIO_TO_NT_EDGES: list[dict[str, Any]] = [
    # Dopamine — produced by dopamine_synthesis; depleted by neuroinflammation/apoptosis
    {"source_id": "bio:process:dopamine_synthesis",
     "relation": "produces", "target_id": "chem:neurotransmitter:dopamine", "weight": 0.95},
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:neurotransmitter:dopamine", "weight": 0.80},
    {"source_id": "bio:pathway:apoptosis",
     "relation": "depletes", "target_id": "chem:neurotransmitter:dopamine", "weight": 0.75},

    # Serotonin — depleted by neuroinflammation, NF-kB (IDO pathway), mitochondrial dysfunction
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "depletes", "target_id": "chem:neurotransmitter:serotonin", "weight": 0.80},
    {"source_id": "bio:pathway:nfkb_pathway",
     "relation": "reduces", "target_id": "chem:neurotransmitter:serotonin", "weight": 0.75},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "depletes", "target_id": "chem:neurotransmitter:serotonin", "weight": 0.70},

    # GABA — disrupted by neuroinflammation; reduced by apoptosis and oxidative stress
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "disrupts", "target_id": "chem:neurotransmitter:gaba", "weight": 0.75},
    {"source_id": "bio:pathway:apoptosis",
     "relation": "reduces", "target_id": "chem:neurotransmitter:gaba", "weight": 0.70},
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "reduces", "target_id": "chem:neurotransmitter:gaba", "weight": 0.70},

    # Glutamate — elevated by mitochondrial dysfunction (excitotoxicity); released by neuroinflammation
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "elevates", "target_id": "chem:neurotransmitter:glutamate", "weight": 0.80},
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "releases", "target_id": "chem:neurotransmitter:glutamate", "weight": 0.85},
    {"source_id": "bio:pathway:apoptosis",
     "relation": "releases", "target_id": "chem:neurotransmitter:glutamate", "weight": 0.75},

    # Acetylcholine — reduced by neuroinflammation, apoptosis, NF-kB
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:neurotransmitter:acetylcholine", "weight": 0.80},
    {"source_id": "bio:pathway:apoptosis",
     "relation": "depletes", "target_id": "chem:neurotransmitter:acetylcholine", "weight": 0.75},
    {"source_id": "bio:pathway:nfkb_pathway",
     "relation": "reduces", "target_id": "chem:neurotransmitter:acetylcholine", "weight": 0.70},
]

# ---------------------------------------------------------------------------
# P9 chem→bio edges (NT affects diseases/processes)
# Targets: existing diseases (parkinsons, alzheimers, huntingtons) + new disease nodes
# ---------------------------------------------------------------------------

_P9_NT_TO_BIO_EDGES: list[dict[str, Any]] = [
    # Dopamine → disease/process links
    {"source_id": "chem:neurotransmitter:dopamine",
     "relation": "deficiency_in", "target_id": "bio:disease:parkinsons", "weight": 0.90},
    {"source_id": "chem:neurotransmitter:dopamine",
     "relation": "dysregulated_in", "target_id": "bio:disease:schizophrenia", "weight": 0.85},
    {"source_id": "chem:neurotransmitter:dopamine",
     "relation": "modulates", "target_id": "bio:process:neurodegeneration", "weight": 0.75},
    {"source_id": "chem:neurotransmitter:dopamine",
     "relation": "regulates", "target_id": "bio:process:dopamine_synthesis", "weight": 0.80},

    # Serotonin → disease/process links
    {"source_id": "chem:neurotransmitter:serotonin",
     "relation": "deficiency_in", "target_id": "bio:disease:major_depression", "weight": 0.90},
    {"source_id": "chem:neurotransmitter:serotonin",
     "relation": "influences", "target_id": "bio:disease:alzheimers", "weight": 0.65},
    {"source_id": "chem:neurotransmitter:serotonin",
     "relation": "modulates", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.70},
    {"source_id": "chem:neurotransmitter:serotonin",
     "relation": "modulates", "target_id": "bio:pathway:neuroinflammation", "weight": 0.65},

    # GABA → disease/process links
    {"source_id": "chem:neurotransmitter:gaba",
     "relation": "deficiency_in", "target_id": "bio:disease:epilepsy", "weight": 0.90},
    {"source_id": "chem:neurotransmitter:gaba",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.70},
    {"source_id": "chem:neurotransmitter:gaba",
     "relation": "inhibits", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.65},

    # Glutamate → disease/process links
    {"source_id": "chem:neurotransmitter:glutamate",
     "relation": "drives", "target_id": "bio:process:neurodegeneration", "weight": 0.85},
    {"source_id": "chem:neurotransmitter:glutamate",
     "relation": "causes", "target_id": "bio:disease:alzheimers", "weight": 0.70},
    {"source_id": "chem:neurotransmitter:glutamate",
     "relation": "promotes", "target_id": "bio:disease:huntingtons", "weight": 0.70},
    {"source_id": "chem:neurotransmitter:glutamate",
     "relation": "activates", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.70},

    # Acetylcholine → disease/process links
    {"source_id": "chem:neurotransmitter:acetylcholine",
     "relation": "deficiency_causes", "target_id": "bio:disease:alzheimers", "weight": 0.90},
    {"source_id": "chem:neurotransmitter:acetylcholine",
     "relation": "modulates", "target_id": "bio:pathway:neuroinflammation", "weight": 0.70},
    {"source_id": "chem:neurotransmitter:acetylcholine",
     "relation": "protects_against", "target_id": "bio:process:neurodegeneration", "weight": 0.75},
    {"source_id": "chem:neurotransmitter:acetylcholine",
     "relation": "modulates", "target_id": "bio:process:immune_activation", "weight": 0.65},
]


def build_p9_kg_data(p8_kg: dict[str, Any]) -> dict[str, Any]:
    """Merge P9 neurotransmitter bridge nodes/edges into P8 KG.

    Adds both chemistry NT nodes and new biology disease nodes.
    Returns the P9 KG dict with updated metadata.
    """
    # Merge chemistry NT nodes and biology disease nodes
    all_new_nodes = _P9_NT_NODES + _P9_NEW_DISEASE_NODES
    nodes = _merge_nodes(p8_kg["nodes"], all_new_nodes)
    valid_ids = {n["id"] for n in nodes}

    all_new_edges = _P9_BIO_TO_NT_EDGES + _P9_NT_TO_BIO_EDGES
=======
# P9 neurotransmitter nodes (chemistry domain)
# Classical NTs: each is a small molecule with rich biomedical PubMed coverage.
# Bridge mechanism identical to ROS family: bio→chem incoming, chem→bio outgoing.
# ---------------------------------------------------------------------------

_P9_NT_NODES: list[dict[str, Any]] = [
    {"id": "chem:metabolite:dopamine",
     "label": "Dopamine",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "51-61-6",
                    "class": "catecholamine_neurotransmitter",
                    "bridge_role": "dopamine-synthesis-neurodegeneration axis"}},
    {"id": "chem:metabolite:serotonin",
     "label": "Serotonin (5-HT)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "50-67-9",
                    "class": "monoamine_neurotransmitter",
                    "bridge_role": "synaptic-plasticity-neurodegeneration axis"}},
    {"id": "chem:metabolite:norepinephrine",
     "label": "Norepinephrine (NE)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "51-41-2",
                    "class": "catecholamine_neurotransmitter",
                    "bridge_role": "stress-response-cardiovascular axis"}},
    {"id": "chem:metabolite:acetylcholine",
     "label": "Acetylcholine (ACh)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "51-84-3",
                    "class": "cholinergic_neurotransmitter",
                    "bridge_role": "cholinergic-deficit-alzheimers axis"}},
    {"id": "chem:metabolite:gaba",
     "label": "GABA (Gamma-Aminobutyric Acid)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "56-12-2",
                    "class": "inhibitory_neurotransmitter",
                    "bridge_role": "inhibitory-signaling-neuroprotection axis"}},
]

# PubMed search terms for P9 new nodes
P9_ENTITY_TERMS: dict[str, str] = {
    "chem:metabolite:dopamine": "dopamine",
    "chem:metabolite:serotonin": "serotonin",
    "chem:metabolite:norepinephrine": "norepinephrine",
    "chem:metabolite:acetylcholine": "acetylcholine",
    "chem:metabolite:gaba": "GABA gamma-aminobutyric acid",
}

# ---------------------------------------------------------------------------
# P9 bio→chem edges (biological processes that produce / regulate NTs)
# These edges enable multi-crossing paths by giving NTs bio→chem incoming arcs.
# ---------------------------------------------------------------------------

_P9_BIO_TO_CHEM_EDGES: list[dict[str, Any]] = [
    # Dopamine: produced by dopamine_synthesis; depleted by neuroinflammation / oxidative stress
    {"source_id": "bio:process:dopamine_synthesis",
     "relation": "produces", "target_id": "chem:metabolite:dopamine", "weight": 0.95},
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:metabolite:dopamine", "weight": 0.85},
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "degrades", "target_id": "chem:metabolite:dopamine", "weight": 0.80},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "impairs", "target_id": "chem:metabolite:dopamine", "weight": 0.80},
    {"source_id": "bio:protein:lrrk2",
     "relation": "regulates", "target_id": "chem:metabolite:dopamine", "weight": 0.75},

    # Serotonin: regulated by BDNF / inflammation / mitochondrial dysfunction
    {"source_id": "bio:protein:bdnf",
     "relation": "supports", "target_id": "chem:metabolite:serotonin", "weight": 0.80},
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:metabolite:serotonin", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "reduces", "target_id": "chem:metabolite:serotonin", "weight": 0.75},
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "depletes", "target_id": "chem:metabolite:serotonin", "weight": 0.75},
    {"source_id": "bio:process:cell_senescence",
     "relation": "reduces", "target_id": "chem:metabolite:serotonin", "weight": 0.65},

    # Norepinephrine: regulated by inflammation, stress response, BDNF
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:metabolite:norepinephrine", "weight": 0.80},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "impairs", "target_id": "chem:metabolite:norepinephrine", "weight": 0.70},
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "degrades", "target_id": "chem:metabolite:norepinephrine", "weight": 0.75},
    {"source_id": "bio:process:inflammatory_cytokine_release",
     "relation": "dysregulates", "target_id": "chem:metabolite:norepinephrine", "weight": 0.70},

    # Acetylcholine: synthesised by cholinergic neurons; depleted in Alzheimer's
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:metabolite:acetylcholine", "weight": 0.90},
    {"source_id": "bio:process:beta_amyloid_aggregation",
     "relation": "reduces", "target_id": "chem:metabolite:acetylcholine", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "impairs", "target_id": "chem:metabolite:acetylcholine", "weight": 0.75},
    {"source_id": "bio:pathway:tau_phosphorylation",
     "relation": "reduces", "target_id": "chem:metabolite:acetylcholine", "weight": 0.80},
    {"source_id": "bio:protein:app",
     "relation": "indirectly_reduces", "target_id": "chem:metabolite:acetylcholine", "weight": 0.70},

    # GABA: inhibitory; reduced by neuroinflammation and oxidative stress
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "reduces", "target_id": "chem:metabolite:gaba", "weight": 0.80},
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "impairs", "target_id": "chem:metabolite:gaba", "weight": 0.70},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "reduces", "target_id": "chem:metabolite:gaba", "weight": 0.70},
    {"source_id": "bio:process:inflammatory_cytokine_release",
     "relation": "inhibits_synthesis", "target_id": "chem:metabolite:gaba", "weight": 0.65},
]

# ---------------------------------------------------------------------------
# P9 chem→bio edges (NT nodes affecting diseases / biological processes)
# ---------------------------------------------------------------------------

_P9_CHEM_TO_BIO_EDGES: list[dict[str, Any]] = [
    # Dopamine → disease / process links
    {"source_id": "chem:metabolite:dopamine",
     "relation": "protects_against", "target_id": "bio:disease:parkinsons", "weight": 0.95},
    {"source_id": "chem:metabolite:dopamine",
     "relation": "activates", "target_id": "bio:receptor:dopamine_d2", "weight": 0.90},
    {"source_id": "chem:metabolite:dopamine",
     "relation": "regulates", "target_id": "bio:process:dopamine_synthesis", "weight": 0.85},
    {"source_id": "chem:metabolite:dopamine",
     "relation": "modulates", "target_id": "bio:process:synaptic_plasticity", "weight": 0.80},
    {"source_id": "chem:metabolite:dopamine",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.75},
    {"source_id": "chem:metabolite:dopamine",
     "relation": "interacts", "target_id": "bio:protein:alpha_syn", "weight": 0.70},

    # Serotonin → disease / process links
    {"source_id": "chem:metabolite:serotonin",
     "relation": "improves", "target_id": "bio:process:synaptic_plasticity", "weight": 0.85},
    {"source_id": "chem:metabolite:serotonin",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:serotonin",
     "relation": "reduces", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.75},
    {"source_id": "chem:metabolite:serotonin",
     "relation": "protects_against", "target_id": "bio:disease:alzheimers", "weight": 0.65},
    {"source_id": "chem:metabolite:serotonin",
     "relation": "supports", "target_id": "bio:protein:bdnf", "weight": 0.70},
    {"source_id": "chem:metabolite:serotonin",
     "relation": "activates", "target_id": "bio:pathway:autophagy", "weight": 0.65},

    # Norepinephrine → disease / process links
    {"source_id": "chem:metabolite:norepinephrine",
     "relation": "modulates", "target_id": "bio:disease:heart_failure", "weight": 0.80},
    {"source_id": "chem:metabolite:norepinephrine",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.70},
    {"source_id": "chem:metabolite:norepinephrine",
     "relation": "modulates", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.70},
    {"source_id": "chem:metabolite:norepinephrine",
     "relation": "affects", "target_id": "bio:process:synaptic_plasticity", "weight": 0.70},
    {"source_id": "chem:metabolite:norepinephrine",
     "relation": "modulates", "target_id": "bio:pathway:neuroinflammation", "weight": 0.65},

    # Acetylcholine → disease / process links
    {"source_id": "chem:metabolite:acetylcholine",
     "relation": "protects_against", "target_id": "bio:disease:alzheimers", "weight": 0.95},
    {"source_id": "chem:metabolite:acetylcholine",
     "relation": "activates", "target_id": "bio:receptor:nmda_receptor", "weight": 0.85},
    {"source_id": "chem:metabolite:acetylcholine",
     "relation": "enhances", "target_id": "bio:process:synaptic_plasticity", "weight": 0.85},
    {"source_id": "chem:metabolite:acetylcholine",
     "relation": "reduces", "target_id": "bio:process:beta_amyloid_aggregation", "weight": 0.75},
    {"source_id": "chem:metabolite:acetylcholine",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:acetylcholine",
     "relation": "reduces", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.65},

    # GABA → disease / process links
    {"source_id": "chem:metabolite:gaba",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:gaba",
     "relation": "reduces", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.75},
    {"source_id": "chem:metabolite:gaba",
     "relation": "modulates", "target_id": "bio:process:synaptic_plasticity", "weight": 0.75},
    {"source_id": "chem:metabolite:gaba",
     "relation": "reduces", "target_id": "bio:disease:als", "weight": 0.60},
    {"source_id": "chem:metabolite:gaba",
     "relation": "inhibits", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.65},
    {"source_id": "chem:metabolite:gaba",
     "relation": "reduces", "target_id": "bio:process:ros_production", "weight": 0.60},
]

# P9 NT metabolite IDs
P9_NT_IDS: list[str] = [
    "chem:metabolite:dopamine",
    "chem:metabolite:serotonin",
    "chem:metabolite:norepinephrine",
    "chem:metabolite:acetylcholine",
    "chem:metabolite:gaba",
]

# All bridge IDs in P9 KG (P7 + P8 + P9 NT)
ALL_BRIDGE_IDS_P9: list[str] = P7_METABOLITE_IDS + P8_METABOLITE_IDS + P9_NT_IDS


def build_p9_kg_data(p8_kg: dict[str, Any]) -> dict[str, Any]:
    """Merge P9 NT nodes/edges into P8 KG.

    Returns the P9 KG dict with updated metadata.
    """
    nodes = _merge_nodes(p8_kg["nodes"], _P9_NT_NODES)
    valid_ids = {n["id"] for n in nodes}

    all_new_edges = _P9_BIO_TO_CHEM_EDGES + _P9_CHEM_TO_BIO_EDGES
>>>>>>> claude/zealous-matsumoto
    edges = _merge_edges(p8_kg["edges"], all_new_edges, valid_ids)

    bio_n = sum(1 for n in nodes if n["domain"] == "biology")
    chem_n = sum(1 for n in nodes if n["domain"] == "chemistry")
    cross_e = [
        e for e in edges
        if _node_domain_from_id(e["source_id"]) != _node_domain_from_id(e["target_id"])
    ]
    cd_density = round(len(cross_e) / len(edges), 4) if edges else 0.0

    metadata = {
<<<<<<< HEAD
        "description": "P9 KG: neurotransmitter bridge family for domain-agnostic validation",
=======
        "description": "P9 KG: NT neurotransmitter bridge family domain-transfer test",
>>>>>>> claude/zealous-matsumoto
        "version": "3.2-p9",
        "base_version": "3.1-p8",
        "node_count": len(nodes),
        "biology_nodes": bio_n,
        "chemistry_nodes": chem_n,
        "edge_count": len(edges),
        "cross_domain_edge_count": len(cross_e),
        "cross_domain_edge_ratio": cd_density,
<<<<<<< HEAD
        "p9_nt_nodes": len(_P9_NT_NODES),
        "p9_new_disease_nodes": len(_P9_NEW_DISEASE_NODES),
        "p9_bio_to_nt_edges": len(_P9_BIO_TO_NT_EDGES),
        "p9_nt_to_bio_edges": len(_P9_NT_TO_BIO_EDGES),
=======
        "p9_new_nodes": len(_P9_NT_NODES),
        "p9_bio_to_chem_edges": len(_P9_BIO_TO_CHEM_EDGES),
        "p9_chem_to_bio_edges": len(_P9_CHEM_TO_BIO_EDGES),
>>>>>>> claude/zealous-matsumoto
        "domains": ["biology", "chemistry"],
    }
    return {"metadata": metadata, "nodes": nodes, "edges": edges}


def build_p9_from_base() -> dict[str, Any]:
    """Build full P9 KG from scratch (base → P7 → P8 → P9)."""
<<<<<<< HEAD
    base_kg = load_base_kg()
    p7_kg = build_p7_kg_data(base_kg)
    p8_kg = build_p8_kg_data(p7_kg)
=======
    p8_kg = build_p8_from_base()
>>>>>>> claude/zealous-matsumoto
    return build_p9_kg_data(p8_kg)


def main() -> None:
    """Build P9 KG and save to JSON."""
<<<<<<< HEAD
    print("=== Building P9 KG (neurotransmitter bridge family) ===")
    base_kg = load_base_kg()
    p7_kg = build_p7_kg_data(base_kg)
    p8_kg = build_p8_kg_data(p7_kg)
    print(f"  P8 KG: {p8_kg['metadata']['node_count']} nodes, "
          f"{p8_kg['metadata']['edge_count']} edges")
    print(f"  Adding {len(_P9_NT_NODES)} NT nodes + "
          f"{len(_P9_NEW_DISEASE_NODES)} disease nodes")
    print(f"  Adding {len(_P9_BIO_TO_NT_EDGES)} bio→NT + "
          f"{len(_P9_NT_TO_BIO_EDGES)} NT→bio edges")
=======
    print("=== Building P9 KG (NT neurotransmitter bridge family) ===")
    p8_kg = build_p8_from_base()
    print(f"  P8 KG: {p8_kg['metadata']['node_count']} nodes, "
          f"{p8_kg['metadata']['edge_count']} edges")
    print(f"  Adding {len(_P9_NT_NODES)} new NT nodes...")
    print(f"  Adding {len(_P9_BIO_TO_CHEM_EDGES)} bio→chem edges...")
    print(f"  Adding {len(_P9_CHEM_TO_BIO_EDGES)} chem→bio edges...")
>>>>>>> claude/zealous-matsumoto

    p9_data = build_p9_kg_data(p8_kg)
    m = p9_data["metadata"]
    print(f"\nP9 KG:")
    print(f"  Nodes: {m['node_count']} (P8: {p8_kg['metadata']['node_count']})")
    print(f"  Edges: {m['edge_count']} (P8: {p8_kg['metadata']['edge_count']})")
    print(f"  Cross-domain edges: {m['cross_domain_edge_count']}")
    print(f"  cd_density: {m['cross_domain_edge_ratio']}")

    with open(P9_KG_PATH, "w", encoding="utf-8") as f:
        json.dump(p9_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {P9_KG_PATH}")


if __name__ == "__main__":
    main()
