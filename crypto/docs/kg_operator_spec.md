# KG Operator Specification

## Operator Semantics

Operators transform one or more KG subgraphs into hypothesis-ready structures.
All operators are pure functions: same inputs → same outputs.  Random state must
be seeded before any operator call.

---

### align(G1, G2, key) → G_aligned

**Purpose:** Find nodes in G1 and G2 that share a common attribute `key`, and create
correspondence edges between them.

**Economic meaning:** Identifies pairs of assets (or time windows) that exhibit
co-movement on a specified dimension (e.g., funding rate direction, liquidity bucket).

**Inputs:**
- `G1`, `G2`: KG subgraphs (dict of nodes + edges)
- `key`: node attribute name to align on

**Output:** New graph with cross-graph alignment edges (`_aligned_to` relation).

**Precondition:** Both graphs must contain the `key` attribute on at least one node each.

---

### union(G1, G2) → G_union

**Purpose:** Merge two KG subgraphs, deduplicating nodes by `node_id`.

**Economic meaning:** Expands the evidence base; used when two independently built
KG families have complementary coverage of the same phenomenon.

**Inputs:** `G1`, `G2`

**Output:** Merged graph; edge conflicts resolved by keeping both (union semantics).

---

### compose(G, relation_type) → G_composed

**Purpose:** Follow chains of a specified relation type to surface transitive connections
(path length ≤ `MAX_COMPOSE_DEPTH`, default 3).

**Economic meaning:** Discovers indirect causal chains.  E.g., asset A ↔ B via
liquidity_shift, B ↔ C via funding_pressure → compose reveals A ↔ C indirectly.

**Inputs:**
- `G`: source graph
- `relation_type`: edge attribute to follow

**Output:** New graph augmented with transitive edges labelled `_composed`.

**Limit:** `MAX_COMPOSE_DEPTH = 3` (prevents exponential blow-up).

---

### difference(G1, G2) → G_diff

**Purpose:** Return nodes/edges in G1 that are NOT in G2.

**Economic meaning:** Finds structure present in one market regime but absent in another.
Useful for regime-change hypothesis generation.

**Inputs:** `G1` (candidate), `G2` (baseline)

**Output:** Subgraph of G1 minus any node/edge present in G2.

---

### rank(candidates, scorer, top_k) → ranked_list

**Purpose:** Score a list of hypothesis candidates and return the top-k.

**Economic meaning:** Prioritises discovery bandwidth on the most promising claims.

**Inputs:**
- `candidates`: list of RawHypothesis objects
- `scorer`: callable(RawHypothesis) → float
- `top_k`: int

**Output:** List of at most `top_k` candidates sorted descending by score.

**Selection artifact note:** When `top_k` << len(candidates), naive ranking creates
selection artifacts (low-variance hypotheses dominate).  The scorer MUST include a
novelty penalty to maintain reachability.
