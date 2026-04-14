"""Build P8 KG: expanded ROS/oxidative-stress bridge family.

P8 hypothesis: the ROS single-point dependence (run_039) can be evolved into a
design principle by expanding the oxidative stress bridge family with antioxidant
enzymes and stress-response regulators that have comparable PubMed coverage.

P7 ROS family (2 nodes):
  reactive_oxygen_species, glutathione

P8 extended ROS family adds 5 nodes:
  superoxide_dismutase, catalase, heme_oxygenase_1, nrf2, malondialdehyde

All 5 new nodes follow the same bridge mechanism:
  chem(oxidative_stress_node) receives bio→chem edges (biology induces/produces/activates)
  chem(oxidative_stress_node) sends chem→bio edges (node affects diseases/processes)

Usage:
    python -m src.scientific_hypothesis.build_p8_kg
"""
from __future__ import annotations

import json
import os
from typing import Any

from src.scientific_hypothesis.build_p7_kg import (
    build_p7_kg_data,
    load_base_kg,
    _merge_nodes,
    _merge_edges,
    _node_domain_from_id,
)

P8_KG_PATH = os.path.join(os.path.dirname(__file__), "bio_chem_kg_p8.json")

# ---------------------------------------------------------------------------
# P8 extended ROS family nodes (chemistry domain)
# All 5 are antioxidant or oxidative-stress response entities.
# They follow the same bridge mechanism as P7: bio→chem incoming, chem→bio outgoing.
# ---------------------------------------------------------------------------

_P8_EXTENDED_ROS_NODES: list[dict[str, Any]] = [
    {"id": "chem:metabolite:superoxide_dismutase",
     "label": "Superoxide Dismutase (SOD)",
     "domain": "chemistry",
     "attributes": {"type": "antioxidant_enzyme", "class": "metalloenzyme",
                    "bridge_role": "ROS-scavenging-neurodegeneration axis"}},
    {"id": "chem:metabolite:catalase",
     "label": "Catalase",
     "domain": "chemistry",
     "attributes": {"type": "antioxidant_enzyme", "class": "heme_enzyme",
                    "bridge_role": "H2O2-clearance-oxidative-damage axis"}},
    {"id": "chem:metabolite:heme_oxygenase_1",
     "label": "Heme Oxygenase-1 (HO-1)",
     "domain": "chemistry",
     "attributes": {"type": "cytoprotective_enzyme", "class": "stress_response",
                    "bridge_role": "oxidative-stress-cytoprotection axis"}},
    {"id": "chem:metabolite:nrf2",
     "label": "NRF2 (Antioxidant Response Activator)",
     "domain": "chemistry",
     "attributes": {"type": "transcription_regulator", "class": "master_antioxidant",
                    "bridge_role": "oxidative-stress-antioxidant-response axis"}},
    {"id": "chem:metabolite:malondialdehyde",
     "label": "Malondialdehyde (MDA)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "542-78-9",
                    "class": "lipid_peroxidation_product",
                    "bridge_role": "lipid-peroxidation-neurodegeneration axis"}},
]

# PubMed search terms for P8 new nodes
P8_ENTITY_TERMS: dict[str, str] = {
    "chem:metabolite:superoxide_dismutase": "superoxide dismutase",
    "chem:metabolite:catalase": "catalase",
    "chem:metabolite:heme_oxygenase_1": "heme oxygenase 1",
    "chem:metabolite:nrf2": "NRF2",
    "chem:metabolite:malondialdehyde": "malondialdehyde",
}

# ---------------------------------------------------------------------------
# P8 bio→chem edges (biology producing/inducing oxidative stress nodes)
# Same mechanism as P7: these enable multi-crossing paths.
# ---------------------------------------------------------------------------

