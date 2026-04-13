# Phase 3: Corpus and Time Split Design

## 1. Time Split の原則

**厳守ルール**: 仮説生成に使用する KG は past corpus（〜2023-12-31）のみから構築する。  
validation corpus（2024-01-01〜2025-12-31）は、ラベリングが開始されるまで仮説生成コードからアクセス不能にする。

```
timeline:
  ├─── past corpus ──────────────────┤validation corpus─────────────┤
  1990                            2023-12-31  2024-01-01         2025-12-31
  
  KG 構築・仮説生成 ───────────────────┤
                                          ↓ time barrier
                              ラベリング（文献照合）────────────────────┘
```

---

## 2. 文献ソース候補

### 2.1 Past Corpus（KG 構築用）

| ソース | 対象 | 取得手段 | 現repo制約との整合 |
|--------|------|---------|------------------|
| PubMed MEDLINE bulk FTP | biology/pharmacology/chemistry 論文 abstracts (1990-2023) | `ftp.ncbi.nlm.nih.gov/pubmed/baseline/` からの静的 XML dump → local JSON | FTP ダウンロードは「外部APIなし」制約の対象外（データ取得スクリプトは外部HTTP呼び出しだが、一度だけ手動実行・結果を static file として保存） |
| ChEMBL (static dump) | 化合物-標的-アッセイ関係 | `ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/` | 同上（手動 FTP download） |
| DrugBank (XML export) | 薬物-標的-疾患 | 手動 download（登録必要、非商用利用可） | 手動取得 → static file |
| UniProt reviewed (Swiss-Prot) | タンパク質-機能-疾患 | `ftp.uniprot.org/pub/databases/uniprot/current_release/` | 手動 FTP |

**MVP 実装**: `src/kg/toy_data.py` / `src/kg/phase4_data.py` の biology/chemistry KG を拡張して手動キュレーションで ≥200 ノード KG を構築する。  
外部データソースの本格取り込みは Full Scale 実装（MVP 後）に先送り。

### 2.2 Validation Corpus（ラベリング用）

| ソース | 対象期間 | 取得手段 | 注意 |
|--------|---------|---------|------|
| PubMed E-utilities API | 2024-01-01〜2025-12-31 | `esearch` + `efetch` スクリプト（一回限り実行・結果を静的 JSONLに保存） | API キーなしでも 3 req/s 制限で取得可能 |
| bioRxiv API | 2024-01-01〜2025-12-31 | `https://api.biorxiv.org/details/biorxiv/...` | JSON レスポンスを静的保存 |
| ChEMBL 新規 assay | 2024-01-01〜 | ChEMBL バージョン差分（release ノート参照） | 手動差分確認 |

**重要**: validation corpus の取得スクリプト（HTTP API コール）は仮説生成フェーズ完了後に実行する。取得スクリプトのコミット hash を `scientific_hypothesis_registry.json` に記録する。

---

## 3. Past Corpus から KG への変換

### 3.1 エンティティ・関係の抽出方針

Past corpus から KG ノード・エッジを構築する。現 `src/kg/models.py` の `KGNode`/`KGEdge` 形式を維持する。

```
抽出対象エンティティ:
  biology domain: protein, gene, pathway, disease, organism
  chemistry domain: compound, reaction, enzyme, functional_group

抽出対象関係（past corpusから手動キュレーション）:
  inhibits, activates, binds_to, catalyzes, is_part_of,
  associated_with, treats, causes, interacts_with
```

### 3.2 KG サイズ目標

| 指標 | MVP | Full Scale |
|------|-----|-----------|
| ノード数 | ≥200（biology: ~120, chemistry: ~80） | ≥1000 |
| エッジ数 | ≥400 | ≥5000 |
| ドメイン数 | 2（biology, chemistry） | 2-3 |
| align 可能ノードペア | ≥30 | ≥150 |

---

## 4. Time Split の実装詳細

### 4.1 ファイル構成

```
data/
├── corpus/
│   ├── past/
│   │   ├── pubmed_bulk_filtered.jsonl   # 〜2023-12-31, title+abstract+MeSH
│   │   ├── chembl_static.jsonl          # 〜2023-12-31, compound-target
│   │   └── md5sums.txt                  # 全ファイルの md5sum（freeze 時に記録）
│   └── validation/
│       ├── pubmed_2024_2025.jsonl        # 2024-01-01〜2025-12-31
│       ├── biorxiv_2024_2025.jsonl       # 同上
│       └── .gitignore_hint              # "validation corpus は仮説生成完了後にのみ参照"
├── kg/
│   ├── biology_kg_v1.json              # past corpus から生成、freeze 後不変
│   └── chemistry_kg_v1.json            # 同上
```

### 4.2 Time Barrier の実装

- `scripts/run_scientific_hypothesis_generation.py` は `data/corpus/validation/` を読まない
- 仮説生成完了後に `scripts/verify_time_split.py` を実行し、生成された仮説が validation corpus を参照していないことを確認
- 確認後、`configs/scientific_hypothesis_registry.json` の `kg_generation_commit` と `hypothesis_generation_commit` を記録

---

## 5. Corpus 収集の現実的制約と対処

| 制約 | 問題 | 対処 |
|------|------|------|
| 「外部APIなし」ルール | PubMed API は HTTP call | 仮説生成スクリプト外で一回限り実行し、static JSON として保存。corpus 収集スクリプト自体は外部呼び出しだが、メインパイプラインには含めない |
| KG ノード数が少ない | toy_data.py は ~50-100 ノード | MVP では手動拡張（domain expert knowledge を JSONL でハードコード）、Full Scale では外部 dump |
| Validation corpus の完全性 | 2024-2025 年の文献が全て取得できない | 取得漏れは investigability の underestimate につながるが、method 間で系統的でないため相対比較は有効。漏れ率を報告する |
| ラベリングに主観が入る | 「supported」判定の曖昧さ | `labeling_protocol.md` の厳密定義と adjudication rule で対処 |

---

## 6. Manual/Semi-automatic Labeling の必要性

**現時点では完全自動収集・ラベリングは不可能。** その理由:

1. **文献照合の精度**: 仮説「compound X activates protein Y in disease Z」が将来文献で「supported」かどうかは、title/abstract のキーワード一致だけでは誤判定が多い。最低限の人手確認が必要。
2. **同一性判定**: 仮説の表現ゆれ（"X inhibits Y" vs "Y is inhibited by X"）を自動で判定するには NLP が必要で、「外部APIなし」制約と衝突する。
3. **Partially_supported の境界**: 間接的証拠の有無は文脈依存であり、規則ベース自動化が困難。

**推奨**: Semi-automatic（キーワード検索で候補文献を絞り込み、最終判定は人手）。
詳細は `labeling_protocol.md` 参照。

---

## 7. 未確定事項

| 項目 | 未確定内容 | 決定期限 |
|------|-----------|---------|
| corpus サイズの下限 | validation corpus が薄すぎると investigability が低く全て not_investigated になる。事前に corpus density を確認する必要がある | Phase 3 実装前 |
| DrugBank ライセンス | 非商用利用可だが再配布不可。local 利用のみに限定し git に commit しない | corpus 取得前 |
| KG エンティティ正規化 | 同一タンパク質が複数名称で出現する問題（UniProt ID 正規化）。MVP では手動対処、Full Scale では要検討 | MVP KG 構築時 |
