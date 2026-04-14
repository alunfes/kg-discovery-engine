"""Build P7 KG: cross-domain metabolite bridge expansion.

P7 hypothesis: chemistry-domain metabolite nodes with both
bio→chem incoming edges AND chem→bio outgoing edges create
multi-crossing paths (chem→bio→chem→bio) that break the geometry ceiling.

Current KG ceiling:
  - Every path has exactly 1 cross-domain edge
  - cross_domain_ratio(L3) = 1/3 = 0.333
  - cross_domain_ratio(L4) = 1/4 = 0.250

P7 bridge metabolites enable:
  - L3 path: chem→bio→chem→bio = 3 crossings / 3 = cdr 1.0
  - L4 path: chem→bio→chem→bio→bio = 3 crossings / 4 = cdr 0.75

Usage:
    python -m src.scientific_hypothesis.build_p7_kg
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BASE_KG_PATH = os.path.join(os.path.dirname(__file__), "bio_chem_kg_full.json")
P7_KG_PATH = os.path.join(os.path.dirname(__file__), "bio_chem_kg_p7.json")


# ---------------------------------------------------------------------------
# P7 bridge nodes — chemistry-domain endogenous metabolites
# Each has edges FROM biology (bio→chem) AND edges TO biology (chem→bio)
# This creates multi-crossing paths: drug→pathway→metabolite→disease
# ---------------------------------------------------------------------------

_P7_METABOLITE_NODES: list[dict[str, Any]] = [
    {"id": "chem:metabolite:nad_plus",
     "label": "NAD+ (Nicotinamide Adenine Dinucleotide)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "53-84-9",
                    "class": "coenzyme", "bridge_role": "AMPK-sirtuin axis"}},
    {"id": "chem:metabolite:glutathione",
     "label": "Glutathione (GSH)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "70-18-8",
                    "class": "antioxidant_tripeptide", "bridge_role": "ROS-neurodegeneration axis"}},
    {"id": "chem:metabolite:ceramide",
     "label": "Ceramide",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "class": "sphingolipid",
                    "bridge_role": "apoptosis-inflammation axis"}},
    {"id": "chem:metabolite:prostaglandin_e2",
     "label": "Prostaglandin E2 (PGE2)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "363-24-6",
                    "class": "eicosanoid", "bridge_role": "NF-kB-inflammation axis"}},
    {"id": "chem:metabolite:nitric_oxide",
     "label": "Nitric Oxide (NO)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "10102-43-9",
                    "class": "signaling_gas", "bridge_role": "neuroinflammation-angiogenesis axis"}},
    {"id": "chem:metabolite:camp",
     "label": "Cyclic AMP (cAMP)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "60-92-4",
                    "class": "second_messenger", "bridge_role": "receptor-autophagy axis"}},
    {"id": "chem:metabolite:reactive_oxygen_species",
     "label": "Reactive Oxygen Species (ROS)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "class": "oxidative_species",
                    "bridge_role": "mitochondrial_dysfunction-NF-kB axis"}},
    {"id": "chem:metabolite:beta_hydroxybutyrate",
     "label": "Beta-Hydroxybutyrate (BHB)",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "300-85-6",
                    "class": "ketone_body", "bridge_role": "metabolism-neuroprotection axis"}},
    {"id": "chem:metabolite:kynurenine",
     "label": "Kynurenine",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "343-65-7",
                    "class": "tryptophan_catabolite",
                    "bridge_role": "neuroinflammation-immune axis"}},
    {"id": "chem:metabolite:lactate",
     "label": "L-Lactate",
     "domain": "chemistry",
     "attributes": {"type": "metabolite", "cas": "79-33-4",
                    "class": "organic_acid",
                    "bridge_role": "Warburg-tumor axis"}},
]

# PubMed search terms for P7 metabolites (used by evidence scoring)
P7_ENTITY_TERMS: dict[str, str] = {
    "chem:metabolite:nad_plus": "NAD+",
    "chem:metabolite:glutathione": "glutathione",
    "chem:metabolite:ceramide": "ceramide",
    "chem:metabolite:prostaglandin_e2": "prostaglandin E2",
    "chem:metabolite:nitric_oxide": "nitric oxide",
    "chem:metabolite:camp": "cyclic AMP",
    "chem:metabolite:reactive_oxygen_species": "reactive oxygen species",
    "chem:metabolite:beta_hydroxybutyrate": "beta-hydroxybutyrate",
    "chem:metabolite:kynurenine": "kynurenine",
    "chem:metabolite:lactate": "lactate",
}

# ---------------------------------------------------------------------------
# P7 bio→chem edges (biology producing/releasing chemistry metabolites)
# These are the KEY edges that enable multi-crossing paths.
# Pattern: biology_node → produces/releases/depletes → chem_metabolite
# ---------------------------------------------------------------------------

_P7_BIO_TO_CHEM_EDGES: list[dict[str, Any]] = [
    # NAD+ produced/regulated by biology
    {"source_id": "bio:pathway:ampk_pathway",
     "relation": "increases", "target_id": "chem:metabolite:nad_plus", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "depletes", "target_id": "chem:metabolite:nad_plus", "weight": 0.80},
    {"source_id": "bio:protein:sirt1",
     "relation": "consumes", "target_id": "chem:metabolite:nad_plus", "weight": 0.90},
    {"source_id": "bio:process:cell_senescence",
     "relation": "depletes", "target_id": "chem:metabolite:nad_plus", "weight": 0.75},

    # Glutathione produced/depleted by biology
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "depletes", "target_id": "chem:metabolite:glutathione", "weight": 0.85},
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "depletes", "target_id": "chem:metabolite:glutathione", "weight": 0.80},
    {"source_id": "bio:process:neurodegeneration",
     "relation": "depletes", "target_id": "chem:metabolite:glutathione", "weight": 0.75},

    # Ceramide produced by apoptosis/inflammation
    {"source_id": "bio:pathway:apoptosis",
     "relation": "produces", "target_id": "chem:metabolite:ceramide", "weight": 0.80},
    {"source_id": "bio:process:inflammatory_cytokine_release",
     "relation": "produces", "target_id": "chem:metabolite:ceramide", "weight": 0.70},

    # PGE2 produced by NF-kB / inflammation
    {"source_id": "bio:pathway:nfkb_pathway",
     "relation": "produces", "target_id": "chem:metabolite:prostaglandin_e2", "weight": 0.85},
    {"source_id": "bio:process:inflammatory_cytokine_release",
     "relation": "releases", "target_id": "chem:metabolite:prostaglandin_e2", "weight": 0.80},

    # Nitric oxide produced by neuroinflammation
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "produces", "target_id": "chem:metabolite:nitric_oxide", "weight": 0.85},
    {"source_id": "bio:protein:vegf",
     "relation": "induces", "target_id": "chem:metabolite:nitric_oxide", "weight": 0.75},

    # cAMP produced/regulated by receptors
    {"source_id": "bio:receptor:adenosine_a2a",
     "relation": "produces", "target_id": "chem:metabolite:camp", "weight": 0.90},
    {"source_id": "bio:receptor:glucocorticoid_receptor",
     "relation": "elevates", "target_id": "chem:metabolite:camp", "weight": 0.70},
    {"source_id": "bio:receptor:dopamine_d2",
     "relation": "reduces", "target_id": "chem:metabolite:camp", "weight": 0.80},

    # ROS produced by mitochondrial dysfunction / oxidative stress
    {"source_id": "bio:process:mitochondrial_dysfunction",
     "relation": "produces", "target_id": "chem:metabolite:reactive_oxygen_species", "weight": 0.90},
    {"source_id": "bio:pathway:oxidative_stress",
     "relation": "produces", "target_id": "chem:metabolite:reactive_oxygen_species", "weight": 0.90},
    {"source_id": "bio:process:ros_production",
     "relation": "generates", "target_id": "chem:metabolite:reactive_oxygen_species", "weight": 0.95},
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "produces", "target_id": "chem:metabolite:reactive_oxygen_species", "weight": 0.80},

    # Beta-hydroxybutyrate produced by metabolism
    {"source_id": "bio:process:glucose_metabolism",
     "relation": "produces", "target_id": "chem:metabolite:beta_hydroxybutyrate", "weight": 0.75},
    {"source_id": "bio:pathway:ampk_pathway",
     "relation": "promotes", "target_id": "chem:metabolite:beta_hydroxybutyrate", "weight": 0.70},

    # Kynurenine produced by neuroinflammation / immune activation
    {"source_id": "bio:pathway:neuroinflammation",
     "relation": "produces", "target_id": "chem:metabolite:kynurenine", "weight": 0.80},
    {"source_id": "bio:process:immune_activation",
     "relation": "produces", "target_id": "chem:metabolite:kynurenine", "weight": 0.75},

    # Lactate produced by glucose metabolism / tumor hypoxia
    {"source_id": "bio:process:glucose_metabolism",
     "relation": "generates", "target_id": "chem:metabolite:lactate", "weight": 0.80},
    {"source_id": "bio:process:tumor_angiogenesis",
     "relation": "produces", "target_id": "chem:metabolite:lactate", "weight": 0.75},
]


# ---------------------------------------------------------------------------
# P7 chem→bio edges (metabolites affecting biology)
# These complete the multi-crossing path back into biology domain.
# Pattern: chem_metabolite → activates/inhibits/promotes → biology_node
# ---------------------------------------------------------------------------

_P7_CHEM_TO_BIO_EDGES: list[dict[str, Any]] = [
    # NAD+ → biology
    {"source_id": "chem:metabolite:nad_plus",
     "relation": "activates", "target_id": "bio:protein:sirt1", "weight": 0.90},
    {"source_id": "chem:metabolite:nad_plus",
     "relation": "activates", "target_id": "bio:pathway:ampk_pathway", "weight": 0.80},
    {"source_id": "chem:metabolite:nad_plus",
     "relation": "reduces", "target_id": "bio:process:cell_senescence", "weight": 0.75},
    {"source_id": "chem:metabolite:nad_plus",
     "relation": "may_reduce_risk_of", "target_id": "bio:disease:alzheimers", "weight": 0.55},

    # Glutathione → biology
    {"source_id": "chem:metabolite:glutathione",
     "relation": "reduces", "target_id": "bio:process:ros_production", "weight": 0.85},
    {"source_id": "chem:metabolite:glutathione",
     "relation": "protects", "target_id": "bio:protein:sod1", "weight": 0.75},
    {"source_id": "chem:metabolite:glutathione",
     "relation": "reduces", "target_id": "bio:process:neurodegeneration", "weight": 0.70},
    {"source_id": "chem:metabolite:glutathione",
     "relation": "protects_against", "target_id": "bio:disease:parkinsons", "weight": 0.55},

    # Ceramide → biology
    {"source_id": "chem:metabolite:ceramide",
     "relation": "activates", "target_id": "bio:pathway:apoptosis", "weight": 0.85},
    {"source_id": "chem:metabolite:ceramide",
     "relation": "promotes", "target_id": "bio:process:neurodegeneration", "weight": 0.70},
    {"source_id": "chem:metabolite:ceramide",
     "relation": "promotes", "target_id": "bio:disease:alzheimers", "weight": 0.60},

    # Prostaglandin E2 → biology
    {"source_id": "chem:metabolite:prostaglandin_e2",
     "relation": "activates", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.80},
    {"source_id": "chem:metabolite:prostaglandin_e2",
     "relation": "promotes", "target_id": "bio:disease:rheumatoid_arthritis", "weight": 0.80},
    {"source_id": "chem:metabolite:prostaglandin_e2",
     "relation": "promotes", "target_id": "bio:disease:colon_cancer", "weight": 0.65},
    {"source_id": "chem:metabolite:prostaglandin_e2",
     "relation": "promotes", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.75},

    # Nitric oxide → biology
    {"source_id": "chem:metabolite:nitric_oxide",
     "relation": "modulates", "target_id": "bio:pathway:neuroinflammation", "weight": 0.70},
    {"source_id": "chem:metabolite:nitric_oxide",
     "relation": "promotes", "target_id": "bio:process:tumor_angiogenesis", "weight": 0.75},
    {"source_id": "chem:metabolite:nitric_oxide",
     "relation": "may_treat", "target_id": "bio:disease:heart_failure", "weight": 0.55},

    # cAMP → biology
    {"source_id": "chem:metabolite:camp",
     "relation": "activates", "target_id": "bio:pathway:autophagy", "weight": 0.75},
    {"source_id": "chem:metabolite:camp",
     "relation": "modulates", "target_id": "bio:process:dopamine_synthesis", "weight": 0.70},
    {"source_id": "chem:metabolite:camp",
     "relation": "reduces", "target_id": "bio:process:inflammatory_cytokine_release", "weight": 0.65},

    # ROS → biology
    {"source_id": "chem:metabolite:reactive_oxygen_species",
     "relation": "damages", "target_id": "bio:protein:sod1", "weight": 0.85},
    {"source_id": "chem:metabolite:reactive_oxygen_species",
     "relation": "activates", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.80},
    {"source_id": "chem:metabolite:reactive_oxygen_species",
     "relation": "promotes", "target_id": "bio:process:neurodegeneration", "weight": 0.80},
    {"source_id": "chem:metabolite:reactive_oxygen_species",
     "relation": "drives", "target_id": "bio:disease:parkinsons", "weight": 0.70},
    {"source_id": "chem:metabolite:reactive_oxygen_species",
     "relation": "promotes", "target_id": "bio:process:cell_senescence", "weight": 0.75},

    # Beta-hydroxybutyrate → biology
    {"source_id": "chem:metabolite:beta_hydroxybutyrate",
     "relation": "suppresses", "target_id": "bio:process:neurodegeneration", "weight": 0.75},
    {"source_id": "chem:metabolite:beta_hydroxybutyrate",
     "relation": "inhibits", "target_id": "bio:pathway:nfkb_pathway", "weight": 0.70},
    {"source_id": "chem:metabolite:beta_hydroxybutyrate",
     "relation": "may_treat", "target_id": "bio:disease:alzheimers", "weight": 0.50},
    {"source_id": "chem:metabolite:beta_hydroxybutyrate",
     "relation": "may_reduce_risk_of", "target_id": "bio:disease:parkinsons", "weight": 0.50},

    # Kynurenine → biology
    {"source_id": "chem:metabolite:kynurenine",
     "relation": "suppresses", "target_id": "bio:process:immune_activation", "weight": 0.75},
    {"source_id": "chem:metabolite:kynurenine",
     "relation": "promotes", "target_id": "bio:process:neurodegeneration", "weight": 0.65},
    {"source_id": "chem:metabolite:kynurenine",
     "relation": "promotes", "target_id": "bio:disease:huntingtons", "weight": 0.60},

    # Lactate → biology
    {"source_id": "chem:metabolite:lactate",
     "relation": "modulates", "target_id": "bio:receptor:glucocorticoid_receptor", "weight": 0.65},
    {"source_id": "chem:metabolite:lactate",
     "relation": "promotes", "target_id": "bio:disease:glioblastoma", "weight": 0.65},
    {"source_id": "chem:metabolite:lactate",
     "relation": "modulates", "target_id": "bio:process:immune_activation", "weight": 0.60},
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _node_domain_from_id(node_id: str) -> str:
    """Infer domain from node ID prefix."""
    if node_id.startswith("bio:"):
        return "biology"
    if node_id.startswith("chem:"):
        return "chemistry"
    return "unknown"


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def load_base_kg(path: str = BASE_KG_PATH) -> dict[str, Any]:
    """Load the base (200-node) KG JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _merge_nodes(base_nodes: list[dict], new_nodes: list[dict]) -> list[dict]:
    """Merge new nodes into base, skipping duplicates."""
    existing = {n["id"] for n in base_nodes}
    merged = list(base_nodes)
    for node in new_nodes:
        if node["id"] not in existing:
            merged.append(node)
            existing.add(node["id"])
    return merged


