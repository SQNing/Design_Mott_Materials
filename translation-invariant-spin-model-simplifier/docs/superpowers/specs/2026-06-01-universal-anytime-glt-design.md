# Universal Anytime GLT 设计稿

## 1. 目标

本设计定义一个“通用、双轨、anytime”的 GLT 求解框架，面向任意可被编译为统一局域张量 / Hamiltonian payload 的模型。

核心目标有三个：

1. 尽快给出一个很准的可行解，也就是高质量上界。
2. 在允许的预算内尽量给出全局最小值证书，也就是可靠下界与 gap。
3. 当预算不足时，仍然返回结构清晰的部分结果，明确区分“已证部分”和“启发式部分”。

这里的“任何 model”只指能够先被编译成统一中间表示的模型。纯黑盒目标函数不进入证书路径，只能作为启发式候选输入。

## 2. 设计原则

- GLT 不是单一算法，而是一条求解管线。
- 上界和下界必须分层保存，不能互相污染。
- 快路径和证书路径都要保留独立 provenance。
- 统一输出必须显式标注 `candidate`、`certificate`、`completion`、`provenance`。
- 任何退化都要是显式退化，不允许悄悄把启发式结果伪装成证书。

## 3. 总体架构

系统分成四层：

1. `Model Compiler`
2. `Fast Engine`
3. `Proof Engine`
4. `Anytime Coordinator`

### 3.1 Model Compiler

职责是把输入模型规范化成 canonical payload，并附带 capability tags。

最小规范化输出必须包含以下字段：

- `canonical_model`: dict
- `capabilities`: dict
- `objective_oracle`: callable descriptor or serializable handle
- `structure_summary`: dict
- `solver_hints`: dict

`canonical_model` 的最小子字段：

- `model_kind`: string
- `local_dimension`: integer, strictly positive
- `bond_tensors`: list of bond records
- `structure`: dict with the geometric metadata needed for routing
- `symmetry_tags`: list of strings, possibly empty

每个 `bond_tensor` 记录至少要有：

- `source`: integer
- `target`: integer
- `R`: length-3 integer vector
- `tensor`: serialized complex tensor

`capabilities` 的最小子字段：

- `supports_q_optimization`: bool
- `supports_cp_manifold`: bool
- `supports_interval_bounds`: bool
- `supports_sos_bounds`: bool
- `has_translation_symmetry`: bool
- `is_local_tensor_payload`: bool

`structure_summary` 的最小子字段：

- `structural_dimension`: integer
- `magnetic_site_count`: integer
- `active_axes`: list of integers
- `description`: string

`solver_hints` 的最小子字段：

- `preferred_fast_backend`: string or null
- `preferred_proof_backend`: string or null
- `weight_bound`: number or null
- `max_supercell_shape`: list of 3 integers or null

### 3.2 Fast Engine

职责是尽快找到好的候选解，而不是证明最优。

推荐分两级：

1. `q / eigenvalue refinement`
   - 适合具有平移或傅里叶结构的模型。
   - 采用 mesh seed + 多起点局部优化 + nonsmooth refinement。
   - 目标是尽快找到很好的 `q_vector`、权重 `p_weights`、局域候选态。

2. `CP manifold refinement`
   - 适合局域态可以写成 `CP^(N-1)` 的模型。
   - 采用 manifold / Riemannian 优化，把候选解抛光到更好的可行点。
   - 目标是提高 upper bound 的质量，而不是改变证书语义。

Fast Engine 只输出候选可行解与启发式上界，不输出最终证书。

### 3.3 Proof Engine

职责是给出 lower bound 和 gap certificate。

建议默认主线是：

- interval branch-and-bound
- box-level lower bound evaluation
- incumbent-driven pruning

可选增强后端：

- SOS / moment-SDP hierarchy
- 适用于小规模或结构足够多项式化的模型

注意：SOS / moment-SDP 在本设计中是预留增强后端，不作为第一阶段实现基线。

Proof Engine 只输出：

- `lower_bound`
- `global_upper_bound`
- `gap`
- `status`
- `frontier`
- `proof_trace`

它不能把候选能量写成下界。

### 3.4 Anytime Coordinator

职责是调度 fast / proof 两条线，并按预算自动切换。

推荐策略：

1. 先跑 Fast Engine，拿到一个尽早可用的 incumbent。
2. 立刻把 incumbent 喂给 Proof Engine，作为 upper bound。
3. 证书路径持续收紧 gap。
4. 如果在预算内达到阈值，则升级为 `final`。
5. 如果预算不够，则返回 `partial`，但所有结果都要标明来源。

## 4. 结果契约

统一结果对象建议分成四块：

### 4.1 `candidate`

保存启发式可行解：

- `energy`
- `state`
- `witness`
- `refinement_history`
- `source`

`candidate` 的最小空值规则：

- 没有可行候选时，`candidate` 取 `null`
- 有候选但没有完整 witness 时，`witness` 可为 `null`
- `energy` 必须是 candidate 自身的能量，不得被证书下界覆盖

### 4.2 `certificate`

保存证书信息：

- `lower_bound`
- `upper_bound`
- `gap`
- `status`
- `coverage`
- `proof_trace`

`certificate` 的最小空值规则：

- 没有证书时，`certificate` 取 `null`
- 证书仍在进行中时，`status = partial`
- `lower_bound` 和 `upper_bound` 都必须是证书语义，不得混入候选能量

