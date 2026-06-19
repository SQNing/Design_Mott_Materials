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

## 4. 接口契约

### 4.1 请求 schema

顶层请求对象必须包含以下字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `model` | object | yes | - | 待编译的原始模型 payload |
| `mode` | enum: `fast`, `certified`, `anytime` | yes | - | 选择快路径、证书路径或双轨路径 |
| `seed` | integer | no | `0` | 随机种子 |
| `budget` | object | yes | - | 资源上限 |
| `thresholds` | object | yes | - | 停止阈值 |
| `routing` | object | no | `{}` | 后端与路径偏好 |

`budget` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `wall_time_sec` | number or null | no | null | 最大墙钟时间 |
| `box_budget` | integer or null | no | null | 最大 branch-and-bound 盒子数 |
| `candidate_starts` | integer or null | no | null | 快路径随机起点数 |
| `fast_iterations` | integer or null | no | null | 快路径局部迭代上限 |

`thresholds` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `gap_tolerance` | number | yes | - | 可接受的证书 gap 上限 |
| `stationarity_tolerance` | number | yes | - | 可接受的流形/驻点残差 |
| `energy_tolerance` | number | yes | - | 可接受的候选能量稳定阈值 |

`routing` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `fast_backend` | string or null | no | null | 首选快路径后端 |
| `proof_backend` | string or null | no | null | 首选证书后端 |
| `proof_strategy` | enum: `proof_only`, `candidate_assisted`, `auto` | mode-dependent | `auto` | 证书路径是否允许/优先使用候选 incumbent |

规则：

- `routing.proof_strategy` 在 `mode = certified` 时必须显式给出，不能省略。
- `routing.proof_strategy = auto` 只在 `mode = anytime` 时生效。
- `routing.proof_strategy` 在 `mode = fast` 时忽略。
- `budget` 中至少有一个限额字段必须非 `null`，否则实现无法做 any-time 调度。
- `routing.fast_backend` 和 `routing.proof_backend` 的优先级高于 `solver_hints.preferred_fast_backend` 和 `solver_hints.preferred_proof_backend`。
- 如果 `routing.*_backend` 为空，则使用 `solver_hints.preferred_*`；如果两者都为空，则由协调器根据 `capabilities` 和默认策略选择。

### 4.2 响应 schema

顶层响应对象必须包含以下字段：

| Field | Type | Required | Nullability | Meaning |
|------|------|----------|-------------|---------|
| `status` | enum: `ok`, `error` | yes | - | 顶层返回状态 |
| `completion` | object | yes | never null | 运行结论与停止原因 |
| `candidate` | object or null | yes | nullable | 启发式可行解；在 `status = error` 时可保留已序列化的诊断快照 |
| `certificate` | object or null | yes | nullable | 下界证书或 bound summary；在 `status = ok` 时必须为对象；在 `status = error` 时可为 `null` 或诊断快照 |
| `provenance` | object | yes | never null | 求解来源与执行路径 |
| `errors` | array or null | no | nullable | 错误列表 |
| `warnings` | array or null | no | nullable | 警告列表 |

`completion` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `status` | enum: `final`, `partial`, `failed` | yes | - | 结果是否完成闭合 |
| `reason` | string or null | yes | null | 停止或退化原因 |
| `stopping_condition` | string or null | yes | null | 具体停止条件 |
| `budget_used` | object | yes | - | 已消耗预算 |
| `budget_remaining` | object or null | yes | null | 剩余预算 |
| `execution_path` | enum: `not_started`, `fast_only`, `proof_only`, `candidate_assisted` | yes | - | 实际执行路径 |

`budget_used` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `wall_time_sec` | number or null | yes | null | 已消耗墙钟时间上限或分配值 |
| `elapsed_wall_time_sec` | number or null | yes | null | 实际已消耗墙钟时间 |
| `box_budget` | integer or null | yes | null | 已消耗或分配的 box 预算 |
| `candidate_starts` | integer or null | yes | null | 已消耗或分配的候选起点数 |
| `fast_iterations` | integer or null | yes | null | 已消耗或分配的 fast 迭代数 |

