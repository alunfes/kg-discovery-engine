# LaTeX Conversion Notes — KG Discovery Engine Paper

**Date**: 2026-04-10  
**Converted from**: docs/paper_skeleton.md + all source-of-truth documents  
**Target**: paper/ directory (main.tex + sections/ + tables/ + figures/)

---

## 変換方針

### ソース優先度

1. `docs/paper_claims.md` → 3 core claims の precise statements (絶対変えない)
2. `docs/paper_skeleton.md` → 各セクションのドラフト文章 (LaTeXに移植)
3. `docs/method_summary.md` → Method 節の技術詳細
4. `docs/threats_to_validity.md` → Threats 節 (T1-T5 全移植)
5. `docs/case_study_notes.md` → Case Studies 節 (全文移植)
6. `docs/relation_semantics_audit.md` → Table 3 + Discussion のコア論点
7. `paper_assets/final_metrics.json` → Table 1 数値
8. `paper_assets/subset_summary_table.csv` → Table 2 数値
9. `paper_assets/candidate_validation_table.csv` → Table 4
10. `paper_assets/relation_semantics_table.csv` → Table 3 (代表行のみ)

### 保守的言い回しの徹底

- Case studies: 各候補を positive control / weakly novel / artifact risk に明示分類
- "discovered" → "identified as hypothesis candidates"
- "mechanistic hypotheses" → "structurally generated cross-domain connections with variable mechanistic interpretability"
- A-1 は必ず positive control として説明 (novelty主張しない)
- conditional claims はconditionalのまま

---

## ファイル構成

```
paper/
├── main.tex                     ← 全セクションを \input で包含
├── references.bib               ← プレースホルダ (TODO- prefix)
├── sections/
│   ├── 00_abstract.tex
│   ├── 01_introduction.tex
│   ├── 02_related_work.tex
│   ├── 03_method.tex            ← Figure 1 (pipeline) 配置
│   ├── 04_experimental_setup.tex
│   ├── 05_results.tex           ← Figure 2,3,4 + Table 1,2 配置
│   ├── 06_case_studies.tex      ← Table 4 参照
│   ├── 07_discussion.tex        ← Table 3 + relation semantics audit
│   ├── 08_threats_to_validity.tex
│   ├── 09_limitations.tex
│   └── 10_conclusion.tex
├── tables/
│   ├── table1_hypothesis_status.tex
│   ├── table2_subset_comparison.tex
│   ├── table3_relation_semantics.tex
│   └── table4_candidate_summary.tex
└── figures/                     ← symlinks to paper_assets/figures/
    ├── figure1_pipeline.png
    ├── figure2_alignment_leverage.png
    ├── figure3_drift_by_depth.png
    └── figure4_filter_effect.png
```

---

## コンパイル可否

### 環境メモ

**この環境では pdflatex 未インストール**のためコンパイル未実施。
TeX Live または MacTeX をインストールしてから以下のコマンドで実行できる。

### 必要パッケージ

```
article (standard)
geometry
graphicx
booktabs
hyperref
amsmath
amssymb
microtype
enumitem
xcolor
tabularx
multirow
url
natbib
```

### コンパイルコマンド

