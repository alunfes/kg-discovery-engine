# Pre-Registration: Investigability Hypothesis v2 (run_018)

**Experiment ID**: investigability_v2  
**Pre-registration Date**: 2026-04-14  
**Status**: REGISTERED (not yet frozen — freeze occurs before data collection)  
**Registry file**: configs/investigability_registry.json

---

## 1. 動機と HARKing 防止

run_017 の副次評価基準 SC-3r において、KG multi-op (C2) の investigability が
C_rand_v2 に対して有意に高いことが確認された (C2=0.920 vs C_rand_v2=0.640, p=0.0007)。

この結果は **事前に primary endpoint として設定していなかった**。
SC-3r は run_017 の primary endpoint (SC-1r: novel_supported_rate) の副次評価として
探索的に設定された指標である。

本事前登録の目的:
- run_017 SC-3r 発見後に「investigability が高い仮説を生成する」という仮説を立てる行為は
  HARKing (Hypothesizing After Results are Known) に該当する可能性がある
- この実験は SC-3r 結果が N=70 でも再現されるかを検証する
- 仮説・統計手法・成功基準を**データ収集前**に公開登録することで透明性を確保する

**重要**: 本実験は SC-1r (novel_supported_rate) の救済を目的としない。
run_017 で SC-1r が FAIL した事実は変わらない。N を増加させても SC-1r の再検定は行わない。

---

## 2. 仮説定義

### 帰無仮説 (H0_inv)

> KG multi-op (C2) は random sampling (C_rand_v2) より investigable hypothesis を
> 多く生成しない（investigability_rate が等しいか低い）

### 対立仮説 (H1_inv) — Primary

> KG multi-op (C2) は random sampling (C_rand_v2) より investigable hypothesis を
> 有意に多く生成する（investigability_rate が高い）

**検定方向**: 片側 (C2 > C_rand_v2)  
**有意水準**: α = 0.05  
**検定手法**: Fisher's exact test (one-sided, 手実装 — scipy 不可)

---

## 3. 用語定義

### Investigable Hypothesis

後続文献 (PubMed 2024-2025) で検証対象となった仮説。
Layer 1 ラベルが `not_investigated` 以外であること。

| Layer 1 ラベル | Investigable? |
|---------------|--------------|
| supported | YES |
| partially_supported | YES |
| contradicted | YES |
| investigated_but_inconclusive | YES |
| not_investigated | **NO** |

### Investigability Rate

```
investigability_rate = investigated_count / total_count
```

`investigated_count` = supported + partially_supported + contradicted + investigated_but_inconclusive

---

## 4. 評価方法

### Primary Endpoint

- **指標**: investigability_rate (C2 vs C_rand_v2)
- **検定**: Fisher's exact test (one-sided, H_a: C2 > C_rand_v2)
- **有意水準**: p < 0.05

### Secondary Endpoint

- **指標**: investigability_rate (C2 vs C1)
- **検定**: Fisher's exact test (one-sided, H_a: C2 > C1)
- **有意水準**: p < 0.10 (緩めの基準 — 探索的)

### Replication Criterion

- **基準**: C2 investigability_rate >= 0.85
- **根拠**: run_017 C2 investigability = 0.920。半分以上の再現を要件とする。

---

## 5. サンプルサイズ根拠 (N=70 per method, Total=210)

### 検出力計算

run_017 観測: C2=0.920, C_rand_v2=0.640, 差=0.280

N=50 (run_017) での Fisher's exact:
- p=0.0007 (強い有意差)
- しかし N=50 は 95% 信頼区間が広い

N=70 (run_018) での期待検出力:
- δ=0.20 (保守的推定、run_017 差の 71%) で検出力 > 85%
- δ=0.28 (run_017 観測値) で検出力 > 95%

### N 増加の目的

1. **SC-3r 再現確認** — N=50 の単一実験結果 (p=0.0007) が N=70 でも維持されるか確認
2. **効果量の推定精度向上** — investigability 差の信頼区間を縮小
3. **新 primary endpoint での検定** — H_inv を適切なサンプルサイズで検証

**N 増加は SC-1r 救済目的ではない。SC-1r は本実験の評価指標に含まない。**

---

## 6. データ収集プロトコル

### PubMed 検索

- **Validation period**: 2024/01/01 — 2025/12/31
- **Past period** (Layer 2 用): 1900/01/01 — 2023/12/31
- **Rate limit**: ≥ 1.1 秒間隔 (PubMed API 規約遵守)
- **Max papers per hypothesis**: 5 件
- **Seed**: 42 (決定論的)

### Time Split 設定 (run_017 と同一)

```
Past corpus: ≤ 2023 — known_fact 判定に使用
Validation: 2024-2025 — investigability 判定に使用
```

---

## 7. 二層ラベリング