`budget_remaining` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `wall_time_sec` | number or null | yes | null | 剩余墙钟时间 |
| `box_budget` | integer or null | yes | null | 剩余 box 预算 |
| `candidate_starts` | integer or null | yes | null | 剩余候选起点数 |
| `fast_iterations` | integer or null | yes | null | 剩余 fast 迭代数 |

`candidate` 的最小子字段：

| Field | Type | Required | Nullability | Meaning |
|------|------|----------|-------------|---------|
| `energy` | number | yes when non-null | never null inside candidate | 候选解能量 |
| `state` | object | yes when non-null | never null inside candidate | 候选态 / classical state |
| `witness` | object or null | no | nullable | 可行性或最优性证据 |
| `refinement_history` | array or null | no | nullable | 快路径 / 流形 refinement 轨迹 |
| `source` | string | yes when non-null | never null inside candidate | 候选来源 |

`certificate` 的最小子字段：

| Field | Type | Required | Nullability | Meaning |
|------|------|----------|-------------|---------|
| `status` | enum: `certified`, `partial`, `upper_bound_only`, `lower_bound_only`, `failed` | yes | - | 证书状态 |
| `lower_bound` | number or null | yes | nullable | 全局下界 |
| `upper_bound` | number or null | yes | nullable | 最优已知可行上界 |
| `gap` | number or null | yes | nullable | `upper_bound - lower_bound` |
| `coverage` | object | yes | never null | 证书覆盖范围与搜索摘要 |
| `proof_trace` | object or null | no | nullable | 详细证明轨迹 |

`coverage` 的最小子字段：

| Field | Type | Required | Nullability | Meaning |
|------|------|----------|-------------|---------|
| `processed_boxes` | integer | yes | never null | 已处理盒子数 |
| `pruned_boxes` | integer | yes | never null | 已剪枝盒子数 |
| `retained_boxes` | integer | yes | never null | 已保留盒子数 |
| `split_boxes` | integer | yes | never null | 已分裂盒子数 |
| `max_queue_size` | integer | yes | never null | 队列峰值 |
| `frontier_size` | integer | yes | never null | 当前前沿大小 |
| `frontier` | array | yes | never null | 当前未闭合盒子的精确盒子列表 |
| `global_lower_bound` | number or null | yes | nullable | 证书路径累计下界 |
| `global_upper_bound` | number or null | yes | nullable | 证书路径累计上界 |

`frontier` 的每个条目必须是一个 object，且至少包含：

- `box`
- `lower_bound`
- `upper_bound`
- `depth`
- `status`

`proof_trace` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `status` | enum: `not_run`, `partial`, `complete`, `failed` | yes | - | 证书轨迹状态 |
| `reason` | string or null | yes | null | 停止或失败原因 |
| `steps` | array or null | yes | null | 证书步骤记录 |

`provenance` 的最小子字段：

| Field | Type | Required | Default | Meaning |
|------|------|----------|---------|---------|
| `requested_mode` | enum | yes | - | 请求中的模式 |
| `requested_proof_strategy` | enum or null | yes | null | 请求中的证书策略 |
| `execution_path` | enum | yes | - | 实际执行路径 |
| `fast_backend` | string or null | yes | null | 实际使用的快路径后端 |
| `proof_backend` | string or null | yes | null | 实际使用的证书后端 |
| `compiler_version` | string | yes | - | 编译器版本或标识 |
| `seed` | integer | yes | - | 实际使用的随机种子 |
| `capabilities` | object | yes | - | 编译器产出的能力标签 |
| `budget` | object | yes | - | 实际使用的预算配置 |

`provenance.execution_path` 使用与 `completion.execution_path` 相同的枚举集合。

响应规则：

- `status = ok` 表示返回了一个可解释、可序列化的结果对象，不要求一定闭合 gap。
- `status = error` 表示编译、执行或序列化阶段发生了致命错误，导致正常结果合同无法闭合。
- 在 `status = ok` 的返回中，`certificate` 必须是对象，不能为 `null`。
- 在 `status = error` 的返回中，`candidate` 和 `certificate` 允许保留已序列化的诊断快照，但这些快照只作调试用途，不得被当作正式的 final / certified 结果消费。
- 在 `status = error` 的返回中，`completion.status` 必须是 `failed`，`completion.reason` 必须指向 fatal error，`completion.stopping_condition` 必须写成 `fatal_error` 或等价细分值。
- 在 `status = error` 的返回中，`errors` 必须是非空数组；`warnings` 可为 `null` 或数组。
- 在 `status = error` 的返回中，`provenance` 仍然必须存在，并且必须记录最后已知的执行路径、种子、预算和能力标签；如果错误发生在路由选择之前，则 `provenance.execution_path = not_started`。