def _merge_edges(
    base_edges: list[dict],
    new_edges: list[dict],
    valid_ids: set[str],
) -> list[dict]:
    """Merge new edges, skipping duplicates and invalid node refs."""
    existing = {(e["source_id"], e["relation"], e["target_id"]) for e in base_edges}
    merged = list(base_edges)
    skipped = 0
    for edge in new_edges:
        key = (edge["source_id"], edge["relation"], edge["target_id"])
        if key in existing:
            continue
        if edge["source_id"] not in valid_ids:
            print(f"  [SKIP] Unknown src: {edge['source_id']}")
            skipped += 1
            continue
        if edge["target_id"] not in valid_ids:
            print(f"  [SKIP] Unknown tgt: {edge['target_id']}")
            skipped += 1
            continue
        merged.append(edge)
        existing.add(key)
    if skipped:
        print(f"  [{skipped} edges skipped due to missing nodes]")
    return merged


def build_p7_kg_data(base_kg: dict[str, Any]) -> dict[str, Any]:
    """Merge P7 metabolite bridge nodes/edges into base KG.

    Returns the P7 KG dict with updated metadata.
    """
    nodes = _merge_nodes(base_kg["nodes"], _P7_METABOLITE_NODES)
    valid_ids = {n["id"] for n in nodes}

    all_new_edges = _P7_BIO_TO_CHEM_EDGES + _P7_CHEM_TO_BIO_EDGES
    edges = _merge_edges(base_kg["edges"], all_new_edges, valid_ids)

    bio_n = sum(1 for n in nodes if n["domain"] == "biology")
    chem_n = sum(1 for n in nodes if n["domain"] == "chemistry")
    cross_e = [
        e for e in edges
        if _node_domain_from_id(e["source_id"]) != _node_domain_from_id(e["target_id"])
    ]
    cd_density = round(len(cross_e) / len(edges), 4) if edges else 0.0

    metadata = {
        "description": "P7 KG: cross-domain metabolite bridge expansion",
        "version": "3.0-p7",
        "base_version": base_kg["metadata"].get("version", "2.0"),
        "node_count": len(nodes),
        "biology_nodes": bio_n,
        "chemistry_nodes": chem_n,
        "edge_count": len(edges),
        "cross_domain_edge_count": len(cross_e),
        "cross_domain_edge_ratio": cd_density,
        "p7_metabolite_nodes": len(_P7_METABOLITE_NODES),
        "p7_bio_to_chem_edges": len(_P7_BIO_TO_CHEM_EDGES),
        "p7_chem_to_bio_edges": len(_P7_CHEM_TO_BIO_EDGES),
        "domains": ["biology", "chemistry"],
    }
    return {"metadata": metadata, "nodes": nodes, "edges": edges}


