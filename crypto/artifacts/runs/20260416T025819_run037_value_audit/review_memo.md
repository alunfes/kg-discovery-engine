# Review Memo — Run 037: Real-Data Value Audit

**Date**: 2026-04-16  
**Status**: Complete  

---

## What We Did

Applied the locked Run 036 delivery policy to 100 simulated shadow sessions
(5 regime profiles × 20 seeds × 8h each = 800 operator-hours) and classified
every surfaced card instance by operational value.

## Top 3 Findings

1. **90.7% of surfaced instances are redundant**.  The push engine already filters
   well, but null_baseline + baseline_like cards still reach the surface through
   the volume-driven S1/S2 escape paths in hot batches.

2. **Resurfaced cards deliver 5.6× higher value density** (0.322 vs 0.057).
   The 120-min archive/resurface window is the single most effective signal-quality
   amplifier in the current policy.

3. **Value density is regime-stable** (0.067–0.073).  The policy doesn't degrade
   in hot markets despite 5× volume increase.  Operator burden (cards/push) is the
   real hot-regime problem, not signal quality.

## Top Priority for Run 038

Two pre-suppression rules cover 14,698 redundant records (36.4% of surface):

- Drop `null_baseline` branch before delivery layer (zero value, all tiers)
- Route `baseline_like` tier to archive-only (not surfaced until confirmed)

These two rules reduce surface volume ~52% with near-zero value loss.

## What Did Not Work as Expected

- The live-only vs batch-supported comparison surface density is misleading
  (0.133 vs 0.065) because live-only cards can't be action_worthy by definition.
  The relevant insight is that live-only attention_worthy cards are real signals
  awaiting confirmation — they should be flagged "pending" in operator UI, not
  suppressed.

## Decision Made

Maintain locked policy as-is for Run 038 production rollout, adding only the
null_baseline pre-filter and baseline_like archive routing as incremental changes.
Do not modify T1/T2/S3 thresholds until post-filter baseline is established.
