# Phase 0: Theme Selection

## 選定基準

| 基準 | 説明 |
|------|------|
| KG alignment 適合性 | 複数ドメインのKGをalign/union/composeすることに意味があるか |
| 文献取得容易性 | past corpus / future corpus を現repoの制約（外部APIなし）で取得できるか |
| 後続文献検証可能性 | 生成した仮説を将来文献のタイトル/アブスト照合で検証できるか |
| random baseline 比較可能性 | 「関係のランダム組み合わせ」が明確に存在し、比較が公平か |
| 支配的バイアスの不在 | タイミング・実行依存性・市場摩擦が仮説の正否を決めないか |

---

## 候補3つの評価

### 候補A: crypto market structure × network science

| 基準 | 評価 | 理由 |
|------|------|------|
| KG alignment 適合性 | △ | ノード（取引所/プロトコル）と network 概念（hub/centrality）のalignは恣意的になりやすい |
| 文献取得容易性 | △ | crypto論文はarXivにあるが母数が少なく、時系列分離が粗い |
| 後続文献検証可能性 | △ | 仮説の正否が"価格変動"に依存しがちで文献評価と混在する |
| random baseline 比較 | ○ | エッジのランダムシャッフルは容易 |
| 支配的バイアス不在 | ✗ | execution dependency・市場摩擦が支配的。Trading alpha に近い問題に戻る |

**総評**: KG向きの仮説生成に向かない。trading alpha discovery の延命になるリスクが高い。

---

### 候補B: DeFi mechanism design × behavioral finance

| 基準 | 評価 | 理由 |
|------|------|------|
| KG alignment 適合性 | △ | DeFi機構（AMM/liquidation）と behavioral finance 概念（loss aversion/herding）のalignは意味を持ちにくい |
| 文献取得容易性 | △ | DeFi論文は2020年以降に急増、behavioral finance は古典的文献が多い。time split が難しい |
| 後続文献検証可能性 | △ | DeFi自体が急速進化しており「将来文献で支持」の判定基準が揺れる |
| random baseline 比較 | ○ | 可能 |
| 支配的バイアス不在 | △ | プロトコル設計の妥当性は「採用されたか否か」で判定されがちで文献支持と乖離する |

**総評**: ドメイン間のセマンティックギャップが大きく、alignオペレータが表面的な操作になる可能性が高い。

---

### 候補C: biology × chemistry（既存KG Discovery Engine の延長）

| 基準 | 評価 | 理由 |
|------|------|------|
| KG alignment 適合性 | ◎ | 酵素↔触媒、タンパク質↔化合物などの cross-domain synonymはoperators.pyに既実装。align/union/composeが構造的に意味を持つ |
| 文献取得容易性 | ◎ | PubMed/bioRxiv/ChemRxiv は標準APIあり、abstract は公開。既存 toy_data.py/phase4_data.py をベースにできる |
| 後続文献検証可能性 | ○ | 医薬・代謝経路・drug repurposing は文献が豊富で検証期間2年あれば十分な母数が得られる |
| random baseline 比較 | ◎ | エッジのtype構成比を保ちつつランダムシャッフルが明確に定義できる |
| 支配的バイアス不在 | ◎ | 「文献で報告されたか否か」が客観的基準になり、タイミングや実行コストが支配的でない |

**総評**: 既存実装と整合し、KGオペレータの強みが最も活きる。文献検証の基盤（PubMed）が確立されており、random baseline 設計も明確。

---

## 主候補の選定

### 主候補: **候補C — biology × chemistry**

**選定理由（KG向きか、の視点）:**

1. **align オペレータの実効性**: `operators.py` の `_CROSS_DOMAIN_SYNONYMS` で enzyme↔catalyst, protein↔compound が既に実装済み。alignment に意味がある。
2. **compose オペレータの実効性**: 生物学的経路（A→B→C）の multi-hop 推論は drug repurposing・代謝経路予測の実際の研究手法と一致する。
3. **文献time split の明確性**: PubMed の publication date は信頼性が高く、2024-01-01 を validation 開始点とする cut-off が容易に実装できる。
4. **既存KGの再利用**: `src/kg/toy_data.py`（biology/chemistry domains）・`src/kg/phase4_data.py` が直接ベースになる。新規KG構築コストが最小。
5. **random baseline の公平性**: エッジのrelation type分布を保ちつつランダムに接続を組み替えるoperationが定義しやすい。

**サブテーマ（主候補内の焦点)**: **drug repurposing 仮説の生成**
- 既知薬物と新規疾患/標的の間の KG multi-hop 関係から仮説を生成
- 将来文献での "repurposing candidate" 報告が検証根拠になる
- biology KG (pathway/protein) × chemistry KG (compound/reaction) の compose が直接有用

---

## 次点候補

### 次点: **候補B — DeFi mechanism design × behavioral finance**

DeFi文献の蓄積が2025年以降に加速すると予想されるため、validation corpus が2026年時点では thin である問題が解消される可能性がある。2027年以降の再評価候補。

---

## 未確定事項

- **KG規模**: toy_data.py のノード数（~50-100）では align の精度評価が粗い。Phase 3以降でノード数≥200 のKGを構築するか、Wikidata/DrugBank をオフライン dump で取得するかは未決定。Phase 2 pre-registration 時に確定する。
- **文献corpus の収集手段**: PubMed E-utilities API はHTTP呼び出しが必要で「外部APIなし」制約と抵触する。**manual download（MEDLINE bulk export）または pre-fetched JSON の静的ファイル利用**で回避する想定だが、Phase 3 corpus design 時に最終確定。