def validate_p7_kg(p7_data: dict[str, Any]) -> dict[str, Any]:
    """Validate P7 KG and return stats including geometry indicators."""
    nodes = {n["id"] for n in p7_data["nodes"]}
    edges = p7_data["edges"]
    connected = set()
    for e in edges:
        connected.add(e["source_id"])
        connected.add(e["target_id"])
    isolated = nodes - connected
    cross = [
        e for e in edges
        if _node_domain_from_id(e["source_id"]) != _node_domain_from_id(e["target_id"])
    ]
    # Count edges in each direction
    bio_to_chem = [
        e for e in cross
        if e["source_id"].startswith("bio:") and e["target_id"].startswith("chem:")
    ]
    chem_to_bio = [
        e for e in cross
        if e["source_id"].startswith("chem:") and e["target_id"].startswith("bio:")
    ]
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "isolated_count": len(isolated),
        "cross_domain_edges": len(cross),
        "bio_to_chem_edges": len(bio_to_chem),
        "chem_to_bio_edges": len(chem_to_bio),
        "cd_density": round(len(cross) / len(edges), 4) if edges else 0.0,
        "checks": {
            "node_count_ge_200": len(nodes) >= 200,
            "no_isolated_nodes": len(isolated) == 0,
            "bio_to_chem_edges_exist": len(bio_to_chem) > 0,
        },
    }


