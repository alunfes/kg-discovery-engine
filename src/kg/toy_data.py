"""Toy Knowledge Graph datasets for experiments.

Two domains:
- biology (proteins, enzymes, reactions)
- chemistry (compounds, reactions, properties)
- software (modules, dependencies, patterns)
- networking (protocols, layers, services)
"""

from .models import KGEdge, KGNode, KnowledgeGraph


def build_biology_kg() -> KnowledgeGraph:
    """Small biology KG: proteins, enzymes, reactions."""
    kg = KnowledgeGraph(name="biology")

    nodes = [
        KGNode("bio:protein_A", "ProteinA", "biology"),
        KGNode("bio:protein_B", "ProteinB", "biology"),
        KGNode("bio:enzyme_X", "EnzymeX", "biology"),
        KGNode("bio:enzyme_Y", "EnzymeY", "biology"),
        KGNode("bio:reaction_1", "Reaction1", "biology"),
        KGNode("bio:reaction_2", "Reaction2", "biology"),
        KGNode("bio:cell_membrane", "CellMembrane", "biology"),
        KGNode("bio:nucleus", "Nucleus", "biology"),
    ]
    for n in nodes:
        kg.add_node(n)

    edges = [
        KGEdge("bio:protein_A", "inhibits", "bio:enzyme_X"),
        KGEdge("bio:protein_B", "activates", "bio:enzyme_X"),
        KGEdge("bio:enzyme_X", "catalyzes", "bio:reaction_1"),
        KGEdge("bio:enzyme_Y", "catalyzes", "bio:reaction_2"),
        KGEdge("bio:reaction_1", "produces", "bio:protein_B"),
        KGEdge("bio:protein_A", "binds_to", "bio:cell_membrane"),
        KGEdge("bio:cell_membrane", "contains", "bio:enzyme_Y"),
        KGEdge("bio:nucleus", "encodes", "bio:protein_A"),
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
        KGNode("chem:catalyst_M", "CatalystM", "chemistry"),
        KGNode("chem:catalyst_N", "CatalystN", "chemistry"),
        KGNode("chem:reaction_alpha", "ReactionAlpha", "chemistry"),
        KGNode("chem:reaction_beta", "ReactionBeta", "chemistry"),
        KGNode("chem:polymer_Z", "PolymerZ", "chemistry"),
        KGNode("chem:solvent_S", "SolventS", "chemistry"),
    ]
    for n in nodes:
        kg.add_node(n)

    edges = [
        KGEdge("chem:compound_P", "inhibits", "chem:catalyst_M"),
        KGEdge("chem:compound_Q", "activates", "chem:catalyst_M"),
        KGEdge("chem:catalyst_M", "accelerates", "chem:reaction_alpha"),
        KGEdge("chem:catalyst_N", "accelerates", "chem:reaction_beta"),
        KGEdge("chem:reaction_alpha", "yields", "chem:compound_Q"),
        KGEdge("chem:compound_P", "dissolves_in", "chem:solvent_S"),
        KGEdge("chem:solvent_S", "facilitates", "chem:catalyst_N"),
        KGEdge("chem:reaction_beta", "produces", "chem:polymer_Z"),
    ]
    for e in edges:
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
