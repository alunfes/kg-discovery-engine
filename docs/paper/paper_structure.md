# Paper Structure — KG Discovery Engine
*Fixed 2026-04-15 | One-line summary: "Long-path discovery is not inherently blocked by a novelty ceiling; it becomes viable in a domain-agnostic manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection."*

---

## Section 1: Introduction

**唯一の目的**: novelty ceiling という先入観を問い直し、問題の重要性と本研究の位置づけを確立する。

**置く図表**:
- 主図: なし
- 補助: なし

**読者に理解してほしいこと**: 長パスの biomedical KG discovery は investigability が低くなると広く信じられてきたが、その原因は path length 自体にあるのではなく、選択戦略の設計にある。本研究はこの前提を実験的に覆す。

**次節へのつながり**: では何が ceiling を生み出し、何が ceiling を破るのか — その着想を次節で提示する。

---

## Section 2: Core Idea (Approach)

**唯一の目的**: bridge geometry + endpoint-aware selection という 2 層の解決策が ceiling を破れるという着想と、その 4 条件設計原理を 1 ページで固定する。

**置く図表**:
- 主図: なし（または 4 conditions の概念ダイアグラム — 未確定）
- 補助: **4 Conditions 表**（構造層 / 選択層の役割分担を示す）

**読者に理解してほしいこと**: ① bridge 構造（bio→chem→bio 多ドメイン交差パス） ② 高 cross_domain_ratio（cdr_L3 ≥ 0.60） ③ 直近文献カバレッジ（2024-2025 endpoint pair 論文） ④ endpoint-aware selection（pre-filter）の 4 条件が揃って初めて ceiling が消える。条件 1-2 は KG 構築層、条件 3-4 は ranking 選択層であり、どちらの層も単独では不十分である。

**次節へのつながり**: この着想を実装した技術（R3 ranker, T3 bucketed selection, pre-filter）と実験設計を Method で具体化する。

---

## Section 3: Method

**唯一の目的**: R3 / T3 / pre-filter の技術仕様と、P4→P10-A の実験を 3 claims の証拠系譜として整理する（全実験を均等には扱わない）。

**置く図表**:
- 主図: なし（技術仕様はアルゴリズム / 数式で示す）
- 補助: **実験設計表**（Phase × Run × 対応 Claim × 役割 の早見表）

**読者に理解してほしいこと**: R3 は `0.4 × structure_norm + 0.6 × evidence_norm` の hybrid ranker で B2 の基礎となる。T3 は L2:L3:L4+ = 50%:29%:21% のバケット選択で長パス多様性を保証する。pre-filter は `0.50 × recent_validation_density + ...` の 4 成分スコアで endpoint-pair の 2024-2025 PubMed 信号を組み込む。P4 は baseline 確立 (B2)、P7/P8 は C1 の証拠、P9/P10-A は C2/C3 の証拠として機能する — P5/P6-A は ceiling の発見として位置づける。

**次節へのつながり**: この設計が 3 つの claim ごとに何を示したかを Results の 3 節で順に示す。

---

## Section 4: Results

### 4.1 C1: Bridge Geometry Removes the Novelty Ceiling

**唯一の目的**: P6-A での ceiling 発見と P7 breakthrough の対比により、geometry 増強が investigability ceiling を解除することを実証する。

**置く図表**:
- **主図 (Fig 1)** [新規]: P6-A vs P7 vs P8 の cdr_L3 と investigability の 2 指標比較バーチャート — 詳細は `docs/paper/figure_table_list.md` §Fig 1
- **補助 (Table 1)** [新規]: 実験条件別 geometry + investigability メトリクス一覧（cdr_L3, T3 inv, B2 gap、ROS/NT family での再現確認）

**読者に理解してほしいこと**: cdr_L3 が 0.333（P6-A）→ 0.619（P7）→ 0.740（P8）と増加するにつれ investigability が B2 baseline (0.9714) を超える。bridge geometry の増強が ceiling 突破の直接原因であり、ROS ファミリーのいずれのサブセットでも再現される。

**次節へのつながり**: この geometry breakthrough が特定の化学ファミリー（ROS）に依存しないか — NT ファミリーへの転移可能性を C2 で検証する。

---

### 4.2 C2: The Mechanism Is Domain-Agnostic

**唯一の目的**: P9 の GEOMETRY_ONLY 判定が selection artifact であったことを示し、P10-A の T3+pf が NT ファミリーでも STRONG_SUCCESS を達成することで DOMAIN_AGNOSTIC を確立する。

**置く図表**:
- **主図 (Fig 2)** [新規]: ROS ファミリー（P8）と NT ファミリー（P9 T3 vs P10-A T3+pf）の investigability 比較 — GEOMETRY_ONLY → DOMAIN_AGNOSTIC の転換を可視化。詳細は `docs/paper/figure_table_list.md` §Fig 2
- **補助 (Table 2)** [新規]: ROS (P8) / NT-T3 (P9) / NT-T3+pf (P10-A) の geometry メトリクス + investigability 対応表（family transfer score 表）

