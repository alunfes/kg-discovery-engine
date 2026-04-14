# 次の研究方向 — Density-Aware Pair Selection

作成日: 2026-04-14

---

## 問いの転換

| | 問い | 状態 |
|--|------|------|
| 旧 | How to improve KG operator? | 不毛と判明（run_020 NO-GO） |
| 新 | How to select density-aware cross-domain pairs? | 次の本丸 |

run_021 の結論: C2 の investigability 問題は operator の品質ではなく、literature-density asymmetry が規定している。operator tuning を続けることは非生産的であり、pair selection の設計に移行する。

---

## 次の主仮説

### H_density_select

> density-aware cross-domain pair selection を導入すると、C2 の investigability が C1 と統計的に同等になる。

**具体的な実装:**
- compose パス探索時に、`min_density` が閾値以上のペアのみを候補にする
- 閾値は run_021 の四分位分析から設定（Q2 以上 ≈ `min_density ≥ 1,000` 程度）
- 閾値を下回るペアは compose の候補から除外する

**成功基準:**
- C2_density_aware の investigability ≥ C1 の investigability（統計的有意差なし）
- Fisher exact test p > 0.05（帰無仮説: C2_density_aware = C1 を棄却できない）

---

### H_matched_parity

> matched density / novelty 条件下で、C2 と C1 の investigability に統計的有意差はない。

**根拠:** run_021 matched comparison において、`den_mid` および `den_high` 群では C1≈C2（gap ≈ 0）。density を統制すれば C2 の investigability 劣位は消える。

**成功基準:**
- matched 条件での C1 vs C2 investigability 差 ≤ 0.02
- Fisher exact test p > 0.05

---

## 実験計画案（run_022）

### フェーズ 1: density-aware filter の実装

1. `src/scientific_hypothesis/density_aware_compose.py` を新規作成
2. compose オペレータ内に density フィルタを追加
   - 入力: entity pair (A, B)
   - フィルタ条件: `min(density_A, density_B) ≥ threshold`
   - threshold = Q2 from run_021 ≈ 1,000
3. `runs/run_021_density_ceiling/density_scores.json` の density 情報を参照

### フェーズ 2: C2_density_aware vs C1 の比較

| 条件 | 設定 |
|------|------|
| C1 (baseline) | single-op bio-only（run_018 設定を流用） |
| C2_density_aware | multi-op、density filter 適用 |
| N | 70（SC-3r と同一サイズ） |
| ラベリング | investigability ラベリングプロトコル準拠 |

### フェーズ 3: matched comparison の再確認

- density / novelty を統制した matched comparison で gap ≤ 0.02 を確認
- density bin ごとの breakdown も記録

---

## やらないこと

| 項目 | 理由 |
|------|------|
| operator tuning の延命 | run_020 で NO-GO 確定。追加投資は非生産的 |
| SC-1r 救済 | supported novelty は KG の強みを測る指標として不適切と判断 |
| 別ドメインへの早期移行 | まず bio × chem で density-aware の効果を確認してから |
| threshold の過度な最適化 | Q2 を基準に固定し、最初の実験は1点で実施 |

---

## 長期的な意味

density-aware pair selection が成功した場合、以下の成果が得られる:

1. **KG の「使い方ガイド」の確立**
   - どの density 条件で KG が有効かを定量的に示せる
   - 「KG が使えるドメインペア」の予測モデルの基礎になる

2. **applicability boundary の定量化**
   - KG Discovery Engine が有効な条件を `min_density ≥ threshold` として形式化
   - 新しいドメインペアへの適用可能性を事前に判断できる

3. **研究コミュニティへの示唆**
   - KG ベースの仮説生成において、文献密度が investigability の律速因子であることを示す
   - 知識グラフの「密度の非対称性」という新しい評価軸の提案

---

## 優先度

| 優先度 | タスク |
|--------|--------|
| P1 | density-aware pair selection の実装 + 実験（run_022） |
| P1 | H_matched_parity の検証 |
| P2 | density threshold の最適化（Q1/Q2/Q3 の比較） |
| P3 | 別ドメインへの展開（density-aware が成功した後） |

---

---

## 次フェーズ案（run_023 確定後）

### P2-A: low-density regime の失敗機構の特定

Q1 における C2 の investigability 低下 (delta=-0.235) の具体的原因を分析する。

**問い:**
- なぜ low-density cross-domain ペアで investigability が落ちるのか
- 文献が少ないこと自体が原因なのか（エビデンス不在）、それとも仮説の質が下がるのか（KG が貧弱な繋ぎ方をする）

**アプローチ:**
- Q1 の C2 仮説を個別に精査し、investigability=0 の原因をカテゴリ分類
- 「文献なし」 vs 「文献はあるが仮説が無効」 の比率を計測

---

### P2-B: density-aware selection を discovery engine の標準設計に昇格（推奨）

density-aware pair selection は「C2 救済策」ではなく、**探索系評価における selection design law の発見**として位置付ける。

**実装方針:**
- `min_density` threshold (~7500–8100) を compose パイプラインの標準パラメータにする
- applicability boundary の定量化: 「KG が有効な domain pair の条件」を `min_density ≥ threshold` として形式化
- 新しいドメインペアへの適用可能性を事前に判断できるスコアリングを設計

**意義:**
- 単なる「フィルタ追加」ではなく、KG Discovery Engine の適用条件を定義する設計原則
- 別ドメイン展開時のデフォルト設計として採用可能
- 「density が十分な条件でのみ KG を使う」という知見の実装形態

**優先度: P2-B を推奨** — P2-A よりも直接的な設計インパクトがあり、次フェーズの基盤になる。

---

## 参照文書

- `docs/scientific_hypothesis/final_interpretation_v2.md` — 検証系列の総括
- `docs/scientific_hypothesis/density_ceiling_results.md` — run_021 詳細結果
- `docs/scientific_hypothesis/density_causal_conclusion.md` — run_023 因果検証結論
- `runs/run_021_density_ceiling/quartile_analysis.json` — density 四分位データ
- `runs/run_021_density_ceiling/matched_comparison.json` — matched comparison 結果
- `runs/run_023_density_causal_verification/regression_results.json` — 回帰分析結果