### 4.3 结果语义

统一结果对象按以下规则解释：

- `status = ok` 表示返回了一个可解释的结果对象，不要求一定闭合 gap。
- `status = error` 表示编译 / 执行 / 序列化阶段发生了致命错误，导致正常结果合同无法闭合。
- 在 `status = ok` 的返回中，`certificate` 必须是对象，不能为 `null`。
- 在 `status = error` 的返回中，`candidate` 和 `certificate` 可以保留诊断快照，但这些快照不应被当作正式结果消费。
- 如果证明路径已经启动并形成了可序列化的失败摘要，则不要使用 `status = error`；应使用 `status = ok`，并根据是否还保留有用结果，把 `completion.status` 置为 `partial` 或 `failed`。
- `candidate = null` 表示没有发现可行解。
- `certificate = null` 表示没有形成任何可用证书对象。
- 当 `certificate.status = upper_bound_only` 时，说明只形成了可行上界，`certificate.lower_bound` 和 `certificate.gap` 取 `null`，`certificate.upper_bound` 必须等于 `candidate.energy`。
- 当 `certificate.status = lower_bound_only` 时，说明只形成了下界，`certificate.upper_bound` 和 `certificate.gap` 取 `null`。
- 当 `certificate.status = partial` 时，说明上下界都存在但 gap 尚未闭合，`lower_bound` 和 `upper_bound` 都必须是数值，`gap` 必须等于 `upper_bound - lower_bound`。
- 当 `certificate.status = certified` 时，说明 `candidate` 与 `certificate` 的 gap 已在 `thresholds.gap_tolerance` 内闭合，`gap` 必须是数值且满足阈值。
- 当 `certificate.status = failed` 时，说明没有形成任何可用 bound。若 proof path 从未进入，则 `lower_bound`、`upper_bound` 和 `gap` 都取 `null`，`coverage.frontier` 为空数组，`proof_trace = null`。若 proof path 已进入但在形成第一个可用 bound 之前停止，则 `coverage.frontier` 必须保留停止时的 live frontier 精确快照，`proof_trace.status = partial`，`proof_trace.steps` 必须是非空数组，`completion.status = partial`，且 `coverage.frontier_size = len(coverage.frontier)`。
- `completion.status = final` 只在 `certificate.status = certified` 时允许。
- `completion.status = partial` 用于任何有用但未闭合的输出，包括仅有 candidate、仅有 lower bound、或 proof / candidate 已产生可序列化过程但尚未形成可用 bound 的情况。
- `completion.status = failed` 仅在没有产生可用 candidate、没有产生任何可用 bound、也没有产生任何可序列化的 proof frontier / proof trace 时使用。
- `proof_engine.global_upper_bound` 必须被归一化到 `certificate.upper_bound`；`proof_engine.frontier` 必须被归一化到 `certificate.coverage.frontier`。
- `certificate.coverage.frontier_size` 必须等于 `len(certificate.coverage.frontier)`。
- `certificate.coverage.frontier` 是 live queue / stack 的精确快照，不是进度摘要；条目顺序必须与 solver 停止时的处理优先级一致。
- `certificate.coverage.frontier` 的每个条目必须至少包含 `box`, `lower_bound`, `upper_bound`, `depth`, `status` 五个字段，其中 `status` 只能取 `open`、`queued`、`stalled`。
- `proof_trace.steps` 必须是按实际执行顺序序列化的对象数组；每个 step 至少要能表示 `kind`、`decision`、`reason`，并在适用时附带 `box`、`lower_bound`、`upper_bound`。
- `proof_trace.status` 为 `partial` 或 `complete` 时，`steps` 必须是非空数组；`not_run` 时 `steps` 取 `null` 或空数组；`failed` 时 `steps` 可以为空，也可以保留失败前的部分轨迹。
- `certificate.status = failed` 不是空对象的同义词；它表示证明路径返回了结构化失败摘要，但没有形成任何可用 bound。

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

