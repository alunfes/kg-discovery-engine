# ACCEPT / MITIGATE / INVESTIGATE Classification — Run 042

**Total permanent losses**: 61

| Classification | Count | % | Interpretation |
|----------------|-------|---|----------------|
| ACCEPT | 41 | 67.2% | Structural; accept as policy spec |
| MITIGATE | 19 | 31.1% | Addressable by upstream change |
| INVESTIGATE | 1 | 1.6% | Unclear; needs more data |

---

## ACCEPT Losses

**Count**: 41 (67.2% of losses)

These losses are structural — they represent cases where no reasonable policy change could recover the card without breaking other guarantees.

### ACCEPT sub-categories

- **no_companion_window**: 28 (68.3% of ACCEPT)
- **proximity_miss**: 8 (19.5% of ACCEPT)
- **time_expired**: 3 (7.3% of ACCEPT)
- **companion_preceded**: 2 (4.9% of ACCEPT)

### ACCEPT examples (first 5)

- `c000` | family=null | score=0.5004 | archival_regime=sparse | transition=sparse→sparse | gap=540min | mechanism=time_expired
- `c017` | family=null | score=0.4916 | archival_regime=sparse | transition=sparse→sparse | gap=300min | mechanism=proximity_miss
- `c000` | family=momentum | score=0.4841 | archival_regime=sparse | transition=sparse→sparse | gap=900min | mechanism=time_expired
- `c001` | family=null | score=0.5144 | archival_regime=sparse | transition=sparse→sparse | gap=120min | mechanism=no_companion_window
- `c000` | family=null | score=0.4742 | archival_regime=sparse | transition=sparse→sparse | gap=780min | mechanism=time_expired

---

## MITIGATE Losses

**Count**: 19 (31.1% of losses)

These losses are addressable. The most impactful upstream changes are:

### Fix pattern: `extend_archive_max_age_per_family` (9 losses)

Families: unwind=4, cross_asset=3, reversion=2

Examples:
- `c001` | family=cross_asset | score=0.4158 | transition=sparse→sparse | gap=300min
- `c009` | family=cross_asset | score=0.5045 | transition=sparse→sparse | gap=300min
- `c018` | family=cross_asset | score=0.5225 | transition=sparse→sparse | gap=300min

### Fix pattern: `regime_aware_archival` (10 losses)

Families: momentum=4, cross_asset=2, reversion=2, unwind=2

Examples:
- `c001` | family=cross_asset | score=0.5826 | transition=sparse→sparse | gap=240min
- `c000` | family=momentum | score=0.4257 | transition=sparse→sparse | gap=150min
- `c002` | family=cross_asset | score=0.4705 | transition=sparse→sparse | gap=180min

---

## INVESTIGATE Losses

**Count**: 1 (1.6% of losses)

These losses don't fit cleanly into ACCEPT or MITIGATE. Further data or logic review needed.

- **proximity_miss**: 1 (100.0% of INVESTIGATE)

### INVESTIGATE examples (first 5)

- `c004` | family=momentum | score=0.4568 | transition=mixed→mixed | gap=330min | reason: proximity_miss in mixed regime, gap=330min, family=momentum, score=0.4568 — no c...

---

## Summary Recommendations


### Immediate (no code change required)

- **Accept** all time_expired and companion_preceded losses as spec (5 losses). These are by design.

### Low-effort mitigations

- **Per-family archive_max_age extension**: extend archive_max_age for high-value families (cross_asset, reversion) from 480min to ~720min in calm/active regime. Expected to recover ~9 losses (14.8% of total).
- **Regime-aware archival**: skip baseline_like archival for high-activity families when regime is calm/active. Expected to recover ~10 losses (16.4% of total).

### Do not attempt

- Widening resurface_window_min (Run 040 showed zero net improvement due to LCM(30,45)=90min constraint)
- Multi-resurface policy (Run 041 showed it degrades quality)
- Reducing archive_max_age (would increase time_expired losses)
