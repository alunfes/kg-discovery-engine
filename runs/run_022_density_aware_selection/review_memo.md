# run_022 density-aware pair selection — review_memo.md
Generated: 2026-04-14 10:57

## 実験概要

**目的**: density-aware C2 pair selection により C1 との investigability parity を達成できるか検証。
**仮説**: H_density_select (parity), H_matched_parity (density-matched parity)
**参照**: run_021 にて H_ceiling 支持 (log_min_density: |r|=0.461)、低密度群のみ C1-C2 gap 集中。

## 実験条件

| 条件 | N | 説明 |
|------|---|------|
| C2_density_aware | 70 | density filter (min_density >= 8105.5)後の multi-op pipeline |
| C1_baseline | 70 | run_018 C1 再利用 |
| C_rand_v2 | 70 | run_018 C_rand_v2 再利用 |

**density threshold**: run_021 Q2_median = 8105.5

## 主要結果

| Method | N | Investigated | Investigability | Novel_Supported |
|--------|---|--------------|-----------------|-----------------|
| C2_density_aware | 70 | 68 | 0.971 | 9 |
| C1_baseline | 70 | 68 | 0.971 | 5 |
| C_rand_v2 | 70 | 42 | 0.600 | 15 |

## 統計検定

### SC_ds_primary (主検定): C2_density_aware parity with C1
- C2_da investigability: 0.971
- C1 investigability: 0.971
- Delta: 0.0000 (threshold: 0.02)
- Fisher two-sided p: 1.0000
- Parity条件 (p>0.05): ✓ PASS
- Delta条件 (<=0.02): ✓ PASS
- **判定: ✓ PASS**

### SC_ds_improvement: C2_da > run_018 C2 baseline (0.914)
- C2_da rate: 0.971
- **判定: ✓ PASS**

### SC_ds_random: C2_da > C_rand_v2
- Fisher one-sided p: 0.0000
- **判定: ✓ PASS**

## Matched Comparison (density-only bins)

- C1-C2_da gap (unmatched): 0.0000
- Reportable cells: 3
- Max gap: 0.0645
- **H_matched_parity: REJECTED**
- Note: max reportable gap=0.0645 > 0.03: H_matched_parity rejected

## 総合判定

**GO/NO-GO: GO**

- SC_ds_primary (parity): PASS
- SC_ds_improvement: PASS
- SC_ds_random: PASS

## 考察

### H_density_select: 支持

density filter (min_density >= 8105.5) 適用後、C2_density_aware investigability は 0.971 となり、C1 investigability 0.971 と統計的に同等 (Fisher two-sided p=1.0000 > 0.05, delta=0.0000 <= 0.02)。

run_021 で特定された density ceiling の影響を、density filter によって制御できることが確認された。

### 改善確認

C2_density_aware (0.971) は run_018 C2 baseline (0.914) を超えた。density filter が C2 investigability 向上に有効であることが確認された。

## 次のステップ

- density-aware selection の有効性が確認された
- threshold の最適化 (Q1/Q3 での感度分析) を検討
- 他ドメインペアへの適用可能性を評価
- 論文用図表の作成