输出约束：

- `completion.execution_path = fast_only`
- `candidate` 应尽量返回；如果快路径没有找到可行解，则 `candidate = null`
- `certificate` 只允许是 `upper_bound_only`、`lower_bound_only`、`partial`、`failed`，或在 fast 自身给出 exactness 证据时为 `certified`
- 快模式不会在 fast 失败后自动启动 Proof Engine
- 若只有 candidate，则 `certificate.status = upper_bound_only`
- 若只有 lower bound，则 `certificate.status = lower_bound_only`
- 若 candidate 和 lower bound 都有但未闭合 gap，则 `certificate.status = partial`
- 若 candidate 和 certificate 都没有，则 `certificate.status = failed`
- `completion.status = partial` 表示有 candidate、只有 lower bound、candidate 和 lower bound 未闭合，或有其他可复用但未闭合的证据
- `completion.status = failed` 仅表示既没有 candidate 也没有任何 bound
- `completion.status = final` 仅当 Fast Engine 自身直接给出 exactness 证据时允许

### 5.2 `certified`

Proof Engine 为主，候选生成是否参与由 `routing.proof_strategy` 明确指定。

适用场景：

- 需要尽可能强的下界证书
- 接受更慢的运行时间

执行约束：

- 当 `routing.proof_strategy = proof_only` 时，Proof Engine 不依赖 Fast Engine 的 incumbent。
- 当 `routing.proof_strategy = candidate_assisted` 时，协调器先尝试 Fast Engine，再把得到的 incumbent 喂给 Proof Engine；如果 Fast Engine 没产出 candidate，则自动降级为 proof-only 路径，但必须在 `provenance.execution_path` 中记录真实执行路径。
- 当 `routing.proof_strategy = candidate_assisted` 但 Fast Engine 没产出 candidate 时，仍然可以继续 proof-only 求证，不算错误。
- `completion.status = final` 只在证书闭合 gap 时允许。
- `completion.status = partial` 用于只有 lower bound、只有 candidate、proof 未闭合但仍产出有用结果、或 proof 只留下可序列化 frontier / trace 但尚未形成 bound 的情况。
- `completion.status = failed` 仅在 candidate、lower bound、frontier、trace 都不存在，或者底层 fatal error 已经把正常合同打断时使用。

### 5.3 `anytime`

默认模式。

规则：

- `anytime` 有两类 routing family：
  - `auto` / `candidate_assisted` 是 fast-first family，默认先跑 Fast Engine，再尽力补证。
  - `proof_only` 是 proof-first family，直接进入 Proof Engine，不先跑 Fast Engine。
- 任一侧都可以先结束
- 返回结果中必须清晰区分启发式和证书部分

执行约束：

- `routing.proof_strategy = auto` 时，协调器先尝试 Fast Engine；若得到 candidate，则使用 candidate-assisted proof；若没有 candidate，则自动退化为 proof-only。
- `routing.proof_strategy = proof_only` 时，协调器跳过 Fast Engine，直接进入 Proof Engine。
- `completion.execution_path` 必须记录真实执行路径，而不是请求中的偏好。
- `completion.status` 的判定规则与 `certified` 相同，但 `anytime` 优先保留 candidate，再尽力补证。

### 5.4 模式矩阵

| 模式 | `routing.proof_strategy` | Fast Engine | Proof Engine | `provenance.execution_path` | `completion.status` when exact | `completion.status` when only candidate | `completion.status` when only lower bound | `completion.status` when nothing found |
|------|--------------------------|-------------|--------------|------------------------------|-------------------------------|-----------------------------------------|-------------------------------------------|------------------------------------------|
| `fast` | ignored | required | forbidden | `fast_only` | `final` only if fast itself proves exactness | `partial` | `partial` | `failed` |
| `certified` | `proof_only` | forbidden | required | `proof_only` | `final` | `partial` | `partial` | `failed` |
| `certified` | `candidate_assisted` | required if available | required | `candidate_assisted` or `proof_only` if fallback occurs | `final` | `partial` | `partial` | `failed` |
| `anytime` | `auto` | required if capabilities/budget permit | required or fallback | `candidate_assisted`, `proof_only`, or `fast_only` | `final` | `partial` | `partial` | `failed` |
| `anytime` | `proof_only` | forbidden | required | `proof_only` | `final` | `partial` | `partial` | `failed` |
| `anytime` | `candidate_assisted` | required if available | required | `candidate_assisted` or `proof_only` if fallback occurs | `final` | `partial` | `partial` | `failed` |

