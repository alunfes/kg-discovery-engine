# Drift Scaleup Comparison — 57 nodes (Run 008) vs 500+ nodes (Run 009)

## Run 008 Drift (57 nodes, Condition C)
| Depth | Drift Rate |
|-------|-----------|
| 2-hop | 37% |
| 3-hop | 67% |
| 4-5-hop | 83% |

## Run 009 Drift (500+ nodes, per condition)

### Condition A
| Depth | Run009 Rate | Delta vs Run008 |
|-------|------------|----------------|
| 2-hop | 23.90% | -13.10% |
| 3-hop | 49.50% | -17.50% |
| 4-5-hop | 71.76% | -11.24% |

### Condition B
| Depth | Run009 Rate | Delta vs Run008 |
|-------|------------|----------------|
| 2-hop | 22.36% | -14.64% |
| 3-hop | 46.15% | -20.85% |
| 4-5-hop | 100.00% | +17.00% |

### Condition C
| Depth | Run009 Rate | Delta vs Run008 |
|-------|------------|----------------|
| 2-hop | 22.91% | -14.09% |
| 3-hop | 48.37% | -18.63% |
| 4-5-hop | 71.17% | -11.83% |

### Condition D
| Depth | Run009 Rate | Delta vs Run008 |
|-------|------------|----------------|
| 2-hop | 22.91% | -14.09% |
| 3-hop | 48.37% | -18.63% |
| 4-5-hop | 71.17% | -11.83% |

## Interpretation

- Negative delta → drift DECREASED at larger scale (scale artifact confirmed)
- Positive delta → drift INCREASED (structural problem, not scale artifact)
- ~0 delta → drift is scale-independent (operator design issue)