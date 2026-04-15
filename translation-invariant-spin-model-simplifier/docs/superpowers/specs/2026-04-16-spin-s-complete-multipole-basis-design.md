# 通用 Spin-S 完整多极矩基底设计

**日期：** 2026-04-16

## 目标

为 `translation-invariant-spin-model-simplifier` 增加对通用 `spin-S` 局域空间的支持，
其中 `S = 0, 1/2, 1, 3/2, ...`。本设计的长期目标不是只支持低阶自旋算符，而是支持
**完整多极矩基底**，并逐步把这套基底接入当前的矩阵分解、canonicalize、可读模型、
报告和后续 classical / LSWT 路径。

当前 FeI2 case 作为第一批真实验证对象，但架构设计不能写成只服务于 `spin-1` 特例。

## 用户确认方向

- 目标是通用 `spin-S` 支持，而不是只修 FeI2。
- 长期目标是支持完整多极矩基底，而不是只支持 `Sx, Sy, Sz` 或只支持到二次项。
- 实现采用分阶段推进。
- 当前 FeI2 case 可以作为主验证对象。
- 当前 case 的测试脚本和临时输入整理脚本不要求 git 追踪。
- `specs`、`plans`、`implementation` 和 `notes` 必须放在 `docs/` 下。

## 问题陈述

当前矩阵分解路径集中在 `scripts/simplify/decompose_local_term.py`，其局限非常明确：

- 只支持 `representation.kind == "matrix"` 的实际分解；
- `operator` 输入只被包装成 `raw-operator`，无法继续进入 canonicalize；
- 局域 Hilbert 空间维度被硬编码为 `2`；
- 本质上只支持 `spin-1/2` 的 `I, Sx, Sy, Sz` 张量积基底。

因此，当前路径无法处理：

- `spin-1` 的单离子二次项与更高多极结构；
- `spin-3/2` 及以上的一般局域算符空间；
- 依赖完整多极矩表示的真实材料有效模型；
- FeI2 这类需要 `spin-1` 语义的 case。

## 关键术语与完整性定义

### 1. 局域 Hilbert 空间

对单站点自旋 `S`，局域 Hilbert 空间维度为：

```text
d = 2S + 1
```

### 2. 局域算符空间

单站点线性算符空间维度为：

```text
d^2 = (2S + 1)^2
```

### 3. “完整多极矩基底”的含义

本设计中“完整多极矩基底”是指：

- 单站点局域算符基底完整张成整个 `d x d` 复矩阵空间；
- 在物理分层上包含从 `rank 0` 到 `rank 2S` 的全部局域多极矩；
- 第一阶段就必须把这套完整基底的构造与矩阵分解能力定义清楚。

这意味着：

- `spin-1/2`：包含 `rank 0, 1`
- `spin-1`：包含 `rank 0, 1, 2`
- `spin-3/2`：包含 `rank 0, 1, 2, 3`
- 一般 `spin-S`：包含 `rank 0` 到 `rank 2S`

这里的“分阶段实现”不是把目标降成“不做完整多极矩”，而是：

- 第一阶段先完成完整基底的生成与矩阵分解；
- 后续阶段再逐步把这套完整基底接入当前 pipeline 的可读分组、报告语义与求解路径。

## 方案比较

### 方案 1：只把当前 `spin-1/2` 基底推广到 `Sx, Sy, Sz`

优点：

- 实现最简单；
- 对少数 Heisenberg 型模型足够。

缺点：

- 无法代表 `spin-1` 的自然局域结构；
- 无法承诺支持完整多极矩基底；
- 会在 `spin-1`、`spin-3/2` 与更高自旋上很快失真。

### 方案 2：支持 dipole 加常见二次项

优点：

- 比方案 1 更贴近 FeI2；
- 工程风险比完整基底小。

缺点：

- 仍然不是完整局域算符空间；
- 对一般 `S` 的扩展仍要返工；
- 不能作为长期统一表示层。

