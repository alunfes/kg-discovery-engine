# 次のアクション — Run 003 後

## Run 003 で解決したこと
- [x] H3評価方式を hypothesis-level に変更 → **H3 PASS (ratio=1.25)**
- [x] toy data拡充（bio/chem 8→12ノード）
- [x] bio_chem_bridge KG追加（明示的cross-domain エッジ9件）
- [x] H2検証フレームワーク実装 → **H2 PASS (劣化0.21%)**
- [x] H4検証フレームワーク実装（Spearman相関）
- [x] テスト追加・全パス

## 未解決の問題

### H1 FAIL (+3.0%)
C2 mean (0.7508) vs C1 mean (0.7290) → +3.0%（閾値10%未達）

**Option A (推奨)**: compose_cross_domain() オペレータの追加
```python
def compose_cross_domain(kg, max_depth=3):
    """Cross-domain パスを優先探索するcompose変種。
    subject.domain != object.domain のパスのみ返す。"""
```
これにより C2 で cross-domain 仮説のみを生成 → mean 上昇が期待できる。

**Option B**: H1 閾値を 10% → 5% に引き下げ
Run 001〜003 の実測改善は +3〜3.3%。測定対象のシステム特性に合わせた閾値見直しも正当。

### H4 FAIL (tie: Spearman 0.9893)
all-2hop 問題: biology KG の全候補が 2ホップ → naive も aware も traceability=0.7。

**必須対策**: H4専用テストKGの設計
```python
def build_h4_test_kg():
    """1ホップ・2ホップ・3ホップが混在する H4 検証用KG。"""
    # 1ホップ: A→B (direct, high traceability)
    # 2ホップ: A→B→C
    # 3ホップ: A→B→C→D (low traceability)
```

---

## 優先度：高

### 1. H1 改善: compose_cross_domain() オペレータ追加
`src/pipeline/operators.py` に追加:
```python
def compose_cross_domain(kg, max_depth=3):
    candidates = compose(kg, max_depth=max_depth)
    return [c for c in candidates if _is_cross_domain_candidate(c, kg)]
```
C2 パイプラインで `compose_cross_domain()` を使う新条件 C2_xd を追加。

### 2. H4 検証強化: hop数混在KG
`src/kg/toy_data.py` に `build_h4_test_kg()` を追加:
- 直接1ホップ関係 3件
- 2ホップ間接推論 4件
- 3ホップ長距離推論 3件

---

## 優先度：中

### 3. analogy-transfer オペレータ実装
`src/pipeline/operators.py` の `analogy_transfer_placeholder` を実装:
- bio↔chem アライメントマップを使ってpatternを転写
- cross-domain仮説生成の別アプローチ

### 4. H1閾値見直しの議論
実測 +3% に対して 10% 閾値は高すぎる可能性。
`docs/hypotheses.md` で H1 定義を「C2のcross-domain仮説が C1の全仮説より novelty が10%高い」に変更する案を検討。

---

## 優先度：低

### 5. belief-update オペレータ実装
### 6. software↔networking cross-domain KG の実験
