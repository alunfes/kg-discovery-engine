# Run 023: Default vs Slice Comparison

Global baseline: 10 windows, hit_rate_strict=0.840, hit_rate_broad=1.000

## Slice: calm (windows [0, 2, 4, 5])

| Metric | Global | Slice | Δ% | Exceeds ±20%? |
|--------|--------|-------|----|--------------|
| hit_rate_strict | 0.8400 | 1.0000 | +19.1% | no |
| hit_rate_broad | 1.0000 | 1.0000 | +0.0% | no |
| hl_effectiveness | 1.0000 | 1.0000 | +0.0% | no |
| monitoring_cost_efficiency | 0.0160 | 0.0153 | -3.9% | no |
| promote_freq | 0.0663 | 0.0707 | +6.6% | no |
| contradict_freq | 0.0000 | 0.0000 | +0.0% | no |
| time_to_outcome_mean | 3.6300 | 1.2500 | -65.6% | YES ⚠ |

## Slice: event-heavy (windows [1, 3, 6, 8, 9])

| Metric | Global | Slice | Δ% | Exceeds ±20%? |
|--------|--------|-------|----|--------------|
| hit_rate_strict | 0.8400 | 0.6800 | -19.1% | no |
| hit_rate_broad | 1.0000 | 1.0000 | +0.0% | no |
| hl_effectiveness | 1.0000 | 1.0000 | +0.0% | no |
| monitoring_cost_efficiency | 0.0160 | 0.0163 | +2.2% | no |
| promote_freq | 0.0663 | 0.0585 | -11.8% | no |
| contradict_freq | 0.0000 | 0.0000 | +0.0% | no |
| time_to_outcome_mean | 3.6300 | 2.9400 | -19.0% | no |

## Slice: sparse (windows [7])

| Metric | Global | Slice | Δ% | Exceeds ±20%? |
|--------|--------|-------|----|--------------|
| hit_rate_strict | 0.8400 | 1.0000 | +19.1% | no |
| hit_rate_broad | 1.0000 | 1.0000 | +0.0% | no |
| hl_effectiveness | 1.0000 | 1.0000 | +0.0% | no |
| monitoring_cost_efficiency | 0.0160 | 0.0167 | +4.4% | no |
| promote_freq | 0.0663 | 0.1143 | +72.4% | YES ⚠ |
| contradict_freq | 0.0000 | 0.0000 | +0.0% | no |
| time_to_outcome_mean | 3.6300 | 15.5000 | +327.0% | YES ⚠ |

