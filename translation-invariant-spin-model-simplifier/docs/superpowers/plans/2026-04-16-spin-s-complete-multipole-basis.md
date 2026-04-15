# Spin-S 完整多极矩基底实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前矩阵分解路径建立通用 `spin-S` 完整多极矩基底支持，并分阶段把它接入 canonicalize、readable model 与 FeI2 验证流程。

**Architecture:** 先新增通用 `spin-S` 基底生成模块，使 `decompose_local_term.py` 不再只支持 `spin-1/2`。随后让 canonical label 和 term metadata 能稳定表达完整多极矩基底，再逐步接入 readable block 与报告层。FeI2 作为工作目录真实 case 验证对象，验证脚本不要求 git 追踪，但关键结论必须进入 `docs/superpowers/notes/`。

**Tech Stack:** Python 3, `unittest`/`pytest`, 当前 `scripts/simplify/` 模块，docs 下的 spec/plan/notes 文档

---

## 文件结构

**Create:**
- `scripts/simplify/spin_multipole_basis.py`
- `docs/superpowers/notes/2026-04-16-fei2-spin-s-validation.md`

**Modify:**
- `scripts/simplify/decompose_local_term.py`
- `scripts/simplify/canonicalize_terms.py`
- `scripts/simplify/identify_readable_blocks.py`
- `scripts/simplify/assemble_effective_model.py`
- `scripts/output/render_report.py`

**Tests / verification:**
- Repo 内最小契约测试：新增或扩展针对 basis generation、matrix decomposition、canonicalize 的小测试
- 工作目录验证：使用 `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/`

**不纳入 git 追踪：**
- 当前 FeI2 工作目录里的临时测试脚本
- 工作目录里的临时输入转换脚本

## 任务分解

### Task 1：锁定 spin-S 完整基底的最小契约

**Files:**
- Create: `tests/test_spin_multipole_basis.py`
- Modify: `docs/superpowers/plans/2026-04-16-spin-s-complete-multipole-basis.md`

- [ ] **Step 1: 写失败测试，覆盖单站点完整基底维数**

```python
def test_spin_half_basis_has_dimension_four():
    basis = build_spin_multipole_basis("1/2")
    assert len(basis) == 4


def test_spin_one_basis_has_dimension_nine():
    basis = build_spin_multipole_basis(1)
    assert len(basis) == 9


def test_spin_three_half_basis_has_dimension_sixteen():
    basis = build_spin_multipole_basis("3/2")
    assert len(basis) == 16
```

- [ ] **Step 2: 写失败测试，覆盖 rank 范围**

```python
def test_spin_one_basis_contains_rank_zero_to_two():
    basis = build_spin_multipole_basis(1)
    ranks = {entry["rank"] for entry in basis}
    assert ranks == {0, 1, 2}
```

- [ ] **Step 3: 运行测试确认它们先失败**

Run: `python3 -m pytest tests/test_spin_multipole_basis.py -q`
Expected: FAIL，因为 `spin_multipole_basis.py` 还不存在。

- [ ] **Step 4: 提交失败测试基线**

```bash
git add -f tests/test_spin_multipole_basis.py docs/superpowers/plans/2026-04-16-spin-s-complete-multipole-basis.md
git commit -m "test: cover spin-S multipole basis contract"
```

### Task 2：实现通用 spin-S 完整多极矩基底

**Files:**
- Create: `scripts/simplify/spin_multipole_basis.py`
- Modify: `tests/test_spin_multipole_basis.py`

- [ ] **Step 1: 实现自旋量子数解析**

```python
def parse_spin_value(value):
    # 支持 0, 1/2, 1, 3/2, ...
```

- [ ] **Step 2: 实现单站点 Hilbert 空间维度与 rank 范围**

```python
def local_dimension_for_spin(spin):
    return int(2 * spin + 1)


def supported_ranks(spin):
    return list(range(0, int(2 * spin) + 1))
```

- [ ] **Step 3: 实现完整局域算符基底生成**

