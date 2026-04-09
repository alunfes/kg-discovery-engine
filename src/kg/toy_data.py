"""Toy Knowledge Graph datasets for experiments.

Four domains:
- biology  (proteins, enzymes, reactions)
- chemistry (compounds, reactions, properties)
- software  (modules, dependencies, patterns)
- networking (protocols, layers, services)

Cross-domain bridge functions are also provided for Run 003+:
- build_bio_chem_bridge_kg(): bio↔chem cross-domain KG with explicit bridging nodes
- build_sw_net_bridge_kg():   software↔networking cross-domain KG
- build_noisy_kg():           biology KG with intentional noise (typos, ambiguous labels)
"""

from __future__ import annotations

import random

from .models import KGEdge, KGNode, KnowledgeGraph


def build_biology_kg() -> KnowledgeGraph:
    """Small biology KG: proteins, enzymes, reactions."""
    kg = KnowledgeGraph(name="biology")

    nodes = [
        KGNode("bio:protein_A", "ProteinA", "biology"),
        KGNode("bio:protein_B", "ProteinB", "biology"),
        KGNode("bio:protein_C", "ProteinC", "biology"),
        KGNode("bio:enzyme_X", "EnzymeX", "biology"),
        KGNode("bio:enzyme_Y", "EnzymeY", "biology"),
        KGNode("bio:enzyme_Z", "EnzymeZ", "biology"),
        KGNode("bio:reaction_1", "Reaction1", "biology"),
        KGNode("bio:reaction_2", "Reaction2", "biology"),
        KGNode("bio:reaction_3", "Reaction3", "biology"),
        KGNode("bio:cell_membrane", "CellMembrane", "biology"),
        KGNode("bio:nucleus", "Nucleus", "biology"),
        KGNode("bio:metabolite_M", "MetaboliteM", "biology"),
    ]
    for n in nodes:
        kg.add_node(n)

    edges = [
        KGEdge("bio:protein_A", "inhibits", "bio:enzyme_X"),
        KGEdge("bio:protein_B", "activates", "bio:enzyme_X"),
        KGEdge("bio:enzyme_X", "catalyzes", "bio:reaction_1"),
        KGEdge("bio:enzyme_Y", "catalyzes", "bio:reaction_2"),
        KGEdge("bio:enzyme_Z", "catalyzes", "bio:reaction_3"),
        KGEdge("bio:reaction_1", "produces", "bio:protein_B"),
        KGEdge("bio:reaction_2", "produces", "bio:metabolite_M"),
        KGEdge("bio:reaction_3", "produces", "bio:protein_C"),
        KGEdge("bio:protein_A", "binds_to", "bio:cell_membrane"),
        KGEdge("bio:cell_membrane", "contains", "bio:enzyme_Y"),
        KGEdge("bio:nucleus", "encodes", "bio:protein_A"),
        KGEdge("bio:nucleus", "encodes", "bio:protein_C"),
        KGEdge("bio:metabolite_M", "activates", "bio:enzyme_Z"),
        KGEdge("bio:protein_C", "inhibits", "bio:enzyme_Y"),
    ]
    for e in edges:
        kg.add_edge(e)

    return kg


