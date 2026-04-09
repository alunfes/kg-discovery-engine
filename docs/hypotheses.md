# 仮説定義 (H1-H4)

## H1: Multi-operator Pipeline優位性

**仮説**: multi-operator KG pipelineはsingle-operator methodsより有用な仮説を生成する

### 詳細

単一オペレータ（compose-only または difference-only）では、KGの局所的な構造変換のみを行う。
multi-op pipeline（align → union → compose → difference → evaluate）では、異なる変換を連鎖させることで、単独では発見できない仮説が生まれることを期待する。

### 検証方法

- C1（single-op）vs C2（multi-op）で同一入力KGを使用
- plausibility + novelty の加重平均でスコア比較
- 5試行の平均で評価（決定論的実装のため1試行でも再現可能）

### 合格基準

- C2のmean score ≥ C1のmean score × 1.10

### ステータス

`[ ] 未検証`

---

## H2: 評価レイヤー強化の優先性

**仮説**: 入力KGの完璧化よりも下流の評価レイヤーの強化が重要

### 詳細

入力KGにノイズ・欠損があっても、下流の評価（plausibility/traceability/evidence support）が優れていれば、
高品質な仮説候補を選別できる。逆に、入力KGが完璧でも評価が粗雑では出力品質が下がる。

### 検証方法

- 高品質KG × 簡易評価 vs 低品質KG × 詳細評価 の比較
- 最終ランキングの正解順位との相関で評価

### 合格基準

- 低品質KG × 詳細評価のNDCG ≥ 高品質KG × 簡易評価のNDCG

### ステータス

`[ ] 未検証`

---

## H3: Cross-domain新規性優位性

**仮説**: cross-domain KG操作はsame-domain操作より新規性の高い仮説を生成する

### 詳細

同一ドメイン内のKG操作（biology × biology）は既知の知識の再組み合わせに留まる。
異なるドメインのKGを組み合わせる（biology × chemistry）と、構造的アナロジーから
新規性の高い仮説が生まれやすい。

### 検証方法

- same-domain pair（biology+biology、software+software）
- cross-domain pair（biology+chemistry、software+networking）
- noveltyスコアの中央値比較

### 合格基準

- cross-domain novelty median ≥ same-domain novelty median × 1.20

### ステータス

`[ ] 未検証`

---

## H4: Provenance-aware評価の優位性

**仮説**: provenance-aware evaluationは仮説ランキングの品質を向上させる

### 詳細

仮説の出所（どのオペレータがどのノードから生成したか）を評価スコアに組み込むことで、
トレーサビリティの低い仮説（多段変換で根拠が薄くなったもの）を適切に降格できる。

### 検証方法

- naive評価（provenanceを無視）vs provenance-aware評価 の比較
- traceabilityスコアをprovenance depthに基づいて調整
- 人手によるgold-standard rankingとの相関（Kendall's τ）

### 合格基準

- provenance-aware: Kendall's τ ≥ naive + 0.10

### ステータス

`[ ] 未検証`

---

## 検証ロードマップ

```
Run 001 → H1 予備検証（C1 vs C2 基本比較）
Run 002 → H1 確認 + H3 検証（cross vs same domain）
Run 003 → H2 検証（評価レイヤー品質の影響）
Run 004 → H4 検証（provenance-aware vs naive）
Run 005 → 総合検証・統計的有意性確認
```