规则：

- `routing.proof_strategy` must be explicit for `mode = certified`.
- `routing.proof_strategy = auto` is only valid for `mode = anytime`.
- `routing.proof_strategy = proof_only` or `candidate_assisted` is valid for `mode = anytime`.
- `provenance.execution_path` must record the actual path taken, not the requested preference.
- If a requested `candidate_assisted` path has no candidate, the actual execution path is `proof_only`.
- `fast` mode never falls back to Proof Engine after a fast failure.
- `mode = anytime` 里的 `proof_only` 行是 proof-first family，不是和 fast-first family 冲突；它表示用户主动选择 proof-first 路径。
- 表中的 `nothing found` 仅指 candidate、lower bound、frontier、proof trace 都不存在；若 proof 已进入并保留了 frontier / trace，但没有 bound，则该行不适用，应按 `partial` 解释。

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

- 在 `fast` 模式下，不允许自动启动 Proof Engine 作为失败回退
- 如果快路径没有产出 candidate，则 `candidate = null`
- 如果快路径没有产出任何 bound，则 `certificate.status = failed`
- 如果快路径只产出 candidate，则 `certificate.status = upper_bound_only`
- 如果快路径只产出 lower bound，则 `certificate.status = lower_bound_only`
- 如果快路径同时产出 candidate 和 lower bound 但 gap 未闭合，则 `certificate.status = partial`
- 只有 `certified(candidate_assisted)` 或 `anytime` 的可选路径才允许在快路径失败后继续进入 Proof Engine
- 在 `fast` 模式下，fast 失败后不应继续尝试证书路径，即使有预算剩余

### 7.2 证书路径失败

如果 proof path 失败：

- 如果至少已有 candidate，则保留 candidate，并令 `certificate.status` 为 `upper_bound_only`、`lower_bound_only` 或 `partial`，取决于证书路径已经形成的 bound
- 如果没有 candidate 但已有下界，则保留下界，并令 `certificate.status = lower_bound_only`
- 如果没有 candidate 也没有下界：
  - 若 proof path 从未进入，则 `certificate.status = failed`，`proof_trace = null`，`coverage.frontier = []`
  - 若 proof path 已进入但未形成任何可用 bound，则 `certificate.status = failed`，但必须保留 `proof_trace` 的部分步骤与 `coverage.frontier` 的精确快照
- `proof_trace` 应保留到失败点的部分轨迹；如果未进入 proof path，则为 `null`
- `coverage.frontier` 必须保留当前 frontier 的精确内容，不能写成摘要占位

### 7.3 预算耗尽

预算耗尽时：

- 保留当前最优 candidate
- 保留已确认的 lower bound
- 暴露 `gap`
- 暴露已经覆盖的搜索区域
- `completion.status` 应为 `partial`
- `completion.reason` 应明确写为预算耗尽或时间耗尽

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
   - `certificate.coverage.frontier_size` 必须等于 `len(certificate.coverage.frontier)`

3. 退化语义
   - 预算不足时返回部分结果
   - 证书失败时不丢弃启发式结果
   - 黑盒模型只走启发式通道

4. 结果稳定性
   - 相同输入与相同 seed 下，模式选择一致
   - 关键字段格式稳定
   - capability tags 不随无关代码变动漂移

## 9. 最小示例

### 9.1 请求示例

