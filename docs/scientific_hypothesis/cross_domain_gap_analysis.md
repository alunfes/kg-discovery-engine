# Cross-Domain Gap Analysis: なぜ C2 は C_rand に勝つのに C1 に負けるのか

**作成日**: 2026-04-14  
**根拠データ**: run_018 (N=70 per method)

---

## 観察された構図

| Method | 説明 | Investigability |
|--------|------|----------------|
| C_rand_v2 | random baseline | 0.600 |
| C2 (multi-op) | KG cross-domain (biology × chemistry) | 0.914 |
| C1 (single-op) | KG bio-only | 0.971 |

- C2 > C_rand: KG が意味構造を与えることで investigability が上がる（+0.314）
- C1 > C2: bio-only の single-op が cross-domain の multi-op より investigability が高い（+0.057）

この非対称性をどう説明するか。

---

## 仮説的説明

### 1. 新規性-investigability トレードオフ

cross-domain 仮説（biology × chemistry）は、単一ドメイン仮説（bio-only）より新規性が高い。
しかし、まだ十分に研究されていない領域に踏み込むため、PubMed 上で既存研究が見つかりにくく、
investigability が若干下がる可能性がある。

「新規すぎる仮説は investigable でない」という構造的トレードオフが生じている。

### 2. 文献密度の偏り

- biology 単体: 文献密度が高く、生成した仮説が既存研究でカバーされやすい
- biology × chemistry cross-domain: 交差領域は文献密度が下がり、「既存研究なし」と判定される可能性が上がる

C1 の高 investigability は、KG multi-op の能力ではなく、**bio 領域の文献密度の高さ**を反映している可能性がある。

### 3. align オペレータのノイズ

align オペレータが biology-chemistry 間で意味的に正確でないマッチングを作ることで、
生成された cross-domain 仮説が概念的に不整合になり、investigable でない仮説が混入している可能性がある。

align の精度が上がれば C2 の investigability が改善する余地がある。

---

## 現時点での解釈

これらは3つの独立した仮説であり、現時点では検証されていない。

ただし、以下は確立している:

- **C2 > C_rand は確立**: KG が意味構造を付与することで investigability は上がる
- **C1 > C2 は観察された事実**: bio-only の方が investigable（原因は未解明）
- **C2 が C1 より劣ることは、multi-op が無価値であることを意味しない**

C1 が強いのは、bio 領域の文献密度という外部要因の可能性があり、
multi-op の設計の欠陥とは区別して考える必要がある。

---

## 次の研究問い

「KG multi-op は random baseline より investigable な仮説を生成する」は確立した。
次は **「cross-domain の investigability をどう上げるか」** に進む。

**具体的な問い:**

1. align オペレータの精度向上（意味的マッチングの改善）で C2 investigability は上がるか
2. cross-domain 仮説の中で investigable なものと not_investigated なものの違いは何か
3. 新規性と investigability の定量的トレードオフを測定できるか（新規性スコアの導入）

---

## やらないこと

- SC-1r を救済しにいかない（FAIL は確定）
- 「C2 は C1 より investigability が低いから multi-op はダメ」と早期結論しない
- 原因未解明のまま別ドメインへ飛ばない
- cross-domain の investigability 低下を「設計ミス」と断定しない（観察事実として保持）