def build_chemistry_kg() -> KnowledgeGraph:
    """Small chemistry KG: compounds, catalysts, reactions."""
    kg = KnowledgeGraph(name="chemistry")

    nodes = [
        KGNode("chem:compound_P", "CompoundP", "chemistry"),
        KGNode("chem:compound_Q", "CompoundQ", "chemistry"),
        KGNode("chem:compound_R", "CompoundR", "chemistry"),
        KGNode("chem:catalyst_M", "CatalystM", "chemistry"),
        KGNode("chem:catalyst_N", "CatalystN", "chemistry"),
        KGNode("chem:catalyst_L", "CatalystL", "chemistry"),
        KGNode("chem:reaction_alpha", "ReactionAlpha", "chemistry"),
        KGNode("chem:reaction_beta", "ReactionBeta", "chemistry"),
        KGNode("chem:reaction_gamma", "ReactionGamma", "chemistry"),
        KGNode("chem:polymer_Z", "PolymerZ", "chemistry"),
        KGNode("chem:solvent_S", "SolventS", "chemistry"),
        KGNode("chem:intermediate_I", "IntermediateI", "chemistry"),
    ]
    for n in nodes:
        kg.add_node(n)

    edges = [
        KGEdge("chem:compound_P", "inhibits", "chem:catalyst_M"),
        KGEdge("chem:compound_Q", "activates", "chem:catalyst_M"),
        KGEdge("chem:catalyst_M", "accelerates", "chem:reaction_alpha"),
        KGEdge("chem:catalyst_N", "accelerates", "chem:reaction_beta"),
        KGEdge("chem:catalyst_L", "accelerates", "chem:reaction_gamma"),
        KGEdge("chem:reaction_alpha", "yields", "chem:compound_Q"),
        KGEdge("chem:reaction_alpha", "yields", "chem:intermediate_I"),
        KGEdge("chem:reaction_beta", "produces", "chem:polymer_Z"),
        KGEdge("chem:reaction_gamma", "yields", "chem:compound_R"),
        KGEdge("chem:compound_P", "dissolves_in", "chem:solvent_S"),
        KGEdge("chem:solvent_S", "facilitates", "chem:catalyst_N"),
        KGEdge("chem:solvent_S", "facilitates", "chem:catalyst_L"),
        KGEdge("chem:intermediate_I", "activates", "chem:catalyst_L"),
        KGEdge("chem:compound_R", "inhibits", "chem:catalyst_N"),
    ]
    for e in edges:
        kg.add_edge(e)

    return kg


def build_bio_chem_bridge_kg() -> KnowledgeGraph:
    """Biology + chemistry KG with explicit cross-domain bridging nodes/edges.

    Adds bio↔chem hybrid concepts that create direct cross-domain paths,
    increasing the proportion of cross-domain hypotheses from compose().
    """
    kg = KnowledgeGraph(name="bio_chem_bridge")

    # Bridging nodes (explicitly tagged with both-domain context)
    bridge_nodes = [
        # Bio-side anchors
        KGNode("bio:protein_A", "ProteinA", "biology"),
        KGNode("bio:protein_B", "ProteinB", "biology"),
        KGNode("bio:enzyme_X", "EnzymeX", "biology"),
        KGNode("bio:enzyme_Y", "EnzymeY", "biology"),
        KGNode("bio:reaction_1", "Reaction1", "biology"),
        KGNode("bio:metabolite_M", "MetaboliteM", "biology"),
        # Chem-side anchors
        KGNode("chem:compound_P", "CompoundP", "chemistry"),
        KGNode("chem:compound_Q", "CompoundQ", "chemistry"),
        KGNode("chem:catalyst_M", "CatalystM", "chemistry"),
        KGNode("chem:catalyst_N", "CatalystN", "chemistry"),
        KGNode("chem:reaction_alpha", "ReactionAlpha", "chemistry"),
        KGNode("chem:polymer_Z", "PolymerZ", "chemistry"),
        # Bridge nodes
        KGNode("bridge:enzyme_catalyst_E1", "EnzymeCatalyst", "biology"),
        KGNode("bridge:protein_compound_PC1", "ProteinCompound", "chemistry"),
        KGNode("bridge:metabolite_intermediate_MI1", "MetaboliteIntermediate", "chemistry"),
    ]
    for n in bridge_nodes:
        kg.add_node(n)

    # Bio-internal edges
    bio_edges = [
        KGEdge("bio:protein_A", "inhibits", "bio:enzyme_X"),
        KGEdge("bio:protein_B", "activates", "bio:enzyme_X"),
        KGEdge("bio:enzyme_X", "catalyzes", "bio:reaction_1"),
        KGEdge("bio:reaction_1", "produces", "bio:protein_B"),
        KGEdge("bio:enzyme_Y", "catalyzes", "bio:reaction_1"),
        KGEdge("bio:metabolite_M", "activates", "bio:enzyme_Y"),
    ]
    # Chem-internal edges
    chem_edges = [
        KGEdge("chem:compound_P", "inhibits", "chem:catalyst_M"),
        KGEdge("chem:compound_Q", "activates", "chem:catalyst_M"),
        KGEdge("chem:catalyst_M", "accelerates", "chem:reaction_alpha"),
        KGEdge("chem:reaction_alpha", "yields", "chem:compound_Q"),
        KGEdge("chem:catalyst_N", "accelerates", "chem:reaction_alpha"),
        KGEdge("chem:reaction_alpha", "produces", "chem:polymer_Z"),
    ]
    # Cross-domain bridge edges (bio ↔ chem)
    cross_edges = [
        # Protein binds compound (bio→chem)
        KGEdge("bio:protein_A", "binds", "chem:compound_P"),
        KGEdge("bio:protein_B", "binds", "chem:compound_Q"),
        # Enzyme catalyzes chemical reaction
        KGEdge("bio:enzyme_X", "catalyzes", "chem:reaction_alpha"),
        KGEdge("bio:enzyme_Y", "activates", "chem:catalyst_M"),
        # Metabolite is precursor to chemical compound
        KGEdge("bio:metabolite_M", "precursor_to", "chem:compound_Q"),
        KGEdge("bio:metabolite_M", "precursor_to", "chem:compound_P"),
        # Chemical compound modulates biological enzyme
        KGEdge("chem:compound_P", "inhibits", "bio:enzyme_X"),
        KGEdge("chem:compound_Q", "activates", "bio:enzyme_Y"),
        # Polymer affects biology
        KGEdge("chem:polymer_Z", "modulates", "bio:protein_B"),
        # Bridge node connections
        KGEdge("bio:enzyme_X", "analogous_to", "bridge:enzyme_catalyst_E1"),
        KGEdge("chem:catalyst_M", "analogous_to", "bridge:enzyme_catalyst_E1"),
        KGEdge("bio:protein_A", "related_to", "bridge:protein_compound_PC1"),
        KGEdge("chem:compound_P", "related_to", "bridge:protein_compound_PC1"),
        KGEdge("bio:metabolite_M", "related_to", "bridge:metabolite_intermediate_MI1"),
        KGEdge("chem:reaction_alpha", "involves", "bridge:metabolite_intermediate_MI1"),
    ]
    for e in bio_edges + chem_edges + cross_edges:
        kg.add_edge(e)

    return kg


