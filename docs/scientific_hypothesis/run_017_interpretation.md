# run_017 解釈文書 — Scientific Hypothesis 検証 Close

**作成日**: 2026-04-14  
**Status**: CLOSED — NO-GO (主解析), SC-3r のみ PASS

---

## 1. run_017 検定結果サマリー

### 実験条件

| 項目 | 設定 |
|------|------|
| N per method | 50 |
| Baseline (C_rand) | v2 — ランダムエンティティプールサンプリング (1-hop KG除外済み) |
| ラベリング | 二層 (Layer 1: plausible / Layer 2: novelty 分類) |
| Primary endpoint | SC-1r: novel_supported_rate |

### 数値結果

| Method | N | Investigated | Precision (L1) | Novel_Sup | Known_Fact | Novel_Sup_Rate | Investigability |
|--------|---|-------------|----------------|-----------|------------|----------------|-----------------|
| C2 (multi-op) | 50 | 46 | 0.891 | 6 | 37 | 0.130 | 0.920 |
| C1 (single-op) | 50 | 49 | 0.980 | 4 | 46 | 0.082 | 0.980 |
| C_rand_v2 | 50 | 32 | 0.844 | 7 | 21 | 0.219 | 0.640 |

### 統計検定結果

| SC | 説明 | C2 | C_rand_v2 | p値 | 結果 |
|----|------|-----|-----------|-----|------|
| SC-1r (primary) | novel_supported_rate C2 > C_rand_v2 | 0.130 | 0.219 | 0.9088 | **FAIL** |
| SC-2r | plausible_novelty_rate C2 > C_rand_v2 | 0.260 | 0.580 | 0.9997 | **FAIL** |
| SC-3r | investigability C2 >= C_rand_v2 | 0.920 | 0.640 | 0.0007 | **PASS** |
| SC-4r (exploratory) | known_fact_rate C2 < C_rand_v2 | 0.740 | 0.420 | 0.9997 | **FAIL** |

---

## 2. SC-1r FAIL の解釈

**C2 は novel_supported_rate において C_rand_v2 に勝てなかった。**

- C2 novel_supported_rate = 0.130、C_rand_v2 = 0.219、差 = -0.089
- p = 0.9088 は方向が逆（C2 の方が低い）を示す
- これは C2 が「全くダメ」ということではなく、**supported novelty という評価軸では優位性を確認できなかった**という事実である

重要な留意点:
- C2 の known_fact_rate = 0.740 が高い。KG multi-op は既知の強い関係に収束しやすい傾向がある
- これは「仮説生成器の全面的な敗北」ではなく「supported novelty 軸での優位性の不在」である
- SC-1r FAIL は正式な結果として維持する。緩和・言い訳はしない

---

## 3. SC-3r PASS の解釈

**investigability (p=0.0007) は統計的に非常に強い結果である。**

- C2 investigability = 0.920、C_rand_v2 = 0.640、差 = +0.280
- p = 0.0007 は事前設定の α=0.05 を大幅に下回る
- KG multi-op が生成する仮説は、後続文献で検証対象となる割合が C_rand_v2 より有意に高い

ただし注意点:
- これは **事前に primary endpoint として設定していなかった**指標である（副次的評価基準）
- N=50 での単一実験結果であり、再現確認が必要
- 過大評価せず「有望な副次結果」として扱う

---

## 4. 価値軸のずれ

run_017 が明らかにしたこと:

| 軸 | KG multi-op (C2) | ランダム (C_rand_v2) | 優勢 |
|----|-----------------|----------------------|------|
| supported novelty | 0.130 | 0.219 | C_rand_v2 |
| investigability | 0.920 | 0.640 | **C2** |

この「価値軸のずれ」は重要な発見である:
- **C2 は novel supported hypothesis generator としては現時点で支持されない**
- **C2 は investigable hypothesis generator としては有望な可能性がある**

言い換えると、KG multi-op が生成する仮説は「新規に支持された知見」ではなく「後続研究が実施される価値のある問い」を多く含む傾向がある。

---

## 5. run_016 NO-GO との違い

| セッション | NO-GO 理由 | 状態 |
|-----------|-----------|------|
| run_016 (Session #67) | C_rand v1 の baseline 設計不備（trivially-known ペアが混入） → 評価自体が不成立 | **評価保留 → 解決済み** |
| run_017 (Session #68) | C_rand v2 による適切な baseline での正式な検定 → SC-1r FAIL | **正式な不支持** |

run_016 の NO-GO は「測定できなかった」ことを意味する。  
run_017 の NO-GO は「測定した結果、primary endpoint での優位性がなかった」ことを意味する。  
両者は本質的に異なる。run_017 の結果のみが有効な検定結果である。

---

## 6. Scientific Hypothesis 検証 Close 宣言

**本文書をもって、scientific hypothesis MVP (run_015〜017) の検証を正式に close する。**

| 項目 | 結論 |
|------|------|
| 主解析 (SC-1r) | **NO-GO** — C2 は C_rand_v2 に対して novel_supported_rate で有意差なし |
| 副次結果 (SC-3r) | **有望** — C2 は investigability で有意な優位性あり (p=0.0007)、再現確認要 |
| Close 理由 | Primary endpoint (SC-1r) で有意差なし。現行の実験設計での検証は完了 |

**次の検証フェーズへの移行条件**:
- investigability を primary endpoint とした新仮説 (H_inv) の pre-registration
- N≥200 での再現実験
- known_fact threshold sensitivity analysis (exploratory)

---

## 7. 検証の進化経路

```
trading alpha 検証（run_001〜014）
    ↓ 転換
scientific hypothesis 検証（run_015〜017）
    ├── SC-1r (supported novelty): FAIL → close
    └── SC-3r (investigability): PASS → 新仮説 H_inv へ継続
```

当初は「KG が novel かつ supported な仮説を生成できるか」を問うていた。  
run_017 の結果は「supported novelty」という軸での優位性を否定しつつ、  
「investigability」という新たな価値軸の可能性を示した。  
次フェーズでは investigability を主軸とした検証へ移行する。