_P8_BIO_TO_CHEM_EDGES: list[dict[str, Any]] = [
    # Superoxide dismutase — induced by oxidative stress; depleted by mitochondrial dysfunction
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "induces", "target_id": "chem:metabolite:superoxide_dismutase", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "reduces", "target_id": "chem:metabolite:superoxide_dismutase", "weight": 0.80},
    {"source_id": "bio:process:ros_production",
     "relation": "requires", "target_id": "chem:metabolite:superoxide_dismutase", "weight": 0.90},
    {"source_id": "bio:pathway:nfkb_pathway",
     "relation": "regulates", "target_id": "chem:metabolite:superoxide_dismutase", "weight": 0.70},

    # Catalase — induced by oxidative stress; depleted by H2O2 overload
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "induces", "target_id": "chem:metabolite:catalase", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "reduces", "target_id": "chem:metabolite:catalase", "weight": 0.75},
    {"source_id": "bio:process:ros_production",
     "relation": "activates", "target_id": "chem:metabolite:catalase", "weight": 0.85},
    {"source_id": "bio:process:cell_senescence",
     "relation": "reduces", "target_id": "chem:metabolite:catalase", "weight": 0.70},

    # Heme oxygenase-1 — induced by oxidative stress, inflammation, NF-kB
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "induces", "target_id": "chem:metabolite:heme_oxygenase_1", "weight": 0.90},
    {"source_id": "bio:process:inflammatory_cytokine_release",
     "relation": "upregulates", "target_id": "chem:metabolite:heme_oxygenase_1", "weight": 0.80},
    {"source_id": "bio:pathway:nfkb_pathway",
     "relation": "activates", "target_id": "chem:metabolite:heme_oxygenase_1", "weight": 0.75},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "induces", "target_id": "chem:metabolite:heme_oxygenase_1", "weight": 0.75},

    # NRF2 — activated by oxidative stress and ROS (core sensor of redox state)
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "activates", "target_id": "chem:metabolite:nrf2", "weight": 0.90},
    {"source_id": "bio:process:ros_production",
     "relation": "activates", "target_id": "chem:metabolite:nrf2", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "activates", "target_id": "chem:metabolite:nrf2", "weight": 0.80},
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "activates", "target_id": "chem:metabolite:nrf2", "weight": 0.75},

    # Malondialdehyde — lipid peroxidation product, accumulates in neurodegeneration
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "produces", "target_id": "chem:metabolite:malondialdehyde", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "generates", "target_id": "chem:metabolite:malondialdehyde", "weight": 0.80},
    {"source_id": "bio:process:neurodegeneration",
     "relation": "accumulates", "target_id": "chem:metabolite:malondialdehyde", "weight": 0.70},
    {"source_id": "bio:process:cell_senescence",
     "relation": "accumulates", "target_id": "chem:metabolite:malondialdehyde", "weight": 0.65},
]

# ---------------------------------------------------------------------------
# P8 chem→bio edges (oxidative stress nodes affecting diseases/processes)
# ---------------------------------------------------------------------------