```python
def build_spin_multipole_basis(spin):
    # 返回完整 d^2 维局域算符基底
```

- [ ] **Step 4: 运行最小基底测试**

Run: `python3 -m pytest tests/test_spin_multipole_basis.py -q`
Expected: PASS

- [ ] **Step 5: 提交基底模块**

```bash
git add scripts/simplify/spin_multipole_basis.py tests/test_spin_multipole_basis.py
git commit -m "feat: add generic spin-S multipole basis"
```

### Task 3：让矩阵分解路径接入 spin-S 完整基底

**Files:**
- Modify: `scripts/simplify/decompose_local_term.py`
- Create: `tests/test_decompose_local_term_spin_s.py`

- [ ] **Step 1: 写失败测试，覆盖 spin-1 单站点矩阵分解**

```python
def test_decompose_spin_one_local_matrix_returns_ranked_labels():
    normalized = {...}
    result = decompose_local_term(normalized)
    assert result["mode"] == "spin-multipole-basis"
    assert any(term["label"].startswith("T") for term in result["terms"])
```

- [ ] **Step 2: 写失败测试，覆盖 spin-3/2 双站点维数检查**

```python
def test_decompose_spin_three_half_two_site_matrix_checks_16x16_local_tensor_shape():
    ...
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python3 -m pytest tests/test_decompose_local_term_spin_s.py -q`
Expected: FAIL

- [ ] **Step 4: 把 `decompose_local_term.py` 改成按 `local_hilbert.dimension` 自动选择 spin-S 基底**

```python
def decompose_local_term(normalized, tolerance=1e-9):
    # matrix path:
    # infer spin from local dimension
    # build multipole basis
    # project matrix
```

- [ ] **Step 5: 运行分解测试**

Run: `python3 -m pytest tests/test_spin_multipole_basis.py tests/test_decompose_local_term_spin_s.py -q`
Expected: PASS

- [ ] **Step 6: 提交矩阵分解扩展**

```bash
git add scripts/simplify/decompose_local_term.py tests/test_decompose_local_term_spin_s.py
git commit -m "feat: extend matrix decomposition to generic spin-S"
```

### Task 4：让 canonicalize 接受完整多极矩标签

**Files:**
- Modify: `scripts/simplify/canonicalize_terms.py`
- Create: `tests/test_canonicalize_spin_s_terms.py`

- [ ] **Step 1: 写失败测试，覆盖 `T<rank>_<component>@<site>` 标签**

```python
def test_canonicalize_accepts_ranked_spin_multipole_labels():
    model = {
        "terms": [
            {"label": "T1_z@0 T1_z@1", "coefficient": 1.0},
            {"label": "T2_a@0", "coefficient": 0.5},
        ]
    }
    canonical = canonicalize_terms(model)
    assert canonical["two_body"]
    assert canonical["one_body"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_canonicalize_spin_s_terms.py -q`
Expected: FAIL

- [ ] **Step 3: 扩展 canonicalize 元数据**

```python
{
    "canonical_label": ...,
    "support": ...,
    "body_order": ...,
    "multipole_rank": ...,
    "multipole_family": ...,
}
```

- [ ] **Step 4: 运行 canonicalize 测试**

Run: `python3 -m pytest tests/test_canonicalize_spin_s_terms.py tests/test_spin_multipole_basis.py tests/test_decompose_local_term_spin_s.py -q`
Expected: PASS

- [ ] **Step 5: 提交 canonicalize 扩展**

```bash
git add scripts/simplify/canonicalize_terms.py tests/test_canonicalize_spin_s_terms.py
git commit -m "feat: canonicalize complete spin-S multipole labels"
```

### Task 5：最小接入 readable / report 层，并记录阶段限制

**Files:**
- Modify: `scripts/simplify/identify_readable_blocks.py`
- Modify: `scripts/simplify/assemble_effective_model.py`
- Modify: `scripts/output/render_report.py`
- Create: `tests/test_spin_s_readable_blocks.py`