### 方案 3：以完整多极矩基底为总目标，分阶段实现

优点：

- 与通用 `spin-S` 目标一致；
- 不需要后续推翻标签体系；
- 能把 FeI2 放在通用框架中，而不是特例逻辑中。

缺点：

- 基底设计、标签体系与 downstream 兼容都更复杂；
- 第一阶段也必须做严谨的归一化与规范化约定；
- readable blocks 与 solver 兼容需要后续阶段持续跟进。

## 推荐方案

采用方案 3。

本设计明确把“支持完整多极矩基底”作为**长期目标**，并要求第一阶段就完成：

- 通用 `spin-S` 完整局域算符基底的构造；
- 基于该完整基底的矩阵分解；
- 能进入当前 canonical pipeline 的稳定标签形式。

但本设计同时明确约束：

- 第一阶段不承诺 downstream 的所有模块已经完整吸收全部高阶多极矩语义；
- 第一阶段完成的是“完整基底 + 分解 + 稳定标签”，不是“一步完成所有求解与可视化支持”。

## 表示方案

### 1. 内部表示原则

内部表示必须满足：

- 对任意 `spin-S` 都能完整张成局域算符空间；
- 对多站点项能够自然形成张量积基底；
- 对后续 canonicalize 保持统一的 `factor@site` 标签风格。

### 2. 标签体系

建议内部 canonical label 使用：

```text
T<rank>_<component>@<site>
```

例如：

- `T0_0@0`
- `T1_x@0`
- `T1_y@0`
- `T1_z@0`
- `T2_a@0`
- `T2_b@0`

其中：

- `rank=0` 对应单位类；
- `rank=1` 对应 dipole；
- `rank>=2` 对应更高多极矩。

对 dipole 层保留稳定别名映射：

- `T1_x -> Sx`
- `T1_y -> Sy`
- `T1_z -> Sz`

但 spec 不要求在第一阶段把所有高阶项都翻译成固定人类语义名称。

### 3. 多站点项

多站点项继续沿用当前 factor-product 风格：

- `T1_z@0 T1_z@1`
- `T2_a@0 T1_x@1`
- `T2_a@0 T2_b@1`

这样可以最大限度兼容现有 `canonicalize_terms.py` 的标签解析逻辑，而不是重写整条管线。

### 4. 归一化要求

spec 要求局域基底默认采用 Hilbert-Schmidt 正交归一化。理由是：

- 不同 `rank` 与不同 `S` 的基元尺度必须可比较；
- 后续 `absolute_weight`、`relative_weight` 和 `low_weight` 判断需要一致尺度；
- 如果没有统一归一化，高阶多极矩项会在数值上失真。

## 分阶段实现

### Phase 1：完整多极矩基底与矩阵分解基础层

目标：

- 新增通用 `spin-S` 局域算符基底生成模块；
- 让 `decompose_local_term.py` 支持任意 `S` 的矩阵分解；
- 输出稳定 canonical label；
- 使 `matrix` 路径不再只支持 `spin-1/2`。

建议文件：

- 新增 `scripts/simplify/spin_multipole_basis.py`
- 可选新增 `scripts/simplify/spin_multipole_labels.py`
- 修改 `scripts/simplify/decompose_local_term.py`

这一阶段的限制必须明确写在 spec 中：

- 第一阶段完成“完整基底 + 分解”，不是完整 readable 语义；
- 第一阶段不要求所有 solver 已经理解所有高阶多极矩；
- 第一阶段不要求 `operator` 文本解析与 `matrix` 分解同步完成。

### Phase 2：canonicalize 与标签分层语义

目标：

- 让完整多极矩标签进入 `canonicalize_terms.py`；
- 为 term family 增加 rank 与 multipole 类别元数据；
- 保持与现有 `factor@site` 风格兼容。

建议文件：

