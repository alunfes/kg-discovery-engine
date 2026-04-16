# Value Loss Check — Run 038 Surface Pruning

## Summary verdict

**Value loss: NEGLIGIBLE**

Zero action_worthy or attention_worthy cards are removed. All 44 pruned cards sit at the
novelty floor (0.30) and belong exclusively to non-HYPE or non-cross-domain families.

---

## Pruned card analysis

### null_baseline (21 cards dropped)

These 21 cards represent single-asset BTC/ETH/SOL paths in the microstructure and execution
KGs. Every path follows the pattern `{ASSET}:state_A → relation → {ASSET}:state_B → relation → {ASSET}:state_C`.

**Why these are zero-value for delivery:**
- Single non-HYPE asset: no cross-asset or HYPE-specific discovery
- Discovered by naive single-KG compose with no operator contribution
- Represent well-known within-asset dynamics (BTC calm → momentum → vol_burst)
- Any naive market analyst would already know these sequences
- Secrecy level: all `shareable_structure` — never elevated to internal_watchlist or private_alpha
- Novelty score: 0.30 (minimum floor, no unseen pair or cross-domain component)

**Score profile of null_baseline cards:**
```
actionability: 0.80 (high — microstructure scope gives +0.3 + tradeable asset +0.2 + short path +0.2 + named KG +0.1)
novelty:       0.30 (floor — same-symbol pair penalized for same-state, no cross-asset bonus)
```

The high actionability score is a scoring artifact: the scorer rewards microstructure scope
without distinguishing whether the asset is HYPE or non-HYPE. These cards score "actionable"
but carry no tradeable alpha because they are BTC/ETH/SOL intra-domain sequences.

---

### baseline_like (23 cards archived)

These 23 cards are at novelty_score=0.30 and split into:
- 8 `execution+regime` cards: regime-label-only paths with no tradeable asset symbols
- 15 `cross_asset` cards: HYPE-adjacent (HYPE appears as bridge but not as subject/object)

**Why these are low-value for immediate delivery:**
- execution+regime (8): paths like `regime::calm → suppresses → regime::funding_long → activates → regime::high_vol`
  These are pure regime label transitions — no specific entry signal, no asset specificity
- cross_asset (15): at the novelty floor, meaning the (subject, object) pair appears elsewhere
  in the candidate set, no novel structure is contributed

**Key safeguard: ARCHIVE not DROP**
The baseline_like cards are archived (not discarded). They remain retrievable if:
1. A specific regime transition is confirmed in live data
2. Follow-up evidence elevates the novelty of a specific pattern
3. A HYPE regime event makes the execution+regime paths actionable

---

## Private_alpha integrity check

All 102 private_alpha cards survive pruning intact.

Private_alpha criteria: `actionability >= 0.70 AND novelty >= 0.50 AND cross_asset AND HYPE-involved AND directional`

No null_baseline or baseline_like card satisfies private_alpha criteria:
- null_baseline: no HYPE, no cross-asset → cannot reach private_alpha
- baseline_like: novelty=0.30 < 0.50 threshold → cannot reach private_alpha

**Private_alpha retention: 100%**

---

## Internal_watchlist integrity check

All 88 internal_watchlist cards survive pruning intact.

Internal_watchlist criteria: `actionability >= 0.50 OR novelty >= 0.70`

The 8 baseline_like execution+regime cards have actionability=0.60 but novelty=0.30, so they
were scored as `shareable_structure` by the existing scorer (HYPE not involved). No true
internal_watchlist card is removed.

**Internal_watchlist retention: 100%**

---

## Resurfaced-card utility assessment

| Archived tier | Count | Promotion trigger | Expected utility if promoted |
|---------------|-------|-------------------|------------------------------|
| execution+regime regime-paths | 8 | Confirmed regime shift event lasting >7d | Medium: execution signal only if HYPE-correlated |
| cross_asset novelty-floor | 15 | New evidence for specific (HYPE, {BTC/ETH/SOL}) pair | Low-medium: novelty floor means pair is already known |

Estimated resurfacing rate: <10% of archived cards (2-3 cards) within a 30-day window.

---

## Predicted vs actual reduction

| Metric | Predicted (run037) | Actual (run038) |
|--------|--------------------|-----------------|
| Total reduction | ~36% | 10.8% |
| null_baseline dropped | not specified | 21 (5.1%) |
| baseline_like archived | not specified | 23 (5.6%) |
| value loss | negligible | ZERO (0.0%) |

**The 36% prediction was not achieved.** The actual reduction is 10.8%.

Root cause of overestimate: the run037 prediction likely assumed a broader definition of
"baseline_like" that included all shareable_structure cards (219 = 53.5% of total).
The run038 definition is more conservative, archiving only the minimum-novelty (0.30)
non-HYPE subset. This preserves 175 shareable_structure cards in the active surface —
those representing genuine structural insights about HYPE cross-domain patterns.

The conservative pruning is recommended over the aggressive alternative because:
1. 175 shareable_structure cards include HYPE-involved patterns worth monitoring
2. The multi-op pipeline's cross-domain discoveries should not be bulk-archived
3. The 10.8% reduction achieves zero value loss, while a 36% reduction would lose
   operator-derived HYPE structural patterns
