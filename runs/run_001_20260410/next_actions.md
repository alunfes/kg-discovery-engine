# 次のアクション — Run 001 後

## 優先度：高

### 1. スコアリング改善（H1・H3検証のブロッカー）

**問題**: 現行スコアリングが単調で仮説間の質的差異を捉えられない

**改善案A**: 仮説のエッジのrelation種別を評価に組み込む
- inhibits/activates = functional relation → plausibility高
- "associated_with" = weak relation → plausibility低

**改善案B**: cross-domain パスの検出を明示的に実装
- provenanceパス上でdomainが切り替わっているか確認
- cross-domain パス = novelty ボーナス付与

**実装場所**: `src/eval/scorer.py` の `_score_novelty`, `_score_plausibility`

### 2. アライメントの改善

**問題**: 文字列Jaccardで "enzyme" ↔ "catalyst" が対応付けられない

**改善案**: ドメイン知識ベースの辞書マッピングを追加
```python
DOMAIN_SYNONYMS = {
    "enzyme": ["catalyst", "facilitator"],
    "inhibit": ["block", "suppress"],
    "protein": ["compound", "molecule"],
}
```
これにより概念的アナロジーを介したcross-domain alignが可能になる。

**実装場所**: `src/pipeline/operators.py` の `align` 関数

---

## 優先度：中

### 3. Run 002設計：スコアリング改善版での再検証

- 改善後のスコアラーでH1・H3を再検証
- biology + chemistry + software の3ドメインに拡張
- cross-domain vs same-domain の対比を明確化

### 4. H2検証の設計

- 「低品質KG」の定義：ランダムにエッジを削除（欠損率 30%/50%）
- 「詳細評価」vs「簡易評価」の設定方法を決定

### 5. H4検証の設計

- provenance_aware=True の実装強化
- Gold-standard ranking の定義（手動で10件の正解順位を設定）

---

## 優先度：低

### 6. analogy-transfer の実装（v1以降）

provenanceで取得したパターンをcross-domain転写する。
現状はplaceholderのみ。

### 7. belief-update の実装（v1以降）

新エビデンス追加時に既存仮説スコアを更新する機構。