- 修改 `scripts/simplify/canonicalize_terms.py`
- 可选新增 `scripts/simplify/multipole_term_families.py`

这一阶段的限制：

- readable alias 先覆盖最常见低阶对象；
- 高阶对象允许先保留规范标签。

### Phase 3：readable blocks 与报告层

目标：

- 扩展 `identify_readable_blocks.py`
- 保持 `H_main + H_low_weight + H_residual` 输出结构；
- 对高阶项做到“不丢失、不乱命名、可显式显示 rank/support”

建议文件：

- 修改 `scripts/simplify/identify_readable_blocks.py`
- 修改 `scripts/simplify/assemble_effective_model.py`
- 修改 `scripts/output/render_report.py`

这一阶段的限制：

- 如果尚未形成稳定物理模板名，高阶项应进入 residual，而不是被错误归类。

### Phase 4：FeI2 与真实 case 验证

目标：

- 使用当前 FeI2 case 验证 `spin-1` 路径；
- 作为第一批真实材料验证对象；
- 明确 classical / LSWT 的当前兼容边界。

验证策略分两类：

#### 仓库内最小契约测试

这些测试需要 git 追踪，覆盖：

- 完整基底生成；
- 矩阵分解；
- canonicalize 基本通路；
- 必要的 readable grouping 基础行为。

#### 工作目录真实 case 验证

这些测试以当前 FeI2 工作目录为主：

- 可以使用临时脚本；
- 可以使用临时输入整理文件；
- 不要求 git 追踪；
- 但关键观察、限制和结论必须写入 `docs/superpowers/notes/` 或 implementation notes。

### Phase 5：更高自旋与更广 case 扩展

目标：

- 用 `S=3/2` 及更高 `S` 继续压测；
- 检查标签规模、性能、报告可读性和 solver 兼容边界；
- 为后续更多真实 case 打基础。

## 需要明确写入 spec 的限制

以下限制必须在 spec 中显式写清，避免误解：

1. 第一阶段的“完整”是指**完整多极矩基底的构造与矩阵分解能力**，不是指所有 downstream 模块已经完整支持所有高阶项。
2. `matrix` 分解路径与 `operator` 文本解析路径可以阶段性不同步。
3. 支持完整多极矩基底，并不自动等价于 classical / LSWT 已经支持所有这些项的物理求解。
4. FeI2 是第一批 `spin-1` 验证对象，但架构不能写成只服务 `spin-1`。
5. 仓库内回归测试与工作目录真实 case 验证是两套互补机制，不能混淆。
6. 当前 case 的测试脚本、临时转换脚本和调试输入可以不纳入 git，但文档化结论必须保留在 `docs/`。

## 非目标

- 不在本设计中一次性重写整个 classical / LSWT 求解器，使其立刻完整吸收所有高阶多极矩项；
- 不把 FeI2 写成硬编码特例；
- 不把任意 `2S+1` 局域空间与任意材料语义自动等同，而不记录限制；
- 不为了报告美观而丢弃或误命名高阶多极矩项。

## 测试与文档落点

### docs 目录

- `docs/superpowers/specs/`：正式设计
- `docs/superpowers/plans/`：实施计划
- `docs/superpowers/notes/`：FeI2 case 验证笔记、限制记录、实施观察

### git 追踪策略

- 设计、计划、实施记录、说明笔记：进入 `docs/`
- 仓库内最小契约测试：可 git 追踪
- 当前工作目录下的 FeI2 主验证脚本与临时测试脚本：不强制 git 追踪

## 风险

- 完整多极矩基底一旦标签体系设计不稳，后续 canonicalize 和 readable grouping 会反复返工；
- 高阶多极矩的数量随 `S` 增大会显著膨胀，可读性和性能都要受控；
- 如果第一阶段不把“完整基底”与“downstream 部分支持”区分清楚，后续会高估当前能力；
- 若让 FeI2 特例主导架构，通用 `spin-S` 路径会退化成材料专用实现。
