# Investigability Replication Results (run_018)

**Date**: 2026-04-14
**Status**: GO
**Pre-registration**: configs/investigability_registry.json
**Purpose**: Replicate SC-3r (investigability, p=0.0007 in run_017) with N=70.
**NOT a rescue of SC-1r** — novel_supported_rate FAIL stands.

---

## Hypotheses Tested

| Method | N | Description |
|--------|---|-------------|
| C2 (multi-op) | 70 | align → compose, cross-domain (bio + chem KG) |
| C1 (single-op) | 70 | compose only, biology KG |
| C_rand_v2 | 70 | Random entity pairs (known-fact excluded) |

---

## Results

| Method | N | Investigated | Investigability |
|--------|---|-------------|----------------|
| C2 | 70 | 64 | **0.914** |
| C1 | 70 | 68 | **0.971** |
| C_rand_v2 | 70 | 42 | **0.600** |

---

## Success Criteria

| 基準 | C2 | 比較 | p値 | 結果 |
|------|-----|------|-----|------|
| SC_inv_primary (C2 > C_rand_v2, p<0.05) | 0.914 | C_rand=0.600 | 0.0000 | **PASS** |
| SC_inv_secondary (C2 > C1, p<0.10) | 0.914 | C1=0.971 | 0.9687 | **FAIL** |
| SC_inv_replication (C2 >= 0.85) | 0.914 | threshold=0.85 | — | **PASS** |

---

## 総合判定: **GO**

GO | SC_inv_primary(p<0.05)=PASS | SC_inv_secondary(p<0.10)=FAIL | SC_inv_replication(>=0.85)=PASS

---

## SC-1r との関係 (重要)

**本実験は SC-1r の救済目的ではない。**

run_017 SC-1r (novel_supported_rate) は FAIL (p=0.9088) であり、この判定は変わらない。
investigability の高さは novel_supported_rate とは独立した指標であり、
H1 (KG が novel supported hypothesis を生成する) の棄却を覆すものではない。

本実験で検証するのは:
> 「KG multi-op は investigable な仮説を生成する傾向があるか」

これは新しい仮説 H1_inv として pre-registered されたものである。

---

## 検証の系譜

| Phase | Run | Primary Endpoint | 結果 |
|-------|-----|----------------|------|
| Phase 2 | run_016 | precision_positive | FAIL (baseline bias) |
| Phase 2 re-test | run_017 | novel_supported_rate (SC-1r) | **FAIL** (p=0.9088) |
| Phase 3 (本実験) | run_018 | investigability (SC_inv_primary) | **GO** |
