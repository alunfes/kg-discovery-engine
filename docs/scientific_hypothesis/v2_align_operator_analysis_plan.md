# P2: Align オペレータ精度分析計画

**作成日**: 2026-04-14  
**ステータス**: 設計段階（P1/P3 の結果を待ってから着手）  
**前提**: P1 bridge_quality または alignment_precision が改善効果を示した後に深掘りする

---

## 位置付け

P2 は P1 の仮説（「align のノイズが investigability を下げている」）が支持された場合の深掘り分析。

**着手条件（Go gate）:**
- P1 の bridge_quality または alignment_precision で investigability ≥ 0.95 が確認された場合
- または P1 で align 関連条件が最も高い改善を示した場合

**P1 が全条件で 0.92 未満だった場合:** P2 は後回し。文献密度の構造的問題の調査を優先する。

---

## 研究問い

align オペレータが生成する cross-domain bridge のうち、どの程度が意味的に正確か。  
不正確な bridge（false positive alignment）は investigability の低下に寄与しているか。

---

## 分析計画

### Step 1: 現行 align 出力の分離

`bio_chem_kg_full.json` の cross-domain エッジを以下の2種類に分類する:

| 種別 | 説明 |
|------|------|
| manual_edges | 手動定義された cross-domain エッジ |
| align_edges | align オペレータが生成した bridge エッジ |

実装: エッジの `source` フィールド（または同等のメタデータ）で分離。  
メタデータが欠如している場合は、align オペレータのログから再構築する。

### Step 2: Align エッジのサンプリング評価

align が生成した cross-domain エッジから 20件をランダムサンプリング（seed 固定）し、
手動で以下の3カテゴリにラベリングする:

| ラベル | 定義 |
|--------|------|
| correct | biology と chemistry の概念が意味的に正確に対応している |
| partial_match | 部分的に関連するが、厳密には異なる概念が align された |
| false_positive | 意味的に関係ないのに align された（ノイズ） |

**ラベリング基準:**
- 「同じ生物学的プロセスに関与する化合物」→ correct
- 「名前が似ているが機能が異なる」→ false_positive
- 「一方が他方のサブセット」→ partial_match

**ラベラー:** 実施者1名（バイアス抑制のため、仮説の方向性を忘れてからラベリング）

### Step 3: Precision の推定

```
align_precision = correct / (correct + partial_match + false_positive)
```

20件サンプルから推定した precision と 95% 信頼区間（Wilson interval）を報告。

**判断基準:**
- precision ≥ 0.80: align は十分な精度。bridge quality 以外の要因を調査
- precision 0.60〜0.80: 改善余地あり。bridge_quality フィルタが有効な可能性
- precision < 0.60: align が主要な問題。大幅な改善が必要

### Step 4: Error → Investigability への影響分析

run_018 の 210件のうち、各仮説が経由した bridge の種類を特定し、investigability との関係を調べる。

```
仮説を3グループに分類:
  group_A: align_edges を経由していない仮説（C1 相当）
  group_B: align_edges を経由し、correct bridge のみ使用
  group_C: align_edges を経由し、false_positive または partial_match bridge を含む
```

各グループの investigability rate を比較:

| グループ | 期待 investigability |
|---------|-------------------|
| group_A | 高（C1 相当: 0.97+） |
| group_B | 中〜高（bridge が正確なら C1 に近い） |
| group_C | 低（false positive bridge が investigability を下げる） |

group_B と group_C の差が大きければ、bridge quality 改善の証拠。

**注意:** Step 2 の 20件ラベリングは全 align エッジの一部のみ。  
Step 4 では、サンプリングした 20件の結果を全エッジに外挿することになる。  
外挿の不確実性を明示して報告する。

---

## Alignment Error の分類と原因

Step 2 の結果を踏まえ、false_positive / partial_match の原因を分類する:

### 想定されるエラーパターン

| エラーパターン | 例 | 原因 |
|--------------|-----|------|
| 名前の偶発的類似 | "Glucose" (bio) ↔ "Glucoside" (chem) | CamelCase split が過剰マッチ |
| 同義語辞書の粒度不一致 | 上位概念と下位概念が align | synonym dict が粗い |
| 文脈依存の多義性 | "receptor" が異なる文脈で使われる | 文脈情報なし |

---

## 改善候補の具体案

P2 の分析結果に基づいて、以下の改善候補を評価する:

### 案 A: Synonym Dict の制限

- 現行の synonym dict から false_positive の原因となったペアを削除
- 実装コスト: 低（dict の編集のみ）
- リスク: 有用な bridge も除外してしまう可能性

### 案 B: CamelCase Split の改善

- Split した各トークンに最小文字数制限を設ける（例: 3文字以上のみ）
- 短いトークン（"A", "in", "of" 等）のマッチを無視
- 実装コスト: 低

### 案 C: Alignment Confidence Score の導入

- P1 bridge_quality で実装した confidence score を、P2 の精度分析で校正する
- 手動ラベリング結果を使って、confidence 閾値と precision の関係を計測
- 実装コスト: 中（P1 の延長）

### 案 D: Bidirectional Validation

- align された biology concept の PubMed ヒット数と chemistry concept の PubMed ヒット数を確認
- どちらかが 0 件なら false_positive と判定
- 実装コスト: 中（PubMed API クエリが増加）

---

## P1 bridge_quality 条件との関係

P1 の bridge_quality 条件は、confidence score を導入して低品質 bridge を除外する。  
P2 の Step 2〜3（20件手動ラベリング）は、その confidence score と実際の precision の関係を検証する。

具体的には:
- P1 で confidence < 0.7 を除外 → investigability が改善した場合
- P2 で confidence < 0.7 エッジの precision を確認 → 本当に false_positive が多かったか

P2 は P1 の「なぜ効いたか（または効かなかったか）」を説明する分析として位置付ける。

---

## Pre-registration の必要性

**P2 は分析計画を事前登録することを推奨する。**

理由:
- 20件のサンプリング seed を事前に固定する必要がある
- ラベリング基準を事前に文書化し、ラベリング後の変更を防ぐ
- Step 4 のグループ分類ルールを事前に固定する

**登録すべき内容:**
1. サンプリング seed（例: 42）
2. 20件のサンプリング方法（単純ランダム or 層化）
3. ラベリング基準（correct / partial_match / false_positive の定義）
4. Step 4 のグループ分類ルール
5. precision の判断基準（0.80 / 0.60 の閾値）

**登録タイミング:** P1 の結果確認後、P2 に着手する直前。

---

## 実施スケジュール（仮）

```
P3 novelty 分析（run_018 再分析）     ← 最優先（追加実験不要）
    ↓
P1 Phase A（bridge_quality + alignment_precision）  ← 30件 × 2条件
    ↓ Go/No-Go
P1 Phase B（novelty_ceiling + provenance_quality）  ← 30件 × 2条件
    ↓
P2 align 精度分析（P1 結果の解釈）    ← P1 完了後
```

P2 は P1 Phase A の完了を待ってから計画を確定する。  
P1 が「align は主因でない」を示した場合、P2 の scope を縮小または延期する。

---

## やらないこと

- P1/P3 の結果が出る前に P2 の実装を開始する
- 20件以上のラベリング（過剰なコスト）
- 外部ツール・NLP ライブラリを使った自動ラベリング（Python 標準ライブラリのみ）
- P2 の結果に基づいて P1 の成功基準（0.95）を遡って変更する