### Layer 1 (5-class)

PubMed 2024-2025 ヒット数とキーワード分析に基づく分類:

| ラベル | 条件 |
|--------|------|
| supported | 2本以上の論文で positive キーワード優勢 |
| partially_supported | 1本以上の論文で positive キーワード、または 3件以上ヒット |
| contradicted | negative キーワード優勢 |
| investigated_but_inconclusive | ヒットあり、ただし mixed/inconclusive |
| not_investigated | 0件ヒット |

### Layer 2 (novelty)

`KNOWN_THRESHOLD = 20` (≤2023 PubMed ヒット数基準):

| ラベル | 条件 |
|--------|------|
| known_fact | past_hits > 20 |
| novel_supported | Layer1 positive かつ past_hits ≤ 20 |
| implausible | Layer1 = contradicted |
| plausible_novel | その他 |

**注意**: Layer 2 は SC-1r (novel_supported_rate) のための補助情報として記録するが、
本実験の primary/secondary endpoint の判定には **使用しない**。

---

## 8. 成功基準

| 基準 | 内容 | 判定水準 |
|------|------|--------|
| SC_inv_primary | C2 investigability_rate > C_rand_v2 | Fisher p < 0.05 (primary) |
| SC_inv_secondary | C2 investigability_rate > C1 | Fisher p < 0.10 (exploratory) |
| SC_inv_replication | C2 investigability_rate >= 0.85 | 記述統計 |

### 総合判定

- **PASS**: SC_inv_primary PASS (p < 0.05)
- **FAIL**: p >= 0.05 または C2 investigability ≤ C_rand_v2

**FAIL 時の対応**: investigability 仮説を棄却する。次フェーズは設けない。

---

## 9. Sensitivity Analysis (探索的のみ)

known_fact threshold を変化させた際の各指標への影響を記録する。

| Threshold | 内容 |
|-----------|------|
| 20 | Primary analysis (run_017 設定) |
| 50 | Looser threshold |
| 100 | Very loose threshold |
| 200 | Extremely loose threshold |

**重要**: Sensitivity analysis の結果は primary conclusion を変更しない。
Primary analysis は threshold=20 で固定。

---

## 10. 仮説生成 (N=70 per method)

### C2 (multi_op): 70件

align → union → compose (biology + chemistry KG)

- run_017 からの継続: 50件 (H3001-H3050)
- 新規追加: 20件 (H3051-H3070)
- seed=42 で決定論的

### C1 (single_op): 70件

compose only (biology KG)

- run_017 からの継続: 50件 (H4001-H4050)
- 新規追加: 20件 (H4051-H4070)

### C_rand_v2: 70件

Random cross-domain pairs (blacklisted known-fact pairs excluded)

- pool から seed=42 で決定論的サンプリング
- run_017 の 50件を含み、追加 20件を新規サンプリング
- 既 C2/C1 ペアは blacklist 除外済み

---

## 11. Freeze プロトコル

1. 仮説生成スクリプトの commit hash を記録
2. `configs/investigability_registry.json` の `kg_generation_commit` と
   `hypothesis_generation_commit` フィールドを更新
3. `frozen: true` に設定
4. PubMed validation 実行前に freeze commit を作成

**Freeze 後の変更禁止**:
- 仮説内容の変更
- 統計手法の変更
- 成功基準の変更
- サンプルサイズの変更

---

## 12. SC-1r との関係の明記

**本実験は SC-1r (novel_supported_rate) の救済を目的としない。**

run_017 SC-1r FAIL の事実:
- C2: novel_supported_rate = 0.130
- C_rand_v2: novel_supported_rate = 0.219
- p = 0.9088 → FAIL

この結果は変わらない。N を増加させても SC-1r の検証を再試行しない。
investigability (SC-3r) の再現確認のみが本実験の目的である。

---

## 13. 検証の進化経路

```
Phase 1: trading alpha 検証（run_001〜014）
    → 市場予測精度での KG 優位性を検証
    → FAIL / 打ち切り

Phase 2: scientific hypothesis 検証（run_015〜017）
    → Primary: SC-1r (novel_supported_rate) → FAIL
    → 副次発見: SC-3r (investigability) PASS (p=0.0007, N=50)

Phase 3: investigability 仮説検証（run_018 — 本実験）
    → Primary: SC_inv_primary (investigability, N=70) → TBD
    → Pre-registered before data collection (HARKing 防止)
    → FAIL → investigability 仮説棄却、実験終了
```

---

## 14. 登録情報

| 項目 | 値 |
|------|-----|
| 登録日 | 2026-04-14 |
| 実験開始予定 | 2026-04-14 |
| 担当 | alunfes |
| Registry commit | TBD (freeze 時に記録) |
| Freeze 状態 | 未完了 (データ収集前に freeze 予定) |