```json
{
  "model": {
    "model_kind": "cpn_translation_invariant",
    "local_dimension": 2,
    "bond_tensors": []
  },
  "mode": "anytime",
  "seed": 0,
  "budget": {
    "wall_time_sec": 300,
    "box_budget": 64,
    "candidate_starts": 16,
    "fast_iterations": 200
  },
  "thresholds": {
    "gap_tolerance": 0.001,
    "stationarity_tolerance": 1e-06,
    "energy_tolerance": 1e-06
  },
  "routing": {
    "fast_backend": "cpn-generalized-lt",
    "proof_backend": "interval-branch-and-bound",
    "proof_strategy": "auto"
  }
}
```

### 9.2 部分结果示例

```json
{
  "status": "ok",
  "completion": {
    "status": "partial",
    "reason": "budget_exhausted",
    "stopping_condition": "box_budget_reached",
    "budget_used": {
      "wall_time_sec": 300,
      "elapsed_wall_time_sec": 300,
      "box_budget": 64,
      "candidate_starts": 16,
      "fast_iterations": 200
    },
    "budget_remaining": null,
    "execution_path": "candidate_assisted"
  },
  "candidate": {
    "energy": -1.234,
    "state": { "kind": "classical_state" },
    "witness": null,
    "refinement_history": [],
    "source": "cpn-generalized-lt"
  },
  "certificate": {
    "status": "partial",
    "lower_bound": -1.5,
    "upper_bound": -1.234,
    "gap": 0.2660000000000001,
    "coverage": {
      "processed_boxes": 64,
      "pruned_boxes": 12,
      "retained_boxes": 18,
      "split_boxes": 34,
      "max_queue_size": 17,
      "frontier_size": 1,
      "frontier": [
        {
          "box": {
            "names": ["q0"],
            "lower": [0.0],
            "upper": [0.5],
            "depth": 3
          },
          "lower_bound": -1.5,
          "upper_bound": null,
          "depth": 3,
          "status": "queued"
        }
      ],
      "global_lower_bound": -1.5,
      "global_upper_bound": -1.234
    },
    "proof_trace": {
      "status": "partial",
      "reason": "budget_exhausted",
      "steps": [
        {
          "kind": "split",
          "decision": "continue",
          "reason": "box_pending",
          "box": {
            "names": ["q0"],
            "lower": [0.0],
            "upper": [0.5],
            "depth": 3
          },
          "lower_bound": -1.5,
          "upper_bound": -1.234
        },
        {
          "kind": "terminate",
          "decision": "stop",
          "reason": "budget_exhausted",
          "box": {
            "names": ["q0"],
            "lower": [0.0],
            "upper": [0.5],
            "depth": 3
          },
          "lower_bound": -1.5,
          "upper_bound": -1.234
        }
      ]
    }
  },
  "provenance": {
    "requested_mode": "anytime",
    "requested_proof_strategy": "auto",
    "execution_path": "candidate_assisted",
    "fast_backend": "cpn-generalized-lt",
    "proof_backend": "interval-branch-and-bound",
    "compiler_version": "v1",
    "seed": 0,
    "capabilities": {
      "supports_q_optimization": true,
      "supports_cp_manifold": true,
      "supports_interval_bounds": true,
      "supports_sos_bounds": false,
      "has_translation_symmetry": true,
      "is_local_tensor_payload": true
    },
    "budget": {
      "wall_time_sec": 300,
      "box_budget": 64,
      "candidate_starts": 16,
      "fast_iterations": 200
    }
  },
  "warnings": null,
  "errors": null
}
```

## 10. 分阶段实现建议

建议按三步做：

1. 先把 unified result schema 和 mode router 稳住。
2. 再把 fast path 的 nonsmooth q 优化和 CP 流形 refinement 接进去。
3. 最后增强 proof path，引入更强的 interval / SOS 证书后端。

这样可以保证系统在每个阶段都能返回“有用结果”，不会因为证书还没做完就卡死。

## 11. 结论

这个设计的本质是把 GLT 从“一个方法”升级成“一个 anytime 计算框架”：

- 快路径负责尽量快地找到很准的最小值候选。
- 证书路径负责尽量慢但尽量可靠地给全局下界证书。
- 协调器负责在预算和结果之间做明确路由。

最终目标不是某一个子算法绝对最强，而是任意可编译模型都能进入同一条管线，并且总能得到一个语义清晰的结果。
