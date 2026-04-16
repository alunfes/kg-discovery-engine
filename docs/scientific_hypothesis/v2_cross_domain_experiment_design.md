# P1: Cross-Domain Investigability 改善実験設計

**作成日**: 2026-04-14  
**ステータス**: 設計段階（未実装）  
**前提**: scientific_hypothesis v1 CLOSED。SC-3r (investigability) は確立済み。

---

## 研究問い

C2 (cross-domain multi-op, investigability=0.914) と C1 (bio-only single-op, investigability=0.971) の差 0.057 は何に起因するか。  
その差を縮める（あるいは逆転させる）には operator chain のどこを変えるべきか。

**出発点となる観察:**

| Method | Investigability | N |
|--------|----------------|---|
| C1 (bio-only, single-op) | 0.971 | 70 |
| C2 (cross-domain, multi-op) | 0.914 | 70 |
| C_rand_v2 | 0.600 | 70 |

C2 > C_rand は確立済み（2回再現）。  
C1 > C2 は観察された副次発見。原因は未解明（3仮説が競合中: `cross_domain_gap_analysis.md` 参照）。

---

## 実験設計

### 全体構成

| Condition | 説明 | N |
|-----------|------|---|
| C2_baseline | 現行 multi-op（run_018 設定そのまま） | 30 |
| bridge_quality | align confidence 閾値による低品質 bridge 除外 | 30 |
| alignment_precision | exact match + high-confidence synonym のみ使用 | 30 |
| novelty_ceiling | novelty score 上限による extreme-novel 仮説除外 | 30 |
| provenance_quality | エッジ confidence weight による低品質パス除外 | 30 |

**合計: 5条件 × 30件 = 150件**

**成功基準: investigability ≥ 0.95（C1 との差 < 0.03）**

---

## 各実験条件の詳細

### Condition 0: C2_baseline（コントロール）

- **設定**: run_018 の run_config.json を変更なしで使用
- **目的**: run_018 (N=70) の investigability=0.914 が N=30 のサブセットで安定しているか確認
- **判断**: C2_baseline の investigability が 0.85〜0.95 の範囲外なら、N=30 では比較が不安定。
  その場合は N を増やすか、run_018 データを再利用する。

---

### Condition 1: bridge_quality

**研究仮説**: align オペレータが生成する cross-domain bridge node のうち、低確信度のものがノイズ仮説を混入させ、investigability を下げている。

**現行動作:**
- CamelCase split + synonym dict による alignment
- 全 match を bridge として使用（確信度フィルタなし）

**変更点:**
- alignment confidence score を導入
  - exact string match: confidence = 1.0
  - CamelCase split + exact match: confidence = 0.9
  - synonym dict match（第1段階）: confidence = 0.7
  - synonym dict match（第2段階以降）: confidence = 0.5
- 閾値: confidence < 0.7 の bridge を除外

**実装箇所**: `src/scientific_hypothesis/` の align オペレータ部分（既存 generator を修正）

**期待する変化:**
- bridge 数が減少（cross-domain 接続が減る）
- 残った bridge が意味的に正確 → 生成仮説の investigability 向上

**リスク:**
- bridge 数が少なすぎて 30件生成できない場合は、閾値を 0.6 に緩める

---

### Condition 2: alignment_precision

**研究仮説**: precision-recall のバランスが investigability に影響する。現行は recall 優先（多くの bridge を生成）だが、precision 優先（少数の確実な bridge のみ）に切り替えると investigability が上がる。

**現行動作:**
- synonym dict の全レベルを使用
- CamelCase split も積極使用

**変更点:**
- exact string match のみ bridge として使用
- synonym dict は第1レベル（直接同義語）のみ許可
- CamelCase split は無効化

**bridge_quality との違い:**
- bridge_quality は「スコアリングして低スコアを除外」
- alignment_precision は「マッチングルール自体を厳格化」（スコアなし）

**期待する変化:**
- bridge 数が大幅減少（最も保守的な条件）
- cross-domain 接続が少ない分、bio 寄りの仮説が増える可能性

**リスク:**
- 30件生成困難な場合は事前に bridge 数をカウントして判断

---

### Condition 3: novelty_ceiling

