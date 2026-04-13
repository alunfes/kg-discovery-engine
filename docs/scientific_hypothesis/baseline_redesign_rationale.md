# C_rand 再設計の根拠 — v1 vs v2

**作成日**: 2026-04-14  
**関連 run**: run_016 (Phase 2, v1), run_017 (Phase 3, v2)

---

## 問題の診断: v1 baseline の構造的バイアス

### v1 の設計

C_rand v1 は `generate_random_baseline()` (feasibility_spike.py) で生成された。

```
KG (25ノード) 上でランダムパストラバーサル → 仮説を生成
```

- KG の直接エッジを辿るため、KG に含まれる既知の関係が自然に「ランダム」ペアに混入
- 結果として trivially-known pairs が多数含まれた

### v1 で観測されたバイアス

| 仮説 | ペア | 問題 |
|------|------|------|
| H2001 | HER2 → breast_cancer | HER2+ 乳がんは最も基本的な臨床知識 |
| H2002 | obesity → NAFLD | 直接的な代謝疾患関係 |
| H2003 | JAK inhibition → RA | JAK 阻害薬は RA 承認適応 |
| H2004 | beta-amyloid agg → Alzheimer | アミロイド仮説の中核 |
| H2008 | trastuzumab → breast_cancer | トラスツズマブの承認適応そのもの |

**→ C_rand v1 precision = 1.000** (20件全て positive)  
**→ SC-1 では C2 (0.833) が C_rand (1.000) を上回れず p=1.000**

### 診断結論

C_rand v1 の precision=1.000 は「良いベースライン」ではなく「trivial な ceiling」。  
KG パスで選ばれたペアが既存知識を反映しているのは当然であり、  
これを baseline に使うことは C2 を不当に不利にしていた。

---

## v2 の設計原則

### 1. 真のランダムサンプリング（KG パス非依存）

```python
# v2: エンティティプールから直接サンプリング
for c_id in CHEM_NODES:
    for b_id in BIO_NODES:
        if (c_id, b_id) not in blacklist:
            pool.append((c_id, b_id))
rng.shuffle(pool)
selected = pool[:50]
```

KG のエッジ構造を使わないため、KG に存在しない（= 検証されていない可能性が高い）ペアが多く選ばれる。

### 2. Blacklist 設計

| カテゴリ | 件数 | 内容 |
|----------|------|------|
| KG 1-hop エッジ | ~40 | KG の直接エッジを持つペア |
| trivially-known | ~40 | Phase 2 で判明した自明ペア + 承認適応 |
| C2/C1 と重複 | 100 | C2/C1 と同じペアを除外 |
| **合計** | **142** | 全除外対象 |

### 3. 難易度整合

| 指標 | C2 | C_rand_v2 | 差 |
|------|----|-----------|----|
| cross-domain ratio | 1.000 | 1.000 | 0 |
| avg chain length | 5.16 | 3.0 (trivial) | — |

cross-domain 比率を C2 (100%) と一致させた。

---

## v1 vs v2 比較

| 指標 | C_rand v1 | C_rand v2 |
|------|-----------|-----------|
| 生成方法 | KG パストラバーサル | ランダムエンティティペアリング |
| Known-pair blacklist | なし | あり (142件) |
| precision (L1) | 1.000 | 0.844 |
| known_fact_rate (L2) | 推定 ~1.0 | 0.420 |
| novel_supported_rate (L2) | 推定 ~0.0 | 0.219 |
| investigability | 1.000 | 0.640 |

v2 は v1 より確かに「難しい」ベースラインになった。

---

## 再検定結果の読み方

### Phase 3 結果 (v2)

| 指標 | C2 | C_rand_v2 |
|------|----|-----------|
| precision | 0.891 | 0.844 |
| novel_supported_rate | **0.130** | **0.219** |
| known_fact_rate | 0.740 | 0.420 |
| investigability | **0.920** | **0.640** |

SC-3r (investigability) のみ PASS (p=0.0007)。SC-1r/SC-2r/SC-4r は FAIL。

### 予想外の発見: C2 の known_fact_rate が高い

C_rand_v2 の known_fact_rate (0.420) は C2 (0.740) より**低い**という逆転現象が発生。

理由の仮説:
1. **known_fact threshold (=20) が低すぎる**: C2 が生成するペア（例: metformin→NAFLD）は  
   ≤2023 で 20件超のヒットを持つ程度には既知だが、trivially-known ではない。  
   threshold を 50 や 100 に上げると C2 の known_fact_rate は下がる可能性。

2. **C_rand_v2 はランダム ≠ "難しい"**: ランダムペアの多くは「そもそも共に研究されていない」  
   (past_hits が低い)。これにより known_fact に分類されにくい。  
   しかしその多くは not_investigated → novel_supported ではなく plausible_novel になる。

3. **novel_supported_rate の逆転**: C_rand_v2 は investigated されたペアが 32/50 と少ないが、  
   investigated された中での novel_supported 比率は 7/32 = 0.219 と高い。  
   C2 は 46/50 が investigated だが novel_supported は 6/46 = 0.130 にとどまった。

### 重要な観察: SC-3r の強い PASS

C2 investigability (0.920) vs C_rand_v2 (0.640), p=0.0007。

これは C2 パイプラインの重要な実用特性を示している:
- KG の multi-op が「調査可能な仮説」を確実に生成する
- C_rand_v2 では 18件 (36%) が not_investigated = 研究者が取り組みにくいペア

---

## 結論と今後の方向性

### 再検定の正直な評価

Phase 3 は NO-GO だが、Phase 2 とは**根本的に異なる問題**を示している:

- Phase 2: "C_rand が trivially easy すぎた" (評価不能)
- Phase 3: "C2 が KG 由来の known 関係に依存しすぎている" (実質的な問題)

### 次ステップ候補

1. **known_fact threshold の再校正**: threshold を 20 → 100 に引き上げ、  
   C2 の "metformin → NAFLD" 等が known_fact に分類されないか確認

2. **N 増加 (N≥200)**: N=50 では novel_supported が C2=6件, C_rand_v2=7件と絶対数が少なく、  
   検出力が不足。Power analysis: δ=0.1 差を p<0.05 で検出するには N≈200 必要

3. **ドメイン絞り込み**: C2 が最も新規な仮説を生成するのは「KG に存在するが  
   少数エッジしかない周辺エンティティ間」。高次数ノード(metformin, mTOR等)を  
   除外してスパースなエンティティに限定すると novel_supported_rate が上がる可能性

4. **人間ラベリングで known_fact の再判定**: 自動ラベリングの known_fact 判定が  
   calibrated かどうかを 10 件の手動確認で検証