def main() -> None:
    """Build P7 KG and save to JSON."""
    print("=== Building P7 KG (metabolite bridge expansion) ===")
    base_kg = load_base_kg()
    print(f"  Base KG: {base_kg['metadata']['node_count']} nodes, "
          f"{base_kg['metadata']['edge_count']} edges")
    print(f"  Adding {len(_P7_METABOLITE_NODES)} metabolite nodes...")
    print(f"  Adding {len(_P7_BIO_TO_CHEM_EDGES)} bio→chem edges...")
    print(f"  Adding {len(_P7_CHEM_TO_BIO_EDGES)} chem→bio edges...")

    p7_data = build_p7_kg_data(base_kg)
    stats = validate_p7_kg(p7_data)

    print(f"\nP7 KG stats:")
    print(f"  Nodes: {stats['node_count']} (base: {base_kg['metadata']['node_count']})")
    print(f"  Edges: {stats['edge_count']} (base: {base_kg['metadata']['edge_count']})")
    print(f"  Cross-domain edges: {stats['cross_domain_edges']}")
    print(f"    bio→chem: {stats['bio_to_chem_edges']} [NEW]")
    print(f"    chem→bio: {stats['chem_to_bio_edges']}")
    print(f"  cd_density: {stats['cd_density']}")
    print(f"  Isolated nodes: {stats['isolated_count']}")
    if stats["isolated_count"] > 0:
        all_nodes = {n["id"] for n in p7_data["nodes"]}
        connected = set()
        for e in p7_data["edges"]:
            connected.add(e["source_id"])
            connected.add(e["target_id"])
        print(f"  Isolated: {all_nodes - connected}")

    for check, ok in stats["checks"].items():
        status = "✓" if ok else "✗"
        print(f"  {status} {check}: {ok}")

    with open(P7_KG_PATH, "w", encoding="utf-8") as f:
        json.dump(p7_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {P7_KG_PATH}")


if __name__ == "__main__":
    main()