**読者に理解してほしいこと**: NT ファミリーは geometry (cdr_L3=0.605, P7 比 97.7%) を再現するが、T3 では investigability が下がる (0.8571)。pre-filter を加えると investigability = 1.000 となり ROS と同等の STRONG_SUCCESS になる。P9 の失敗は T3 の edge-level e_score_min が endpoint-level investigability の proxy として不十分だったことに起因する selection artifact だった。

**次節へのつながり**: geometry が同一でなぜ T3 と T3+pf で結果が逆転するのか — pre-filter の機序と必要性を C3 で定量的に示す。

---

### 4.3 C3: Endpoint-Aware Pre-Filter Is Required

**唯一の目的**: B2–T3 gap の逆転（−0.114 → +0.029）を定量的に確立し、pre-filter が geometry を usable discovery に変換する必要十分な selection 層であることを示す。

**置く図表**:
- **主図 (Fig 3)** [既存: `docs/figures/fig1_p10a_comparison.png`]: B2 / T3 / T3+pf の 3 条件バーチャート（investigability / novelty_retention / long_path_share）
- **補助 (Table 3)** [新規]: B2–T3 gap → B2–T3+pf gap の逆転表 + bucket 別 survival rate（L2: 57.1%, L3: 5.0%, L4+: 0.0%）

**読者に理解してほしいこと**: T3+pf は T3 と同一 geometry (cdr_L3=0.605) を持ちながら investigability で B2 を 2.9pp 上回る（1.000 vs 0.9714）。この逆転は pre-filter が L3 バケットを 95%、L4+ バケットを 100% 置き換え、endpoint-level 2024-2025 PubMed 信号を primary signal (weight 0.50) として使うことで達成される。特に serotonin は T3 で 0 パスに抑圧されていたが T3+pf では 15 パスが全て investigated として選択された。

**次節へのつながり**: 3 claims の組み合わせが何を意味するか、一般化の射程と限界を Discussion で論じる。

---

## Section 5: Discussion

**唯一の目的**: 各 claim の含意（何が分かったか / 何が誤解だったか / どこまで一般化できるか）を論じ、特に P9 negative が artifact だった理由を分析する。

**置く図表**:
- 主図: なし（Results の図を参照）
- 補助: なし

**読者に理解してほしいこと**: novelty ceiling は構造的制約ではなく selection strategy の問題だった (C1)。NT ファミリーでの P9 failure は、T3 が edge-level co-occurrence を使うのに対し investigability は endpoint-level 信号であるという signal mismatch に起因する artifact だった (C2)。設計原理の geometry 層（条件 1-2）と selection 層（条件 3-4）は独立して必要であり、片方だけでは STRONG_SUCCESS は達成されない (C3)。これらの知見は PubMed カバレッジがある任意のドメインに理論的に適用可能だが、cold-start robustness（P11-A）と統計的有意性（P11-D, N=200）の検証が残る。

**次節へのつながり**: 本研究にはいくつかの重要な制約があり、それを正直に示す。

---

## Section 6: Limitations

**唯一の目的**: 本研究の適用範囲と未検証の前提を列挙し、読者が結果を適切にスコープできるようにする。

**置く図表**:
- 主図: なし
- 補助: なし

**読者に理解してほしいこと**:
1. **文献依存**: pre-filter は PubMed 2024-2025 カバレッジに依存する。sparse-frontier ドメインでは proxy scoring しか使えない。
2. **family 選択の事前知識依存**: ROS/NT という well-characterized ファミリーを選んだ。frontier family（2024-2025 論文が少ない）への適用は未検証。
3. **KG 構築コスト**: bridge node の多ドメイン交差構造を作るには domain knowledge が必要。自動化の方法は未確立。
4. **N=70 のサンプルサイズ**: 各条件 70 パスの比較は統計的有意性の正式検定には不十分（P11-D で N=200 を計画）。

**次節へのつながり**: 以上の制約のもとで、本研究が確立する貢献を Conclusion として固定する。

---

## Section 7: Conclusion

**唯一の目的**: 3 claims を one-sentence に凝縮し、本研究の貢献を確立する。

**置く図表**:
- 主図: なし
- 補助: なし

**読者に理解してほしいこと**: Long-path discovery は novelty ceiling によって本質的に阻まれるわけではない。semantically enriched bridge geometry（conditions 1-2）と endpoint-aware selection（conditions 3-4）を組み合わせることで、domain-agnostic な STRONG_SUCCESS が達成される。

**One-sentence summary**:
> Long-path discovery is not inherently blocked by a novelty ceiling; it becomes viable in a domain-agnostic manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection.

---

## 図表割り当て一覧

| 図表 | Section | 対応 Claim | 種別 | 状態 |
|------|---------|-----------|------|------|
| Fig 1 | 4.1 | C1 | 主図 | **新規作成が必要** |
| Table 1 | 4.1 | C1 | 補助表 | 新規（データあり） |
| Fig 2 | 4.2 | C2 | 主図 | **新規作成が必要** |
| Table 2 | 4.2 | C2 | 補助表 | 新規（データあり） |
| Fig 3 | 4.3 | C3 | 主図 | 既存: `docs/figures/fig1_p10a_comparison.png` |
| Table 3 | 4.3 | C3 | 補助表 | 新規（データあり） |