```bash
cd paper/
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

### 既知の残存 issue (2026-04-10 時点)

| Priority | Issue | 対処 |
|----------|-------|------|
| HIGH | `.claire/` に誤ったファイルを作成 → 削除必要 | `rm -rf /Users/alun/claude-dev/kg-discovery-engine/.claire/` |
| HIGH | `references.bib` 全エントリが TODO- プレースホルダ | 各引用を人間が手動検証・補完 |
| MEDIUM | Figure サイズ未調整 (width=0.88/0.92 は暫定) | 実際の図の縦横比に合わせて調整 |
| MEDIUM | `tabularx` での列幅調整が必要な場合あり | コンパイル後に目視確認 |
| MEDIUM | `\cite{TODO-*}` が bibtex 未解決警告を生成 | 引用補完後に解消 |
| LOW | Abstract に repository URL プレースホルダあり | 実URL追加 |
| LOW | Author/Institution プレースホルダあり | 実名追加 |
| LOW | 各セクションの文体磨き未実施 | 人間レビュー後 |

---

## TODO リスト（人間が手直しすべき項目）

### 引用 (最優先)

- [ ] TransE (Bordes et al. 2013 NeurIPS) — volume/page 確認
- [ ] RotatE (Sun et al. 2019 ICLR) — 確認
- [ ] ComplEx (Trouillon et al. 2016 ICML) — 確認
- [ ] Entity alignment survey — 具体的な論文特定 (Zhu et al. 2017? Sun et al. 2020?)
- [ ] Schema alignment / ontology matching — Euzenat & Shvaiko 2007?
- [ ] SemMedDB (Kilicoglu et al. 2012) — volume/page/DOI 確認
- [ ] PREDICT (Gottlieb et al. 2011) — 確認
- [ ] Hetionet (Himmelstein et al. 2017 eLife) — DOI 確認
- [ ] PrimeKG (Chandak et al. 2023) — DOI 確認
- [ ] Swanson 1986 — page 7-18 確認
- [ ] LBD survey — 具体的な論文特定
- [ ] Description logics handbook — Cambridge UP 2003 確認
- [ ] Rule-based reasoning — AMIE? RuleN?
- [ ] Wikidata (Vrandecic & Krötzsch 2014 CACM) — volume/DOI 確認

### 図・表の調整

- [ ] Figure 1: キャプションと図の内容が一致しているか確認
- [ ] Figure 2: X軸ラベルが "Subset A/B/C" で一致しているか確認
- [ ] Figure 3: Y軸が drift rate (fraction) であることを確認
- [ ] Figure 4: before/after の数値が figure3_drift_by_depth.png と整合しているか確認
- [ ] Table 2: tabular 幅が2カラムレイアウトでも収まるか確認 (wide table)
- [ ] Table 3: 15行 + legend が1ページに収まるか確認

### 文章

- [ ] Abstract 最終文 "[repository URL]" → 実URL
- [ ] Introduction の author 情報
- [ ] Related work: 各 \cite{TODO-*} が補完されたら文章の流れを再確認
- [ ] Method 3.5 (Data section): 現在 method_summary.md のサブセット情報が
      04_experimental_setup.tex に移植済み → Method節に重複があれば整理

### その他

- [ ] `.claire/` ディレクトリの誤ファイルを削除:
      `rm -rf /Users/alun/claude-dev/kg-discovery-engine/.claire/`
- [ ] Appendix C (candidate examples) の追加 — paper_assets/candidate_examples.md から
- [ ] Run summary table (Appendix B) の詳細版 — run_summary_table.csv から全13行

---

## 3つの中核主張との figure/table 対応

| Claim | Figure | Table | Section |
|-------|--------|-------|---------|
| Claim 1: Alignment unlocks unreachable paths | Figure 2 (alignment leverage) | Table 2 (subset comparison) | 5.1 |
| Claim 2: Deep CD needs quality filtering | Figure 3 (drift by depth), Figure 4 (filter effect) | Table 1 (hypothesis status) | 5.2 |
| Claim 3: Bridge dispersion drives yield | Figure 2 (alignment leverage) | Table 2 (unique/bridge ratio) | 5.3 |
| Root cause (Run 014) | — | Table 3 (relation semantics) | 7.1, 8.5 |
| Candidates | — | Table 4 (candidate summary) | 6 |

---

## 次ステップ推薦

1. **即座**: `.claire/` 誤ファイル削除
2. **次セッション**: `pdflatex main.tex` でコンパイル確認 → エラーリスト作成
3. **その後**: 引用補完 (TODO- entries) → 文体レビュー → 図サイズ最終調整
4. **最終**: journal/conference template への移植 (現在は article class)
