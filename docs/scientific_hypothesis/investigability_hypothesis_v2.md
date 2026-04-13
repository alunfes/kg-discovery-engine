# Investigability 仮説 v2 — 新主仮説定義

**作成日**: 2026-04-14  
**Status**: DRAFT — pre-registration 未実施  
**導出元**: run_017 SC-3r (p=0.0007)

---

## 1. 動機

run_017 の副次評価基準 SC-3r において、KG multi-op (C2) の investigability が
C_rand_v2 に対して有意に高いことが確認された (C2=0.920 vs C_rand_v2=0.640, p=0.0007)。

この結果は事前に primary endpoint として設定していなかったため、
run_017 の主解析結論 (NO-GO) を変えるものではない。しかし、
investigability を主軸とした新たな検証フェーズの根拠として採用する。

---

## 2. 仮説定義

### 帰無仮説 (H0_inv)

> KG multi-op は random sampling (C_rand_v2) より investigable hypothesis を多く生成しない

### 対立仮説 (H1_inv)

> KG multi-op は random sampling (C_rand_v2) より investigable hypothesis を多く生成する

**検定方向**: 片側 (C2 > C_rand_v2)  
**有意水準**: α = 0.05  
**検定手法**: Fisher's exact test (one-sided)

---

## 3. 用語定義

### Investigable hypothesis

後続文献で検証対象となった仮説。具体的には二層ラベリングにおいて
`not_investigated` 以外のラベルを得た仮説。

**ラベル分類**:

| ラベル | Investigable | 説明 |
|--------|-------------|------|
| supported | YES | 後続文献で支持された |
| refuted | YES | 後続文献で否定された |
| plausible | YES | 後続文献で言及・部分支持 |
| not_investigated | NO | 文献で検討されていない |

### Investigability rate

```
investigability_rate = investigated_count / total_count
```

ここで `investigated_count = supported + refuted + plausible`

---

## 4. 評価方法

| 項目 | 設定 |
|------|------|
| Primary endpoint | investigability_rate C2 vs C_rand_v2 |
| N (目標) | ≥ 200 per method |
| Baseline | C_rand_v2 (run_017 と同設計) |
| ラベリング | 二層ラベリング (Layer 1 + Layer 2) |
| 検定 | Fisher's exact test (one-sided, p<0.05) |

---

## 5. N 増加の目的

N≥200 での実験は **SC-1r の救済ではない**。

run_017 で SC-1r (novel_supported_rate) が FAIL した事実は変わらない。
N を増加させても SC-1r の検証を再試行しない。

N 増加の目的は以下に限定する:

1. **SC-3r の再現確認** — N=50 での単一実験結果 (p=0.0007) が N=200 でも維持されるか確認
2. **効果量の推定精度向上** — C2 と C_rand_v2 の investigability 差 (+0.280) の信頼区間を縮小
3. **新 primary endpoint での検定** — H_inv を適切なサンプルサイズで検証

---

## 6. 成功基準

| 基準 | 内容 |
|------|------|
| Primary | C2 investigability_rate > C_rand_v2、Fisher's exact p < 0.05 |
| Secondary | 効果量 (差) ≥ 0.15 (run_017 の 0.280 の半分以上を再現) |
| Failure | p ≥ 0.05、またはC2 ≤ C_rand_v2 |

Failure 時は investigability 仮説も棄却する。次フェーズは設けない。

---

## 7. Pre-registration の必要性

**本仮説は実験前に pre-registration を行うことを必須とする。**

pre-registration に含める内容:
- H0_inv / H1_inv の定義
- 検定手法・有意水準
- N (サンプルサイズ) の事前決定
- 解析対象の指定 (investigability_rate のみ、SC-1r は含まない)
- commit hash による実験設定の固定

pre-registration なしでの実験開始は禁止する。
run_017 SC-3r を起点とした HARKing (Hypothesizing After Results are Known) を防ぐため。

---

## 8. 検証の進化経路

```
Phase 1: trading alpha 検証（run_001〜014）
    → 市場予測精度での KG 優位性を検証
    → FAIL / 打ち切り

Phase 2: scientific hypothesis 検証（run_015〜017）
    → H1: "KG multi-op は novel supported hypothesis を生成する"
    → Primary endpoint (SC-1r): FAIL
    → 副次発見: investigability (SC-3r) PASS (p=0.0007)

Phase 3: investigability 仮説検証（計画中）
    → H1_inv: "KG multi-op は investigable hypothesis を多く生成する"
    → Pre-registration → N≥200 実験 → 結論
```

各フェーズで「証明したいこと」が変化してきた。これは科学的誠実さの観点から
適切な探索プロセスであるが、各フェーズの区切りを明確に記録する責任がある。

---

## 9. 注意事項

- run_017 SC-3r の結果はあくまでも探索的な発見である
- H_inv が棄却された場合、さらなる仮説に移行しない
- investigability そのものが「良い」指標かどうかも別途評価が必要
  （investigability が高い = 研究者にとって価値のある問いかどうかは未検証）