_P8_CHEM_TO_BIO_EDGES: list[dict[str, Any]] = [
    # Superoxide dismutase → disease/process links
    {"source_id": "chem:metabolite:superoxide_dismutase",
     "relation": "reduces", "target_id": "bio:process:ros_production", "weight": 0.90},
    {"source_id": "chem:metabolite:superoxide_dismutase",
     "relation": "protects_against", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:superoxide_dismutase",
     "relation": "protects_against", "target_id": "bio:disease:parkinsons", "weight": 0.65},
    {"source_id": "chem:metabolite:superoxide_dismutase",
     "relation": "protects_against", "target_id": "bio:disease:alzheimers", "weight": 0.60},
    {"source_id": "chem:metabolite:superoxide_dismutase",
     "relation": "reduces", "target_id": "bio:process:cell_senescence", "weight": 0.70},

    # Catalase → disease/process links
    {"source_id": "chem:metabolite:catalase",
     "relation": "reduces", "target_id": "bio:process:ros_production", "weight": 0.90},
    {"source_id": "chem:metabolite:catalase",
     "relation": "protects_against", "target_id": "bio:process:neurodegeneration", "weight": 0.75},
    {"source_id": "chem:metabolite:catalase",
     "relation": "reduces", "target_id": "bio:disease:parkinsons", "weight": 0.60},
    {"source_id": "chem:metabolite:catalase",
     "relation": "reduces", "target_id": "bio:process:cell_senescence", "weight": 0.65},
    {"source_id": "chem:metabolite:catalase",
     "relation": "reduces", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.65},

    # Heme oxygenase-1 → disease/process links
    {"source_id": "chem:metabolite:heme_oxygenase_1",
     "relation": "protects_against", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:heme_oxygenase_1",
     "relation": "reduces", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.75},
    {"source_id": "chem:metabolite:heme_oxygenase_1",
     "relation": "protects_against", "target_id": "bio:disease:parkinsons", "weight": 0.65},
    {"source_id": "chem:metabolite:heme_oxygenase_1",
     "relation": "protects_against", "target_id": "bio:disease:alzheimers", "weight": 0.65},
    {"source_id": "chem:metabolite:heme_oxygenase_1",
     "relation": "reduces", "target_id": "bio:disease:rheumatoid_arthritis", "weight": 0.55},
    {"source_id": "chem:metabolite:heme_oxygenase_1",
     "relation": "reduces", "target_id": "bio:disease:heart_failure", "weight": 0.55},

    # NRF2 → disease/process links (master antioxidant regulator)
    {"source_id": "chem:metabolite:nrf2",
     "relation": "activates", "target_id": "bio:pathway:autophagy", "weight": 0.80},
    {"source_id": "chem:metabolite:nrf2",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:nrf2",
     "relation": "inhibits", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.75},
    {"source_id": "chem:metabolite:nrf2",
     "relation": "protects_against", "target_id": "bio:disease:parkinsons", "weight": 0.65},
    {"source_id": "chem:metabolite:nrf2",
     "relation": "protects_against", "target_id": "bio:disease:alzheimers", "weight": 0.65},
    {"source_id": "chem:metabolite:nrf2",
     "relation": "inhibits", "target_id": "bio:disease:colon_cancer", "weight": 0.55},
    {"source_id": "chem:metabolite:nrf2",
     "relation": "reduces", "target_id": "bio:process:cell_senescence", "weight": 0.70},

    # Malondialdehyde → disease/process links (damage marker)
    {"source_id": "chem:metabolite:malondialdehyde",
     "relation": "promotes", "target_id": "bio:process:neurodegeneration", "weight": 0.75},
    {"source_id": "chem:metabolite:malondialdehyde",
     "relation": "promotes", "target_id": "bio:disease:alzheimers", "weight": 0.65},
    {"source_id": "chem:metabolite:malondialdehyde",
     "relation": "promotes", "target_id": "bio:process:cell_senescence", "weight": 0.70},
    {"source_id": "chem:metabolite:malondialdehyde",
     "relation": "promotes", "target_id": "bio:disease:parkinsons", "weight": 0.60},
    {"source_id": "chem:metabolite:malondialdehyde",
     "relation": "activates", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.65},
]

# All P7 metabolite node IDs (used to define conditions)
P7_METABOLITE_IDS: list[str] = [
    "chem:metabolite:nad_plus",
    "chem:metabolite:glutathione",
    "chem:metabolite:ceramide",
    "chem:metabolite:prostaglandin_e2",
    "chem:metabolite:nitric_oxide",
    "chem:metabolite:camp",
    "chem:metabolite:reactive_oxygen_species",
    "chem:metabolite:beta_hydroxybutyrate",
    "chem:metabolite:kynurenine",
    "chem:metabolite:lactate",
]

