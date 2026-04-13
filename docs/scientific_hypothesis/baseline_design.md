# Phase 4: Baseline Design

## 設計原則

- random baseline は「意味」だけを壊し「複雑度」は揃える
- chain length・relation type 構成比・candidate count をすべての method 間で揃える
- 複雑度が揃わない比較は「KG の価値」ではなく「情報量の差」を測定してしまう

---

## 1. C2: Multi-Operator Pipeline（比較対象の主体）

### 生成フロー

```
biology_kg × chemistry_kg
       │
   align()  ─── AlignmentMap: {bio_node: chem_node, ...}
       │
   union()  ─── merged_kg (全ノード・全エッジ)
       │
  compose() ─── HypothesisCandidates (multi-hop paths)
       │
difference() ─── biology_kg 固有のパターンに絞り込み
       │
  top 50 candidates by score
```

### 保存項目

各 `HypothesisCandidate` に以下を記録:

| フィールド | 説明 |
|-----------|------|
| `id` | `C2_{seq_num}` |
| `method` | `"C2_multi_op"` |
| `subject_id`, `relation`, `object_id` | 仮説の主語・述語・目的語 |
| `description` | 自然言語説明（既存 compose() が生成） |
| `chain_length` | compose の hop 数 |
| `operator_sequence` | `["align", "union", "compose", "difference"]` |
| `path_edges` | 使用エッジのリスト（traceability 用） |
| `novelty_score` | `scorer.py::_score_novelty()` |
| `domains_involved` | `["biology", "chemistry"]` など |
| `cross_domain` | bool |
| `provenance_kg` | どの KG から派生したか |

---

## 2. C1_compose: Single-Operator Baseline（compose only）

### 生成フロー

```
biology_kg  (chemistry_kg を使わない)
       │
  compose() ─── HypothesisCandidates
       │
  top 50 candidates by score
```

### 複雑度の揃え方

| パラメータ | C2 と同じ値 |
|-----------|-------------|
| `max_depth` | 3 |
| `max_per_source` | 10 |
| `filter_relations` | 同じリスト |
| `guard_consecutive_repeat` | True |
| `min_strong_ratio` | 0.4 |
| `filter_generic_intermediates` | True |

**注意**: C1_compose は biology_kg のみに compose を適用するため、cross-domain 仮説は生成されない。この非対称性は **記録するが補正しない**（cross-domain の有無自体が C2 の特徴の一部だから）。

### 保存項目

C2 と同じ schema。`method = "C1_compose"`, `operator_sequence = ["compose"]`

---

## 3. C1_diff: Single-Operator Baseline（difference only）

### 生成フロー

```
biology_kg × chemistry_kg
       │
   align()  ─── AlignmentMap (C2 と同じ alignment 結果を再利用)
       │
difference() ─── biology_kg 固有ノードのエッジ集合
       │
  各エッジを直接仮説に変換（compose なし）
       │
  top 50 candidates
```

**直接変換ルール**: `difference()` の出力エッジ `(A, r, B)` を  
仮説「A {r} B（chem_kg には対応する関係がない）」として解釈する。

### 複雑度の揃え方

difference の出力は 1-hop のみ（chain_length = 1）。C2/C1_compose は multi-hop。

この **chain length の非対称性は記録して分析する**。比較時には:
- chain_length = 1 の C2/C1_compose 仮説 vs C1_diff で追加比較
- 全体比較は chain length の分布差を考慮した感度分析を行う

### 保存項目

`method = "C1_diff"`, `chain_length = 1`, `operator_sequence = ["align", "difference"]`

---

## 4. C_rand: Random Path Baseline

### 設計原則

「KG の構造を破壊し、意味のあるパスを意味のないパスで置き換える」が、  
**relation type の構成比・chain length 分布・candidate 数は C2 と同じに保つ**。

### 生成アルゴリズム

