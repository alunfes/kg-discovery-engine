# Scientific Hypothesis 検証 v1 — 最終結論

**作成日**: 2026-04-14  
**対象実験**: run_017 (N=50) + run_018 (N=70)  
**ステータス**: CLOSED

---

## 正式結論

### SC-1r (novel_supported_rate): FAIL 確定

KG multi-op (C2) が random baseline (C_rand) より高い novel_supported_rate を持つという仮説は、**2回の検証で支持されなかった**。

| 実験 | C2 | C_rand | p値 |
|------|-----|--------|-----|
| run_017 (N=50) | 0.130 | 0.219 | 0.91 |

run_018 では SC-1r は評価対象外（pre-registration 通り）。

**結論**: KG multi-op は "supported novelty generator" ではない。

---

### SC-3r (investigability_rate): 再現確認済み (GO)

KG multi-op (C2) が random baseline (C_rand) より高い investigability_rate を持つという仮説は、**2回の検証で一貫して支持された**。

| 実験 | C2 | C_rand | 判定 |
|------|-----|--------|------|
| run_017 (N=50) | 0.920 | 0.640 | PASS (p=0.0007) |
| run_018 (N=70) | 0.914 | 0.600 | PASS (p<0.05) |

ただし、**single-op (C1 bio-only: 0.971) に対する優位は確認されなかった**。C1 > C2 という副次発見がある。

**結論**: KG multi-op は random baseline より investigable な仮説を生成する。しかし bio-only single-op を上回るとは言えない。

---

## 検証の進化経路

```
[段階1] Trading alpha / meta-filter 仮説
        → 支持されなかった (1/14 Hard No-Go)
        → KG が trading シグナルを生成するという主張は棄却

[段階2] Scientific hypothesis: supported novelty (SC-1r)
        → 支持されなかった (FAIL, p=0.91)
        → KG multi-op は "正しい新規仮説" を当てる能力はない

[段階3] Scientific hypothesis: investigability (SC-3r)
        → 支持された (PASS, 2回再現)
        → KG multi-op は "検証可能な仮説" を生成する能力がある
```

---

## 何が支持され、何が支持されなかったか

| 主張 | 判定 | 根拠 |
|------|------|------|
| KG multi-op > random baseline (investigability) | **支持** | run_017 p=0.0007, run_018 p<0.05 |
| KG multi-op > random baseline (supported novelty) | **不支持** | run_017 p=0.91, C2 < C_rand |
| KG multi-op > single-op (investigability) | **不支持** | C1=0.971 > C2=0.914 (run_018) |
| cross-domain 仮説の新規性と investigability のトレードオフ | **未検証** | 次の研究問いとして継続 |

---

## 現在の位置付け

KG multi-op は **"investigable hypothesis generator"** として位置付ける。

- random に対して: investigability で優位 (確立済み)
- single-op に対して: investigability で優位なし (現時点では C1 > C2)
- "supported novelty" の生成: 未支持

この位置付けは、SC-1r FAIL の事実を変えるものではなく、SC-3r の再現という独立した発見に基づく。

---

## 注記

- SC-3r 仮説は run_017 の事後分析から導出された (post-hoc)
- run_018 は investigability を primary endpoint として事前登録し、確認的検証を行った
- したがって run_018 の結果は confirmatory として扱う
- この文書は結論を盛らないことを方針とする