# P8 new metabolite node IDs
P8_METABOLITE_IDS: list[str] = [
    "chem:metabolite:superoxide_dismutase",
    "chem:metabolite:catalase",
    "chem:metabolite:heme_oxygenase_1",
    "chem:metabolite:nrf2",
    "chem:metabolite:malondialdehyde",
]

# All chemistry-domain bridge metabolite IDs in P8 KG
ALL_BRIDGE_IDS: list[str] = P7_METABOLITE_IDS + P8_METABOLITE_IDS


def build_p8_kg_data(p7_kg: dict[str, Any]) -> dict[str, Any]:
    """Merge P8 extended ROS family nodes/edges into P7 KG.

    Returns the P8 KG dict with updated metadata.
    """
    nodes = _merge_nodes(p7_kg["nodes"], _P8_EXTENDED_ROS_NODES)
    valid_ids = {n["id"] for n in nodes}

    all_new_edges = _P8_BIO_TO_CHEM_EDGES + _P8_CHEM_TO_BIO_EDGES
    edges = _merge_edges(p7_kg["edges"], all_new_edges, valid_ids)

    bio_n = sum(1 for n in nodes if n["domain"] == "biology")
    chem_n = sum(1 for n in nodes if n["domain"] == "chemistry")
    cross_e = [
        e for e in edges
        if _node_domain_from_id(e["source_id"]) != _node_domain_from_id(e["target_id"])
    ]
    cd_density = round(len(cross_e) / len(edges), 4) if edges else 0.0

    metadata = {
        "description": "P8 KG: expanded ROS/oxidative-stress bridge family",
        "version": "3.1-p8",
        "base_version": "3.0-p7",
        "node_count": len(nodes),
        "biology_nodes": bio_n,
        "chemistry_nodes": chem_n,
        "edge_count": len(edges),
        "cross_domain_edge_count": len(cross_e),
        "cross_domain_edge_ratio": cd_density,
        "p8_new_nodes": len(_P8_EXTENDED_ROS_NODES),
        "p8_bio_to_chem_edges": len(_P8_BIO_TO_CHEM_EDGES),
        "p8_chem_to_bio_edges": len(_P8_CHEM_TO_BIO_EDGES),
        "domains": ["biology", "chemistry"],
    }
    return {"metadata": metadata, "nodes": nodes, "edges": edges}


def build_p8_from_base() -> dict[str, Any]:
    """Build full P8 KG from scratch (base → P7 → P8)."""
    base_kg = load_base_kg()
    p7_kg = build_p7_kg_data(base_kg)
    return build_p8_kg_data(p7_kg)


def main() -> None:
    """Build P8 KG and save to JSON."""
    print("=== Building P8 KG (extended ROS/oxidative-stress family) ===")
    base_kg = load_base_kg()
    p7_kg = build_p7_kg_data(base_kg)
    print(f"  P7 KG: {p7_kg['metadata']['node_count']} nodes, "
          f"{p7_kg['metadata']['edge_count']} edges")
    print(f"  Adding {len(_P8_EXTENDED_ROS_NODES)} new ROS-family nodes...")
    print(f"  Adding {len(_P8_BIO_TO_CHEM_EDGES)} bio→chem edges...")
    print(f"  Adding {len(_P8_CHEM_TO_BIO_EDGES)} chem→bio edges...")

    p8_data = build_p8_kg_data(p7_kg)
    m = p8_data["metadata"]
    print(f"\nP8 KG:")
    print(f"  Nodes: {m['node_count']} (P7: {p7_kg['metadata']['node_count']})")
    print(f"  Edges: {m['edge_count']} (P7: {p7_kg['metadata']['edge_count']})")
    print(f"  Cross-domain edges: {m['cross_domain_edge_count']}")
    print(f"  cd_density: {m['cross_domain_edge_ratio']}")

    with open(P8_KG_PATH, "w", encoding="utf-8") as f:
        json.dump(p8_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {P8_KG_PATH}")


if __name__ == "__main__":
    main()
