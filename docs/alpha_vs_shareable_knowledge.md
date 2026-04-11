# Alpha vs. Shareable Knowledge — Secrecy Classification Framework

## Why Secrecy Matters

Trading alpha is a resource that degrades when exposed. A hypothesis about a specific market microstructure inefficiency loses value as more capital deploys against it. This is not a theoretical concern: well-documented examples in equities (low-volatility anomaly, momentum after academic publication) show that systematic exposure of specific signals accelerates their decay.

The Hyperliquid KG Discovery Engine is designed to produce durable, interpretable hypotheses. Some of those hypotheses will encode genuine edges — specific, actionable relationships between market states that could inform a profitable trading strategy. These must be protected. Others will encode structural knowledge — true and interesting observations about how markets work, but not specific enough to trade directly. These can be shared, and sharing them is valuable for research credibility and hypothesis cross-validation.

The secrecy classification framework distinguishes these two categories and provides a systematic way to assign every hypothesis card to the correct level.

---

## The Four Levels

### Level 1: private_alpha

**Definition:** A hypothesis that encodes a specific, actionable, novel edge. If acted upon, this hypothesis could generate positive risk-adjusted returns. Sharing it externally would expose the edge to crowding and decay.

**Characteristics:**
- High actionability score (>= 0.7)
- High novelty score (>= 0.7)
- Contains sufficient specificity to define an entry condition and expected outcome
- The `hypothesis_text` alone, read by a sophisticated counterparty, would reveal the trade setup

**Storage and logging:**
- Stored only in local `runs/` directory with restricted filesystem permissions
- Never included in shared reports, papers, or external communications
- Never logged to shared databases, cloud storage, or version-controlled files
- Referenced in internal tracking by `hypothesis_id` only, not by content

**Examples of private_alpha conditions:**
- A specific funding + volatility state co-occurrence that predicts mean-reversion in HYPE within a defined bar window
- A cross-asset lead-lag relationship between BTC funding and HYPE price that has a consistent timing structure
- A regime-specific execution pattern where entry timing relative to a vol state produces favorable fill quality

### Level 2: internal_watchlist

**Definition:** A hypothesis that is promising but has not yet been validated, or that is actionable but depends on data or conditions not yet fully characterized.

**Characteristics:**
- Moderate to high actionability (>= 0.5) or high novelty with low actionability
- Untested or weakly supported validation status
- The specificity of the claim is not yet sufficient to define a complete trade setup
- May become `private_alpha` after further testing, or `discard` after invalidation

**Storage and logging:**
- Stored in `runs/` directory, accessible to research team members
- May be discussed in internal team review sessions
- Not shared externally, even in structural form
- Tracked with `next_recommended_test` field populated

**When to move to private_alpha:** After successful backtesting across at least two non-overlapping time windows with consistent results.

**When to move to discard:** After a properly specified backtest produces no meaningful edge, or when the underlying data limitation (e.g., no order book) makes the hypothesis fundamentally untestable.

### Level 3: shareable_structure

**Definition:** A hypothesis that encodes a genuine structural observation about market dynamics without sufficient specificity to constitute a tradeable edge. Shareable in research papers, blog posts, or discussions without materially revealing alpha.

**Characteristics:**
- Describes a regime dependency, cross-asset structural relationship, or market microstructure pattern at a level of abstraction that is interesting but not directly actionable
- Does not contain specific numeric thresholds, timing windows, or entry conditions
- Could be independently verified by anyone with access to the same data types
- Novelty is at the structural level ("cross-asset funding synchronization precedes large moves") rather than the specific level ("HYPE funding crossing +0.07% while BTC funding is falling triggers a specific outcome")

**Storage and logging:**
- Stored in the standard inventory; no access restrictions
- May appear in research papers, discussions, or public-facing documents in anonymized or abstracted form
- The `hypothesis_text` at this level should pass the test: "Would sharing this exact text harm our trading edge?" — if the answer is no, it belongs here

**Appropriate content for shareable_structure:**
- Structural regime dependencies (e.g., "high-funding regimes on Hyperliquid exhibits synchronized vol compression across assets before reversals")
- Cross-asset flow patterns at a conceptual level ("BTC microstructure state transitions appear to lead HYPE regime changes with a consistent lag structure")
- General market microstructure observations that are documented in academic literature but newly confirmed for Hyperliquid specifically
- Negative results ("we found no meaningful relationship between SOL funding extremes and HYPE price states")

### Level 4: discard

**Definition:** A hypothesis that fails to provide economic insight. This includes tautologies, definitional relationships, hypotheses that were tested and invalidated, and hypotheses so vague or structurally degenerate that they carry no information.

**Characteristics:**
- Low actionability score (< 0.4) AND low novelty score (< 0.4)
- Provenance path is a tautological loop or self-referential chain
- `validation_status` is `invalidated` or the claim is definitionally true by construction
- Economically empty chains (e.g., `vol_burst → co_occurs_with → high_volatility_state`)