### 4.3 `completion`

保存运行状态：

- `status` 取值建议为 `final`、`partial`、`failed`
- `reason`
- `budget_used`
- `budget_remaining`
- `stopping_condition`

`completion` 的最小空值规则：

- 所有返回都应带 `completion`
- 即使只有 candidate，没有 certificate，也必须说明为什么证书缺失
- `budget_remaining` 在非预算驱动场景下可为 `null`

### 4.4 `provenance`

保存求解来源：

- `compiler_version`
- `fast_backend`
- `proof_backend`
- `selected_mode`
- `capabilities`
- `seed`
- `budget`

`provenance` 在所有非错误返回中都必须存在。

## 5. 模式与路由

入口统一支持三种模式：

1. `fast`
2. `certified`
3. `anytime`

### 5.1 `fast`

只跑 Fast Engine。

适用场景：

- 需要尽快拿到一个很好的候选解
- 不要求证书

### 5.2 `certified`

只跑 Proof Engine，或先跑最小化的候选生成再进入证明流程。

适用场景：

- 需要尽可能强的下界证书
- 接受更慢的运行时间

### 5.3 `anytime`

默认模式。

规则：

- 先快后证
- 任一侧都可以先结束
- 返回结果中必须清晰区分启发式和证书部分

### 5.4 模式矩阵

| 模式 | 是否必须先跑 Fast Engine | 是否允许只跑 Proof Engine | 失败时的返回 |
|------|--------------------------|-----------------------------|--------------|
| `fast` | 是 | 否 | 返回 `candidate`，`certificate = null` |
| `certified` | 否 | 是 | 若能直接证明则返回 `certificate`；若需要候选但失败，则返回 `failed` 或 `partial`，并说明原因 |
| `anytime` | 是 | 否 | 返回当前最好 `candidate` 与当前最好 `certificate`，任一侧中断都保留已完成部分 |

`certified` 不是强制先生成候选的模式；它可以证明优先，也可以在需要时使用最小候选作为剪枝辅助，但这两条路径必须在实现中显式区分。

## 6. 与现有代码的对应关系

现有实现已经给出了可复用骨架：

- `scripts/classical/cpn_generalized_lt_solver.py`
  - 适合作为 fast path 的 `q / eigenvalue refinement` 雏形。
- `scripts/classical/cpn_local_ray_solver.py`
  - 适合作为 `CP^(N-1)` manifold refinement 雏形。
- `scripts/classical/certified_glt/relaxed_bounds.py`
  - 适合作为 box-level relaxed bounds 和优先级计算。
- `scripts/classical/certified_glt/branch_and_bound.py`
  - 适合作为证书主循环。
- `scripts/classical/certified_glt/certify_cpn_glt.py`
  - 适合作为 anytime coordinator 的主入口。
- `scripts/cli/solve_pseudospin_orbital_pipeline.py`
  - 适合作为统一模式切换的 CLI 入口。

## 7. 错误处理与退化策略

设计上必须接受“不完整结果”。

### 7.1 快路径失败

如果 fast path 失败：

- 仍然允许 proof path 独立运行
- 返回 `candidate = null`
- 只要证书能跑，就返回 `certificate`

### 7.2 证书路径失败

如果 proof path 失败：

- 保留 fast path 的 incumbent
- 将结果标记为 `partial`
- 明确说明证书为什么中断

### 7.3 预算耗尽

预算耗尽时：

- 保留当前最优 candidate
- 保留已确认的 lower bound
- 暴露 `gap`
- 暴露已经覆盖的搜索区域

### 7.4 不支持的模型结构

如果模型无法编译到任何已知后端：

- 仍然返回编译失败原因
- 仍然返回最小可用的结构摘要
- 不伪造证书

## 8. 测试策略

测试应覆盖四类行为：

1. 模式选择
   - `fast` 是否只走 fast path
   - `certified` 是否只走 proof path 或按规则走最小候选生成
   - `anytime` 是否按结果和预算切换

2. 契约隔离
   - `lower_bound` 不能被候选能量覆盖
   - `candidate.energy` 不能冒充证书下界
   - `partial` 结果必须携带 provenance

3. 退化语义
   - 预算不足时返回部分结果
   - 证书失败时不丢弃启发式结果
   - 黑盒模型只走启发式通道

4. 结果稳定性
   - 相同输入与相同 seed 下，模式选择一致
   - 关键字段格式稳定
   - capability tags 不随无关代码变动漂移

## 9. 分阶段实现建议

建议按三步做：

1. 先把 unified result schema 和 mode router 稳住。
2. 再把 fast path 的 nonsmooth q 优化和 CP 流形 refinement 接进去。
3. 最后增强 proof path，引入更强的 interval / SOS 证书后端。

这样可以保证系统在每个阶段都能返回“有用结果”，不会因为证书还没做完就卡死。

## 10. 结论

这个设计的本质是把 GLT 从“一个方法”升级成“一个 anytime 计算框架”：

- 快路径负责尽量快地找到很准的最小值候选。
- 证书路径负责尽量慢但尽量可靠地给全局下界证书。
- 协调器负责在预算和结果之间做明确路由。

最终目标不是某一个子算法绝对最强，而是任意可编译模型都能进入同一条管线，并且总能得到一个语义清晰的结果。
