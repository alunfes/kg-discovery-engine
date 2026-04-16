# Noise Analysis — Run 041

A noisy resurface = trigger classification is 'redundant' (low-quality companion; resurface provides no signal uplift).

| Variant | Max resurfaces | Total events | ~Noisy events | Noisy rate | vs baseline |
|---------|----------------|--------------|---------------|-----------|-------------|
| baseline | 1 | 301 | ~26 | 0.086 | +0.0pp |
| (by number) | | #1: 8.6% (n=301) | #2: — (n=0) | #3+: — (n=0) | | |
| variant_a | 2 | 427 | ~42 | 0.098 | +1.2pp |
| (by number) | | #1: 9.0% (n=266) | #2: 11.2% (n=161) | #3+: — (n=0) | | |
| variant_b | 3 | 466 | ~47 | 0.101 | +1.45pp |
| (by number) | | #1: 8.4% (n=250) | #2: 10.3% (n=146) | #3+: 15.7% (n=70) | | |
| variant_c | unlimited | 474 | ~48 | 0.101 | +1.49pp |
| (by number) | | #1: 7.6% (n=236) | #2: 10.4% (n=135) | #3+: 15.5% (n=103) | | |

## Interpretation

If later resurfaces (2nd, 3rd) have higher noisy rates than 1st resurfaces,
multi-resurface is generating diminishing-value events.
If noisy rates are stable across numbers, quality is preserved.