**研究仮説**: 極端に新規な仮説は investigability を下げる（逆U字の右側）。novelty score に上限を設けることで investigability を改善できる。

**現行動作:**
- path_depth_limit で制限しているが、novelty の上限なし

**変更点:**
- 仮説の novelty score を計算（定義は P3 文書参照）
- novelty score が閾値 T_high を超える仮説を除外
- T_high の初期値: P3 分析（run_018 既存データ）から決定する

**注意**: T_high は **P3 の分析完了後に設定する**。P3 が未完了の場合は本条件を後回しにする。

**期待する変化:**
- extremely novel な仮説が除外され、「sweet spot novelty」の仮説のみ残る
- investigability 向上

---

### Condition 4: provenance_quality

**研究仮説**: compose パス上のエッジの品質を考慮することで、確からしいパスのみを仮説生成に使用し、investigability が上がる。

**現行動作:**
- パス長が同じなら品質無視
- 全エッジを等価に扱う

**変更点:**
- 各エッジに confidence weight を付与
  - 手動定義エッジ: weight = 1.0
  - align 生成 bridge エッジ: weight = align confidence score
  - 派生エッジ（union/difference で追加）: weight = 0.8
- パスの品質スコア = パス上の全エッジの weight の積
- quality score < 0.5 のパスを除外

**bridge_quality との違い:**
- bridge_quality は bridge node の品質
- provenance_quality は仮説生成パス全体の品質（bridge を含むが、それだけではない）

---

## 評価方法

### PubMed Validation プロトコル
- 各条件で 30件生成
- run_018 と同じ PubMed validation スクリプトを使用 (`src/scientific_hypothesis/run_018_validate.py`)
- ラベリング基準: `docs/scientific_hypothesis/labeling_protocol.md` に準拠
- investigability = PubMed で関連文献が見つかった仮説の割合

### 判定基準

| 結果 | 判定 |
|------|------|
| investigability ≥ 0.95 | 成功（C1 との差 < 0.03） |
| 0.92 ≤ investigability < 0.95 | 部分的改善（追加分析へ） |
| investigability < 0.92 | 改善なし |

---

## 実施順序と Go/No-Go ゲート

### Phase A: Align 仮説の検証（先行実施）

`bridge_quality` と `alignment_precision` を先に実施する。

**根拠:**
- align が主因なら2条件とも効くはず（相互確認が可能）
- align 精度向上は実装コストが比較的低い
- C1（bio-only, align を使わない）との比較で align の影響を推定できる

**Go/No-Go:**
- どちらかで investigability ≥ 0.95 → Phase B に進む（P2 align operator 深掘り）
- 両方で 0.92 未満 → Phase B の前に P3 novelty 分析を優先する

### Phase B: Novelty / Provenance 仮説の検証（後続実施）

Phase A の結果を見てから `novelty_ceiling` と `provenance_quality` を実施。

**注意**: `novelty_ceiling` の閾値設定は P3 分析の完了が前提。

---

## Pre-registration の必要性

**本実験は事前登録を推奨する。**

理由:
- 4つの条件を複数比較するため、条件選択バイアスのリスクがある
- 成功基準（investigability ≥ 0.95）を事後に変更するリスクを排除する必要がある

**登録すべき内容:**
1. 各条件の実装仕様（閾値・ルール）
2. 成功基準（investigability ≥ 0.95）
3. 実施順序（Phase A → Go/No-Go → Phase B）
4. novelty_ceiling の T_high は P3 完了後に事前登録

**登録タイミング:** 実装完了・コード freeze 後、データ生成前。

---

## P2 との関係

P1 の bridge_quality / alignment_precision が改善効果を示した場合、P2（align operator 精度分析）で原因を深掘りする。

P1 が改善効果を示さなかった場合は、P2 は後回しとし、文献密度の構造的問題（仮説 2 in cross_domain_gap_analysis.md）に焦点を移す。

---

## やらないこと

- SC-1r を救済しにいかない（FAIL は確定・変更なし）
- P1 の結果が出る前に P2 の実装に入らない
- 「改善が見られた」という曖昧な判定（定量基準 0.95 を守る）
- 外部 API や事前学習済みモデルを使った alignment（Python 標準ライブラリのみ）
