# Next Steps: Hyperliquid KG Discovery Engine

*Prioritized action plan as of 2026-04-12. Estimated sessions are rough guides.*

---

## Priority 1: Connect to Real Data (1-2 sessions)

**What to do:** Test `HttpMarketConnector` against `shogun:8081` for HYPE, BTC, ETH, and SOL. Load real 1h OHLCV data and 8h funding rates for the last 30 days. Re-run the full pipeline against this real dataset.

**Why this matters:** Every result produced so far comes from noise-free synthetic data. The mock connector generates clean, regular candles that do not reflect actual Hyperliquid microstructure — there are no vol spikes, no irregular funding prints, no cross-asset correlation breakdowns. Until real data flows through the pipeline, there is no signal to evaluate. The entire state extraction calibration, hypothesis quality assessment, and secrecy classification are built on assumptions that need real-data grounding.

**Concrete steps:**
- Verify `shogun:8081` endpoint availability and response schema against `HttpMarketConnector` expectations
- Run a one-off 30-day OHLCV + funding pull for all four symbols; inspect raw distributions before piping into the pipeline
- Re-calibrate state extraction thresholds against real distributions (see Priority 2 for detail)
- Validate that `vol_burst`, `funding_extreme`, and `spread_proxy` events appear at plausible frequencies (rough targets: funding_extreme 1-5% of bars, vol_burst 2-8%, spread_proxy 5-15%)
- If `shogun` is unavailable, add a fallback: public Hyperliquid REST API for candle data

---

## Priority 2: State Extraction Improvements (1 session)

**What to do:** Fix the `price_momentum` dominance problem and calibrate the missing event types.

**Why this matters:** With 80% of events classified as `price_momentum`, most KG paths route through this node as an intermediate. That produces structurally redundant hypothesis candidates that differ only in their terminal nodes. The result is a bloated candidate set where genuine cross-asset signals are diluted by generic momentum paths. `vol_burst` emitting zero events is a separate problem — it removes an entire event class from discovery.

**Concrete steps:**
- Add intra-symbol deduplication: do not emit consecutive `price_momentum` events for the same symbol within a rolling window (e.g., suppress if the prior bar also triggered)
- Tune `vol_burst` threshold against real realized volatility distributions; the synthetic candles are too smooth to trigger it
- Tune `funding_extreme` percentile cutoffs against real 30-day funding distributions; synthetic funding lacks the tail prints seen in real Hyperliquid data
- Add cross-asset state correlation detection as a dedicated extractor (not inferred post-hoc from KG structure): if HYPE and BTC both enter `price_momentum` within N bars, emit a `correlated_momentum` cross-asset event
- After re-calibration, re-run against real data and verify no single event type exceeds 40% share

---

## Priority 3: Hypothesis Quality Improvement (1-2 sessions)

**What to do:** Reduce structural redundancy in the 299-card output and surface higher-signal candidates.

**Why this matters:** At 299 candidates from 800 candles of synthetic data, the inventory will grow rapidly once real data flows in. Without quality filters, the `private_alpha` tier will be diluted by structurally similar paths that represent the same underlying relationship expressed through minor node variations. The goal is fewer, more distinct hypotheses with higher expected alpha per card.

**Concrete steps:**
- Add economic filter: reject paths where `price_momentum` is the sole intermediate node (too generic; nearly every cross-asset path will pass through it at current calibration)
- Add path diversity filter: if more than 50% of candidates in a secrecy tier share the same intermediate node, apply a coverage cap and discard the weakest-scored duplicates
- Plumb the `min_strong_ratio` filter already present in `operators.py` into the pipeline runner — it currently exists but is not activated
- Implement hypothesis deduplication by path signature: two candidates that traverse the same node sequence in the same direction should merge, keeping the higher-scored card and updating its edge weights

---

## Priority 4: Validation Infrastructure (2-3 sessions)

**What to do:** Build a lightweight backtester connector that tests each `private_alpha` card against historical event data.

**Why this matters:** The 72 `private_alpha` cards are currently all `validation_status: untested`. Without any empirical grounding, the secrecy tier functions as a structural filter rather than an alpha signal detector. Even a simple event study — "did the predicted outcome actually occur N bars after the trigger?" — would allow the system to distinguish structurally plausible hypotheses from economically validated ones.

**Concrete steps:**
- For each `private_alpha` card, extract: trigger event type, trigger symbol, predicted event type, predicted symbol
- Run an event study: for every historical trigger occurrence, check whether the predicted event occurred within 1-3 bars
- Compute hit rate and compare against base rate; threshold for `weakly_supported`: hit rate > base rate + 1 standard deviation
- Update `validation_status` field: `untested` → `weakly_supported` or `invalidated`
- Add decay mechanism: mark `private_alpha` cards as `decayed` if they remain `untested` for more than 30 days without a matching trigger event (stale structure indicator)

---

## Priority 5: Real Alpha Discovery Loop (ongoing)

**What to do:** Establish a weekly cadence of fresh discovery runs and inventory diffing.

**Why this matters:** A single static run is a snapshot. The value of the KG pipeline is in detecting regime shifts and emerging cross-asset structures over time. Running weekly against a rolling 30-day window and comparing the resulting hypothesis inventory against the prior week's inventory surfaces both emerging patterns (newly appeared hypotheses) and structural decay (hypotheses that disappeared).

**Concrete steps:**
- Automate weekly runs: pull fresh 30-day OHLCV + funding, run full pipeline, persist new cards
- Build an inventory diff: compare current run's hypothesis cards against prior week's by path signature
- Flag newly appeared `private_alpha` cards (potentially emerging edge)
- Flag disappeared `private_alpha` cards (structural change or regime shift)
- Write a weekly summary to `artifacts/weekly/YYYY-WNN.md` with: new cards, lost cards, stable cards, top-scored new private_alpha

---

## Priority 6: Execution KG Enhancement (2 sessions)

**What to do:** Add cross-symbol edges to the Execution KG and connect it to regime context.

**Why this matters:** The Execution KG currently has 27 nodes but zero cross-symbol edges, which means it can only generate intra-symbol execution hypotheses. Cross-asset execution spillover — for example, whether HYPE vol burst predicts degraded BTC execution quality — is a structurally plausible and potentially actionable signal that the current builder cannot surface.

**Concrete steps:**
- Add cross-symbol execution edges: connect `HYPE:vol_burst` nodes to `BTC:execution_quality` nodes with a spillover relation
- Connect regime nodes to execution condition nodes (currently Regime KG and Execution KG are linked only via the operator pipeline, not at the builder level)
- Once OI and liquidation data is available via Hyperliquid REST API, add a `liquidity_regime` hypothesis type that connects OI acceleration events to execution degradation

---

## Architecture Backlog (low priority, important for future phases)

These items do not block near-term progress but become relevant once real data is established:

- Confirm `HYPE/USDC:USDC` is tracked in hype-market-data collection; if not, add it
- Consider adding trades data via Hyperliquid REST API to enable buy/sell aggression burst state detection
- Consider OI data via Hyperliquid REST API for acceleration and squeeze detection (new state event types)
- Implement the `analogy_transfer` operator placeholder already present in `operators.py` — this would allow the system to ask whether a pattern observed in HYPE microstructure has a structural analog in BTC microstructure