- [ ] **Step 1: 写失败测试，要求高阶项至少安全进入 residual**

```python
def test_high_rank_terms_fall_back_to_residual_without_crashing():
    canonical_model = {...}
    readable = identify_readable_blocks(canonical_model)
    assert "residual_terms" in readable
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_spin_s_readable_blocks.py -q`
Expected: FAIL

- [ ] **Step 3: 实现最小安全行为**

```python
# 高阶项暂不强行起物理模板名，保留在 residual
```

- [ ] **Step 4: 运行 readable/report 测试**

Run: `python3 -m pytest tests/test_spin_s_readable_blocks.py -q`
Expected: PASS

- [ ] **Step 5: 在 notes 中写明这一阶段限制**

Write: `docs/superpowers/notes/2026-04-16-fei2-spin-s-validation.md`

内容包括：
- 第一阶段已完成的能力
- 当前高阶项在 readable/report 层的处理方式
- 未完成的 solver 兼容边界

- [ ] **Step 6: 提交最小 readable/report 接入与 notes**

```bash
git add -f docs/superpowers/notes/2026-04-16-fei2-spin-s-validation.md
git add scripts/simplify/identify_readable_blocks.py scripts/simplify/assemble_effective_model.py scripts/output/render_report.py tests/test_spin_s_readable_blocks.py
git commit -m "feat: route generic spin-S multipoles through readable model fallbacks"
```

### Task 6：用当前 FeI2 case 做工作目录验证

**Files:**
- Modify: none required in repo
- Write notes: `docs/superpowers/notes/2026-04-16-fei2-spin-s-validation.md`

- [ ] **Step 1: 在工作目录编写临时验证脚本**

Location: `/data/work/zhli/run/codex/spin-effective-Hamiltonian/FeI2/`

Do not add these scripts to git.

- [ ] **Step 2: 以 `selected_model_candidate = "effective"` 跑 FeI2**

验证目标：
- 文档协议层能选中 `effective`
- matrix/operator 预处理能进入新的 spin-S 分解路径
- `spin-1` 局域结构不会再被误判为 `spin-1/2`

- [ ] **Step 3: 记录实际观察**

写入：
- 哪一步已经通
- 哪一步仍卡住
- 是否是 operator 解析问题、solver 兼容问题、还是高阶项 readable 问题

- [ ] **Step 4: 不提交工作目录脚本，只提交 notes 更新**

```bash
git add -f docs/superpowers/notes/2026-04-16-fei2-spin-s-validation.md
git commit -m "docs: record FeI2 spin-S validation notes"
```

### Task 7：验证收束

**Files:**
- Modify: none expected

- [ ] **Step 1: 运行 repo 内最小契约套件**

Run: `python3 -m pytest tests/test_spin_multipole_basis.py tests/test_decompose_local_term_spin_s.py tests/test_canonicalize_spin_s_terms.py tests/test_spin_s_readable_blocks.py -q`
Expected: PASS

- [ ] **Step 2: 运行现有相邻契约测试**

Run: `python3 -m pytest tests/test_skill_contracts.py tests/test_normalize_input.py tests/test_skill_reference_docs.py -q`
Expected: PASS

- [ ] **Step 3: 核对 notes 已记录当前阶段限制**

Checklist:
- 完整多极矩基底是否已在 Phase 1 实现
- readable 层是否仍有保守 fallback
- solver 兼容边界是否写清

- [ ] **Step 4: 提交最终验证快照**

```bash
git add -f docs/superpowers/notes/2026-04-16-fei2-spin-s-validation.md
git commit -m "test: verify staged spin-S multipole support"
```

## 实施注意事项

- 不要把当前 FeI2 工作目录里的临时脚本加入 git。
- repo 内测试只保留最小契约，不把工作目录验证脚本硬塞进仓库。
- 第一阶段必须实现“完整多极矩基底 + 分解”，但不要误宣称 solver 已完整支持所有高阶项。
- 如果高阶项还没有稳定 readable 名称，宁可进入 residual，也不要乱起物理名字。
