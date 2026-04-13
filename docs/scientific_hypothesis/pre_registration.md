# Phase 2: Pre-Registration Document

**Pre-registration date**: 2026-04-13
**Status**: DRAFT — freeze this document before any hypothesis generation run

---

## 1. 研究タイトル

KG Multi-Operator Pipeline による Scientific Hypothesis Generation の将来文献支持率検証

---

## 2. 研究の目的

KG multi-operator pipeline (align → union → compose → difference) が生成する科学的仮説が、  
single-operator baseline および random baseline と比較して、  
将来文献で支持・調査される割合が統計的に高いかを検証する。

---

## 3. 主要パラメータ

| パラメータ | 値 |
|------------|-----|
| 対象ドメイン | biology × chemistry（drug repurposing subtheme） |
| KG生成コミット | [git commit hash — freeze 前に記入] |
| 仮説生成コミット | [git commit hash — freeze 前に記入] |
| 乱数シード | 42 |

---

## 4. 文献コーパス

| 項目 | 値 |
|------|-----|
| corpus sources | PubMed (MEDLINE bulk export), bioRxiv preprints (static dump) |
| past corpus 期間 | 〜 2023-12-31（KG構築・仮説生成の根拠文献） |
| validation corpus 期間 | 2024-01-01 〜 2025-12-31 |
| validation corpus 収集方法 | 手動 download または pre-fetched static JSON（外部API呼び出しなし） |

**Time split 厳守**: past corpus と validation corpus の間に完全な時間的分離を設ける。仮説生成ロジックは past corpus のみを参照する。

---

## 5. 生成方法（methods）

| method ID | 説明 | 使用オペレータ | MVP |
|-----------|------|---------------|-----|
| C2 | multi-op pipeline | align → union → compose → difference | ○ |
| C1_compose | single-op baseline | compose only | ○ |
| C1_diff | single-op baseline | difference only | ✗（Full Scale のみ） |
| C_rand | random path baseline | ランダムエッジシャッフル（relation type 構成比保持） | ○ |

- MVP: C2 / C1_compose / C_rand の3 methods、各 20 仮説（合計 60 件）
- Full Scale: C1_diff を追加し、各 method 最大 50 仮説（合計 200 件）
- chain length・candidate count は method 間で揃える（baseline_design.md 参照）

---

## 6. Novelty スコアリング規則

`src/eval/scorer.py` の `_score_novelty()` を流用。パラメータは固定:
- cross-domain new edge: 1.0
- same-domain new edge: 0.8
- reframed (semantic overlap 0.5–0.8): 0.5
- near-equivalent (semantic overlap > 0.8): 0.2
- already exists in KG: 0.0

high-novelty の閾値: `novelty_score ≥ 0.7`（cross-domain または new edge）

---

## 7. 支持ラベリング規則

5分類ラベル（`supported`, `partially_supported`, `contradicted`, `investigated_but_inconclusive`, `not_investigated`）の定義は `labeling_protocol.md` に従う。

- ラベリングは 1 名の primary labeler が行い、信頼性確認のため 20% サンプルを second labeler が独立ラベリング
- 不一致時は adjudication rule（`labeling_protocol.md` Section 5）に従う
- ラベリング結果は `runs/run_sci_NNN_YYYYMMDD/labels.json` に保存

---

## 8. 成功基準（事前登録）

以下の3条件を事前に登録する。データを見た後の基準変更を禁止する。

| ID | 条件 | 検定方法 |
|----|------|---------|
| SC-1 | precision_positive(C2) > precision_positive(C_rand), p < 0.05 (片側) | Fisher's exact test |
| SC-2 | investigability(C2) ≥ investigability(C_rand) | 記述統計（差の CI 報告） |
| SC-3 | high_novelty_uninvestigated_rate(C2) > high_novelty_uninvestigated_rate(C_rand) | Fisher's exact test |

**「有効性あり」の判定**: SC-1 を満たすこと（必須）。SC-2・SC-3 は副次的支持。

---

## 9. 除外規則（事前定義）

以下の仮説は分析から除外する（除外理由を `labels.json` に記録）:

1. **重複仮説**: 同一 subject-relation-object 組み合わせが複数 method から生成された場合、C2 の仮説を採用し他 method の同一仮説を除外（ただし除外数を報告する）
2. **KG 内既存エッジ**: past corpus の KG に既に存在するエッジを表す仮説（novelty = 0.0）
3. **パース不能仮説**: description が空、または subject/object が NULL の仮説

---

## 10. Freezeチェックリスト

pre-registration を確定（freeze: true）する前に以下を確認する:

- [ ] KG 生成スクリプトのコミット hash を記入
- [ ] 仮説生成スクリプトのコミット hash を記入  
- [ ] `configs/scientific_hypothesis_registry.json` の `frozen: true` を設定
- [ ] past corpus ファイルを `data/corpus/past/` に配置し md5sum を記録
- [ ] validation corpus ファイルを `data/corpus/validation/` に配置しアクセス制限（仮説生成ステップ完了まで参照禁止）
- [ ] 乱数シード 42 で全スクリプトが決定論的に動作することを確認（`scripts/verify_determinism.py` 実行）

---

## 11. 未確定事項（freeze前に解決が必要）

| 項目 | 現状 | 解決方法 |
|------|------|---------|
| KG ノード数 | toy_data.py は ~50-100 ノード | Phase 3 で ≥200 ノードKGを構築するか決定 |
| corpus 収集方法 | PubMed API は外部HTTPで制約違反 | MEDLINE bulk FTP dump（static）を使うか、manual download corpus を使うか Phase 3 で確定 |
| second labeler の確保 | 未確保 | 必要性と代替手段（self-review with 2-week gap）を Phase 5 で決定 |

---

## 12. 変更管理

本文書は freeze 後に変更してはならない。  
やむを得ない変更がある場合は、変更内容・理由・変更者・変更日を末尾の変更ログに追記し、  
`configs/scientific_hypothesis_registry.json` の `frozen` を `false` に戻した上で再 freeze する。

### 変更ログ

| 日付 | 変更者 | 変更内容 | 理由 |
|------|--------|---------|------|
| (none) | — | — | — |