**Storage:** Archived in the run output for audit purposes. Not actively reviewed or acted upon.

---

## Decision Criteria

The following table summarizes the decision criteria for each level:

| Criterion | private_alpha | internal_watchlist | shareable_structure | discard |
|-----------|--------------|-------------------|--------------------|----|
| actionability_score | >= 0.7 | >= 0.5 | < 0.5 | < 0.4 |
| novelty_score | >= 0.7 | any | any | < 0.4 |
| reproducibility_score | any | any | any | < 0.3 forces discard |
| validation_status | any | untested / weakly_supported | any | invalidated |
| hypothesis specificity | high | medium | low | none |
| can be tested without missing data | yes | yes or no | irrelevant | irrelevant |

Additional hard rules:
- A hypothesis with `provenance_path` length > 8 cannot be `private_alpha` without explicit researcher override
- A hypothesis where every edge in the provenance is `co_occurs_with` cannot be `private_alpha`
- A hypothesis that describes a relationship already documented in academic literature scores 0.0 on novelty and cannot be `private_alpha`

---

## How Hypotheses Flow Between Levels

Secrecy classification is not static. As validation evidence accumulates, hypotheses may move between levels. Movements are recorded in the card audit trail with a timestamp and reason.

### Common transitions

**internal_watchlist → private_alpha**
Trigger: Successful backtest across two non-overlapping windows. The hypothesis becomes specific enough to define an entry condition.

**internal_watchlist → discard**
Trigger: Backtest fails. The hypothesis was not reproducible in historical data.

**internal_watchlist → shareable_structure**
Trigger: Backtest reveals a structural pattern but not a tradeable edge. The claim remains interesting at the macro level.

**private_alpha → internal_watchlist**
Trigger: `decay_risk` assessment rises (e.g., known players appear to be trading the same setup). The edge may still exist but is no longer securely held.

**private_alpha → shareable_structure**
Trigger: The hypothesis has decayed (validation_status = `decayed`). The structural insight remains valid but the specific edge is gone. At this point, sharing the structural observation does not expose alpha.

**shareable_structure → discard**
Trigger: The structural observation is found to be definitionally true, or subsequent analysis shows it was an artifact of the data construction.

### Downward classification is final for alpha

A hypothesis that was `private_alpha` and has decayed should move to `shareable_structure` or `discard`, never back to `private_alpha`. If a similar pattern re-emerges in a future market regime, it should generate a new hypothesis card with a new `hypothesis_id`.

---

## Architecture-Level Enforcement

Secrecy is maintained through the following system-level mechanisms:

**File system separation**
`private_alpha` cards are stored in a restricted-access subdirectory. When the inventory is exported or logged, cards with `secrecy_level = "private_alpha"` are excluded from the export payload.

**Log filtering**
The pipeline logger is configured to redact the `hypothesis_text` and `provenance_path` fields for `private_alpha` cards in any log output that goes to shared storage or external systems.

**Run report generation**
The `review_memo.md` file created after each experiment includes summary statistics (number of cards per secrecy level, score distributions) but never reproduces the full content of `private_alpha` cards. It may reference them by `hypothesis_id` only.

**Version control exclusion**
Files containing `private_alpha` card content are listed in `.gitignore`. The run output directory structure is committed, but full `output_candidates.json` files containing `private_alpha` cards are excluded. An anonymized version with those cards redacted is committed instead.

---

## What Should Never Appear in shareable_structure

The following categories of information must not appear in `shareable_structure` cards, even if the hypothesis appears structural:

- Specific numeric thresholds (e.g., "funding rate above X%")
- Specific bar windows (e.g., "within N bars")
- Exact entry conditions derived from the provenance path
- Information about position sizing relative to the signal
- Information about which specific operator chain produced the result (if revealing the chain reveals the edge)
- Historical hit rates or Sharpe estimates for the specific hypothesis

If the `hypothesis_text` would allow a reader to construct a backtest that recovers the same edge, it belongs in `internal_watchlist` or `private_alpha`, not `shareable_structure`.

---

## What IS Appropriate for shareable_structure

- Regime taxonomies derived from the Regime KG (e.g., identifying that Hyperliquid funding exhibits distinct clustering behavior)
- Cross-asset correlation structure at a qualitative level
- Observations about KG operator behavior (e.g., "the compose operator discovers significantly more novel candidates when applied to cross-asset merged KGs than to single-asset KGs")
- Negative results from systematic hypothesis testing
- The existence and general structure of specific hypothesis categories without revealing actionable specifics
- Methodological contributions (the KG operator pipeline approach itself, the hypothesis card schema, the secrecy classification framework)

The shareable_structure level is the primary vehicle for academic and public-facing research output. The system is designed so that the methodology and structural findings can be shared openly while the specific alpha is protected.
