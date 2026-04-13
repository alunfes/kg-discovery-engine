# 主仮説の更新記録 v2

**作成日**: 2026-04-14  
**根拠実験**: run_017 (N=50), run_018 (N=70)

---

## Primary Endpoint の変更

### 旧 primary endpoint: novel_supported_rate (SC-1r)

KG multi-op が random baseline より高い "novel & supported" 仮説を生成するという主張。

**結果**: FAIL (run_017: C2=0.130 vs C_rand=0.219, p=0.91)

---

### 新 primary endpoint: investigability_rate (SC_inv_primary)

KG multi-op が random baseline より高い investigability を持つ仮説を生成するという主張。

**結果**: PASS (run_017: p=0.0007, run_018: p<0.05, 2回再現)

---

## 変更理由

1. **SC-1r は2回の検証で一貫して FAIL**
   - run_017 で C2 < C_rand (C2=0.130, C_rand=0.219)
   - p値 0.91 は帰無仮説方向の強い証拠
   - 追加検証により救済できる状況にない

2. **SC-3r は2回の検証で一貫して PASS、かつ強い効果量**
   - run_017: C2=0.920 vs C_rand=0.640 (効果量大)
   - run_018 (N=70, pre-registered): C2=0.914 vs C_rand=0.600 (再現)

3. **価値軸のずれが判明**
   - KG multi-op の強みは「正しい仮説を当てる」ことではなく「検証可能な仮説を生成する」こと
   - これは SC-1r が問いかけていた価値とは異なる価値軸である

---

## 新仮説体系

| ID | 内容 | ステータス |
|----|------|----------|
| H1_inv (primary) | KG multi-op は random より investigable な仮説を生成する | **支持済み** (2回再現) |
| H2_inv (open) | KG multi-op は single-op より investigable な仮説を生成する | **未支持** (C1=0.971 > C2=0.914) |
| H3_inv (open) | cross-domain 仮説は single-domain 仮説より investigability が低いが新規性が高い | **未検証** |

---

## HARKing に対する透明性

- investigability 仮説 (SC-3r) は **run_017 の事後分析 (post-hoc)** から導出された
- run_018 は investigability を primary endpoint として **事前登録** した上で実施した
- run_018 の結果は confirmatory として扱ってよい
- SC-1r から SC_inv_primary への endpoint 変更は、run_017 結果確認後に行われた
- この変更の経緯は `investigability_hypothesis_v2.md` および `investigability_pre_registration.md` に記録されている

---

## 変更しないこと

- SC-1r の FAIL 判定を覆そうとしない
- investigability 優位を「supported novelty も実はある」という主張に拡大しない
- H2_inv (C2 > C1) を現時点では支持された仮説として扱わない
