# Loss Value Analysis — Run 042

**Total permanently lost**: 61

## Score Distribution of Lost Cards

| Metric | Value |
|--------|-------|
| N | 61 |
| Mean | 0.4918 |
| P25 | 0.4420 |
| P50 | 0.4908 |
| P75 | 0.5280 |
| P90 | 0.5781 |
| Min | 0.4010 |
| Max | 0.6037 |

**High-value losses** (score ≥ 0.55): 12 (19.7%)

**Counterfactually attention_worthy** (score ≥ 0.60): 2 (3.3%)

Note: No baseline_like card can be counterfactually action_worthy (max baseline_like score = 0.62 < actionable_watch threshold = 0.74).

---

## High-Value Losses by Family

(score ≥ 0.55)

| Family | High-value lost | Total lost | High-value rate |
|--------|----------------|------------|-----------------|
| cross_asset | 1 | 17 | 5.9% |
| momentum | 2 | 9 | 22.2% |
| null | 3 | 15 | 20.0% |
| reversion | 1 | 7 | 14.3% |
| unwind | 5 | 13 | 38.5% |

## Interpretation

Baseline_like cards by definition score 0.40–0.62. Even at the top of this range, they cannot be classified as action_worthy (threshold: 0.74). The permanent loss of these cards means we lose *historical confirmation context*, not *actionable signal*.

High-value baseline_like cards (score ≥ 0.55) are near-miss monitor_borderline cards. Their loss is more significant: had they been surfaced immediately, operators might have classified them as monitor_borderline attention items.

Families with high proportion of high-value losses are the primary MITIGATE targets: these families consistently produce baseline_like cards near the monitor_borderline boundary, and their permanent loss is genuinely suboptimal.
