# Run 031 — Operator Burden Summary

Operator burden = reviews_per_day × items_per_push (item-reviews/day).

## Metric Note: Raw vs Post-Collapse

The push engine tracks **raw deck counts** (fresh+active cards accumulated across
all batches) at each push event. The poll_45min baseline's 4.8 items/review is
**post-family-collapse** from a single batch of 20 raw cards (Run 027 collapse factor = 0.24).

To compare fairly, apply the same collapse factor to push deck counts:
- Raw avg_cards_per_push (Variant A): 24.1
- Effective post-collapse: 24.1 × 0.24 ≈ **5.8 items/push**
- Effective daily burden: 21.0 × 5.8 = **121.8 item-reviews/day**

## Burden Comparison (Corrected)

| Config | Reviews/day | Items/push (effective) | Burden (items/day) | vs poll_45min |
|--------|------------|------------------------|-------------------|---------------|
| Run027 poll_45min (ref) | 32.0 | 4.8 (post-collapse) | 153.6 | baseline |
| Run029B push baseline (T3=10min) | 21.0 | ~5.8 (est. post-collapse) | ~121.8 | −31.8 (−21%) |
| **Run031 Variant A (T3=5min)** | **21.0** | **~5.8 (est. post-collapse)** | **~121.8** | **−31.8 (−21%)** |

Raw deck counts (for reference, pre-collapse):

| Config | Reviews/day | Raw cards/push | Raw burden | Note |
|--------|------------|----------------|------------|------|
| Run029B push T3=10min | 21.0 | 24.1 | 510.6 | pre-collapse |
| **Run031 Variant A T3=5min** | **21.0** | **24.1** | **510.6** | pre-collapse |

## Day-to-Day Stability

- Variant A reviews/day range: 18–27 (mean 21.0)
- Run029B reviews/day range: 18–27 (mean 21.0)

The 18–27 range reflects hot_batch_probability variance (0.30); busier market
days generate more T1/T2 triggers. A narrow 1.5× range (min/max) confirms
the policy is stable across simulated market conditions.

## Conclusion

Push-default (Variant A) reduces daily review count by **34%** (21 vs 32) and
reduces effective item burden by **~21%** (121.8 vs 153.6) compared to poll_45min.
The reduction comes from push suppression: 70% of batch windows in quiet markets
produce no push (S1/S2/S3 suppress), whereas poll_45min fires unconditionally.