```python
def generate_random_baseline(
    merged_kg: KnowledgeGraph,
    c2_candidates: list[HypothesisCandidate],
    seed: int = 42
) -> list[HypothesisCandidate]:
    """C2と同じ複雑度のランダム仮説を生成する。"""
    rng = random.Random(seed)
    
    # C2 の chain_length 分布を計算
    length_dist = Counter(h.chain_length for h in c2_candidates)
    
    # C2 の relation type 構成比を計算（全エッジ中の各 relation の割合）
    rel_dist = Counter(e.relation for e in merged_kg.edges)
    
    candidates = []
    for target_chain_length, count in length_dist.items():
        for _ in range(count):
            # ランダムにノードを選ぶ（KG 内の任意のノード）
            subject = rng.choice(list(merged_kg.nodes.values()))
            object_ = rng.choice(list(merged_kg.nodes.values()))
            while object_.id == subject.id:
                object_ = rng.choice(list(merged_kg.nodes.values()))
            
            # relation type を構成比に従ってサンプリング
            relation = rng.choices(
                list(rel_dist.keys()),
                weights=list(rel_dist.values())
            )[0]
            
            # chain_length に合わせた中間ノードをランダム選択
            intermediates = [
                rng.choice(list(merged_kg.nodes.values()))
                for _ in range(target_chain_length - 1)
            ]
            
            candidates.append(HypothesisCandidate(
                id=f"C_rand_{len(candidates):03d}",
                subject_id=subject.id,
                relation=relation,
                object_id=object_.id,
                description=f"{subject.label} {relation} {object_.label} [random]",
                provenance={"method": "random", "chain_length": target_chain_length},
                operator="random_path",
                source_kg_name="merged_kg"
            ))
    
    return candidates[:len(c2_candidates)]  # C2 と同数に揃える
```

### 揃えるパラメータ

| パラメータ | 揃え方 |
|-----------|--------|
| candidate 数 | C2 の出力数と同じ（最大 50） |
| chain_length 分布 | C2 の chain_length histogram に合わせてサンプリング |
| relation type 構成比 | merged_kg 全エッジの relation 構成比で重み付けサンプリング |
| subject/object ドメイン | merged_kg の全ノードからランダム（ドメインは揃えない→これが「意味の破壊」） |

### 保存項目

`method = "C_rand"`, `operator_sequence = ["random_path"]`, `rng_seed = 42`

---

## 5. Optional: Embedding Nearest-Neighbor Baseline（C_emb）

**MVP では実装しない**。Full Scale 以降で検討。

### 設計意図

「embedding 空間で近いノードを繋ぐだけ」の baseline で、  
KG の構造ではなく意味的近傍だけで仮説を生成した場合との比較。

### 実装要件（Full Scale）

- ノードラベルの文字列 bag-of-words 表現（外部 ML モデル不使用）
- TF-IDF ベクトルの cosine similarity で nearest neighbor 取得
- `scipy.sparse` と `math` モジュールのみで実装可能（標準ライブラリ準拠）

---

## 6. Method 間の揃え確認

仮説生成後、`scripts/verify_baseline_parity.py` で以下を確認する:

| 確認項目 | 目標 |
|---------|------|
| 各 method の candidate 数 | 同数（最大 50） |
| chain_length 分布の差 | C2 vs C_rand の KS 統計量 < 0.2 |
| relation type 構成比の差 | C2 vs C_rand の χ² 検定 p > 0.05（揃っていることを確認） |
| 重複仮説数（cross-method） | 記録して報告（除外ルール適用） |

---

## 7. 各 Baseline の分析上の役割

| baseline | 主な役割 |
|---------|---------|
| C1_compose | 「compose だけでも同じ precision になるか」= operator 追加の価値 |
| C1_diff | 「difference だけの 1-hop 仮説はどれほど検証されるか」= multi-hop の価値 |
| C_rand | 「KG 構造が仮説の質に貢献しているか」= KG 自体の価値 |

**解釈ガイド**:
- C2 > C_rand, C2 ≈ C1_compose → multi-hop compose が価値の源泉、align/difference の効果は小さい
- C2 > C1_compose > C_rand → align/union/difference の追加が compose を強化
- C2 ≈ C_rand > C1_compose → compose の探索が仮説の多様性を下げている可能性（要調査）