def build_software_kg() -> KnowledgeGraph:
    """Small software KG: modules, dependencies, design patterns."""
    kg = KnowledgeGraph(name="software")

    nodes = [
        KGNode("sw:module_auth", "AuthModule", "software"),
        KGNode("sw:module_db", "DBModule", "software"),
        KGNode("sw:module_api", "APIModule", "software"),
        KGNode("sw:module_cache", "CacheModule", "software"),
        KGNode("sw:pattern_singleton", "SingletonPattern", "software"),
        KGNode("sw:pattern_observer", "ObserverPattern", "software"),
        KGNode("sw:service_user", "UserService", "software"),
        KGNode("sw:service_session", "SessionService", "software"),
        KGNode("sw:module_tls", "TLSModule", "software"),
    ]
    for n in nodes:
        kg.add_node(n)

    edges = [
        KGEdge("sw:module_auth", "depends_on", "sw:module_db"),
        KGEdge("sw:module_api", "depends_on", "sw:module_auth"),
        KGEdge("sw:module_cache", "accelerates", "sw:module_db"),
        KGEdge("sw:module_db", "implements", "sw:pattern_singleton"),
        KGEdge("sw:module_auth", "implements", "sw:pattern_observer"),
        KGEdge("sw:service_user", "uses", "sw:module_auth"),
        KGEdge("sw:service_user", "uses", "sw:module_api"),
        KGEdge("sw:service_session", "depends_on", "sw:module_auth"),
        KGEdge("sw:module_auth", "uses", "sw:module_tls"),
        KGEdge("sw:module_api", "uses", "sw:module_tls"),
    ]
    for e in edges:
        kg.add_edge(e)

    return kg


def build_networking_kg() -> KnowledgeGraph:
    """Small networking KG: protocols, layers, services."""
    kg = KnowledgeGraph(name="networking")

    nodes = [
        KGNode("net:tcp", "TCP", "networking"),
        KGNode("net:udp", "UDP", "networking"),
        KGNode("net:http", "HTTP", "networking"),
        KGNode("net:tls", "TLS", "networking"),
        KGNode("net:dns", "DNS", "networking"),
        KGNode("net:layer_transport", "TransportLayer", "networking"),
        KGNode("net:layer_application", "ApplicationLayer", "networking"),
        KGNode("net:firewall", "Firewall", "networking"),
        KGNode("net:load_balancer", "LoadBalancer", "networking"),
    ]
    for n in nodes:
        kg.add_node(n)

    edges = [
        KGEdge("net:tcp", "belongs_to", "net:layer_transport"),
        KGEdge("net:udp", "belongs_to", "net:layer_transport"),
        KGEdge("net:http", "runs_over", "net:tcp"),
        KGEdge("net:tls", "secures", "net:http"),
        KGEdge("net:dns", "runs_over", "net:udp"),
        KGEdge("net:http", "belongs_to", "net:layer_application"),
        KGEdge("net:tls", "belongs_to", "net:layer_application"),
        KGEdge("net:firewall", "filters", "net:tcp"),
        KGEdge("net:firewall", "filters", "net:udp"),
        KGEdge("net:load_balancer", "distributes", "net:http"),
    ]
    for e in edges:
        kg.add_edge(e)

    return kg


def build_noisy_kg(noise_rate: float = 0.30, seed: int = 42) -> KnowledgeGraph:
    """Biology KG with intentional noise for H2 verification.

    Noise includes: edge removal (noise_rate fraction), label typos,
    and ambiguous node labels.

    Args:
        noise_rate: Fraction of edges to remove (0.0–1.0).
        seed: Random seed for deterministic noise injection.
    """
    rng = random.Random(seed)
    clean_kg = build_biology_kg()

    noisy = KnowledgeGraph(name=f"biology_noisy_{int(noise_rate * 100)}pct")

    # Add nodes with occasional label noise
    noisy_labels = {
        "bio:enzyme_X": "EnzymeXX",        # typo
        "bio:protein_B": "Protein-B",      # separator variant
        "bio:cell_membrane": "CelMembrane",  # typo
    }
    for node in clean_kg.nodes():
        label = noisy_labels.get(node.id, node.label)
        noisy.add_node(KGNode(node.id, label, node.domain, node.attributes))

    # Randomly remove edges based on noise_rate
    all_edges = list(clean_kg.edges())
    keep_count = max(1, int(len(all_edges) * (1.0 - noise_rate)))
    kept_edges = rng.sample(all_edges, keep_count)
    for edge in kept_edges:
        noisy.add_edge(edge)

    return noisy


def build_mixed_hop_kg() -> KnowledgeGraph:
    """KG designed to produce both 2-hop and 3-hop hypotheses (Run 004).

    Two-domain chain:
      bio:A --inhibits--> bio:B --activates--> bio:C --catalyzes--> chem:X --accelerates--> chem:Y --yields--> chem:Z

    compose(max_depth=5) generates:
      - bio:A → bio:C  (2-hop same-domain,  all-strong)
      - bio:B → chem:X (2-hop cross-domain, all-strong)
      - bio:X → chem:Z (2-hop same-domain,  all-strong) [within chem]
      - bio:A → chem:X (3-hop cross-domain, all-strong)
      - bio:B → chem:Y (3-hop cross-domain, all-strong)

    This lets naive scoring and provenance-aware scoring diverge:
    - naive: traceability=0.7 for ALL provenance depths
    - aware: traceability=0.7 for 2-hop, 0.5 for 3-hop
    The 3-hop cross-domain hypotheses score HIGHER than some 2-hop in naive
    mode (evidence_support+novelty bonus outweighs plausibility penalty),
    but aware mode correctly demotes them by reducing traceability.
    """
    kg = KnowledgeGraph(name="mixed_hop")

    nodes = [
        KGNode("mhk:A", "NodeA", "bio"),
        KGNode("mhk:B", "NodeB", "bio"),
        KGNode("mhk:C", "NodeC", "bio"),
        KGNode("mhk:X", "NodeX", "chem"),
        KGNode("mhk:Y", "NodeY", "chem"),
        KGNode("mhk:Z", "NodeZ", "chem"),
    ]
    for n in nodes:
        kg.add_node(n)

    # Strong-relation chain — all relations in _STRONG_RELATIONS
    edges = [
        KGEdge("mhk:A", "inhibits", "mhk:B"),
        KGEdge("mhk:B", "activates", "mhk:C"),
        KGEdge("mhk:C", "catalyzes", "mhk:X"),   # cross-domain bridge
        KGEdge("mhk:X", "accelerates", "mhk:Y"),
        KGEdge("mhk:Y", "yields", "mhk:Z"),
    ]
    for e in edges:
        kg.add_edge(e)

    return kg


def get_all_toy_kgs() -> dict[str, KnowledgeGraph]:
    """Return all toy KGs keyed by domain name."""
    return {
        "biology": build_biology_kg(),
        "chemistry": build_chemistry_kg(),
        "software": build_software_kg(),
        "networking": build_networking_kg(),
    }
