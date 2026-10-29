# Agent 驱动的研究流程

本入口把已有输入规范化、完整 Hamiltonian 对称性检查、可读表达、数值求解与报告接在同一个可恢复任务中。宿主 agent 负责理解研究问题、解释诊断和选择下一步。项目不启动新的 LLM 服务，也不需要文献登记表才能研究新模型。

阶段一的简化是保真整理。小系数项仍进入完整求解；未测量的重建误差为 null，assessment 为 not_assessed。第二阶段增加独立的物理简化候选和对照验证，见 [物理简化协议](physical-reductions.md)。第三阶段用相互作用干预、观测量响应和假设检验支持物理解释，见 [机制研究协议](mechanism-workflow.md)。完整模型单独保留，结论限定于实际计算范围。

## 公开入口

从项目根目录执行，使用装有 NumPy、SciPy 的 Python：

~~~sh
python scripts/cli/research_workflow.py prepare --request request.json --run-dir RUN
python scripts/cli/research_workflow.py status --run-dir RUN
python scripts/cli/research_workflow.py step --run-dir RUN --action action.json
python scripts/cli/research_workflow.py report --run-dir RUN --output-dir REPORT
~~~

step 默认返回后台 worker 标识；追加 --wait 可等本次动作结束。宿主退出后 worker 继续运行，后续进程用同一 RUN 查询或接续。这个接口使用 Linux /proc、文件锁和进程组；它不是集群调度器。宿主应遵守机器的运行政策，较大计算在计算节点上执行。

Python 对应接口位于 scripts/research/workflow.py 与 scripts/research/report.py：

~~~python
prepare_research_task(request, run_dir)
inspect_research_task(run_dir)
execute_research_action(run_dir, action, wait=False)
render_research_report(run_dir, output_dir)
~~~

## 研究请求

~~~json
{
  "question": "寻找一个有限周期超胞参考态，并检查指定波矢处的谐波稳定性。",
  "model": {"schema_version": "lattice-term-contract/v1"},
  "requested_tasks": ["classical_ground_state", "harmonic_spectrum"],
  "budget": {
    "max_solver_runs": 8,
    "max_wall_time_seconds": 180,
    "max_memory_mb": 2048
  }
}
~~~

示例中的 model 要替换为完整 lattice-term-contract/v1 或 canonical-hamiltonian/v1；不能只保留 schema 字段。也可使用 source.path 读结构化模型，或 source.kind=text/document/latex 配合 source.text/source.path 输入 UTF-8 原文。原始资料单独保存，不把预期答案放进数值输入。

完整模型要求结构、局域空间、相互作用和声明的结构对称操作。缺少关键物理约定时返回 needs_input。宿主读取问题，结合原始材料提取模型；需要研究者作出的选择必须得到明确答复。宿主可以通过 provide_input.model 送入提取的完整模型，或通过 request_updates.agent_normalized_document 使用已有受约束文档归一化接口。用户不需要手写内部 JSON。

输入文本的现有归一化器可能首先询问 ordinary spin / retained multiplet 路线。宿主可直接从已有明确上下文填写；无法确定时才询问研究者。不能把需要文档提取误报为已经理解了全部模型。

## 五类动作

每个动作必须有唯一 action_id 和非空 reason。ID 可包含字母、数字、点、下划线和连字符，最多 96 字符。

### provide_input：补充或修订

~~~json
{
  "action_id": "clarify-symmetry",
  "type": "provide_input",
  "reason": "研究者确认了结构对称性。",
  "model_patch": {"symmetry": {"operations": []}}
}
~~~

这里的空 operations 只是字段示意，实际必须填写明确的对称操作。model 可提供完整替代版本；model_patch 是递归合并。answers 可记录研究者的自然语言回复。request_updates 可更新 normalization、agent_normalized_document、physics_policy、budget、requested_tasks、question。每次生成新模型版本，原始版本保留。对称性修复仅在用户授权的 physics_policy.symmetry_repair=true 时执行。

接续新的研究问题可通过 request_updates 更新 question 和 requested_tasks；模型内容与约定相同的已有参考态仍可复用。

### propose_reduction：提出独立物理简化候选

使用 transformation.kind=drop_terms 选择完整 term_ref，或 project_local_space 提供明确的局域子空间 isometry。候选绑定当前完整模型，重新接受完整结构对称性检查。准备成功只意味着候选可以进入计算，不能据此声称物理近似成立。使用 calculate/task=reduction_validation 指定经典态、低能谱和逐项容差进行对照；详见 [输入示例与判据](physical-reductions.md)。

### propose_mechanism：设计机制研究

声明完整 term_ref 的分组、各组乘因子以及一个全为 1 的完整模型对照。每个干预点重新检查原结构对称性。随后用 calculate/task=mechanism_test 指定数值实验、标量观测量和可被反驳的机制假设。结论包含支持、反驳或不确定，以及原始响应、证据路径、固定态和重新优化态的能量变化。使用细节见 [机制研究协议](mechanism-workflow.md)。

### calculate：明确的数值动作

普通自旋经典搜索：

~~~json
{
  "action_id": "ground",
  "type": "calculate",
  "task": "classical_ground_state",
  "reason": "先在指定有限周期超胞上搜索满足定长约束的参考态。",
  "settings": {
    "supercell_shape": [2, 2, 2],
    "spin_length": 0.5,
    "starts": 4,
    "seed": 31
  }
}
~~~

复用它计算谱：

~~~json
{
  "action_id": "spectrum",
  "type": "calculate",
  "task": "harmonic_spectrum",
  "reason": "检查已有参考态在指定波矢处的驻点与谐波稳定性。",
  "reference_result": "ground",
  "settings": {"spin": 0.5, "reduced_momenta": [[0,0,0],[0.5,0,0]]}
}
~~~

谱必须引用已有合格经典态，继承其磁超胞；不重新搜索经典态。波矢统一使用原胞倒格矢约化坐标。显式提供的 spin 必须与参考态 spin_length 一致。

返回的谱支包含参考磁超胞引起的折叠。若参考超胞大于实际磁周期，不应直接把最小折叠频率解释为对应原胞波矢的单一激发；当前入口没有计算谱的展开权重。

保留 N 能级的 classical_ground_state 使用 starts、seed、max_linear_size、max_sweeps 等既有局域射线参数；不能把任意 supercell_shape 当成已支持参数。它在结构维度决定的有限尺寸序列上搜索，max_linear_size 必须有限。对应谱动作也引用参考结果，并给 reduced_momenta；不用 spin 字段，不推断物理自旋表示。

可通过 wall_time_seconds 对单次动作设更小时间限额；整个任务的总计算时间、实际调用数和每次进程地址空间内存均受 budget 约束。记录的计算时间包括 worker 启动与运行，不包含两次动作之间的等待。地址空间限制是保守的内存上限，可能先于物理内存耗尽触发。

### assess：解释已有证据

~~~json
{
  "action_id": "interpret",
  "type": "assess",
  "reason": "参考态和谱的诊断满足本次有限范围问题。",
  "answer_status": "answered_within_scope",
  "conclusion": "找到了所检验周期超胞中的稳定参考态。",
  "scope": "指定超胞与已采样波矢。",
  "limitations": ["未证明热力学极限的基态。"],
  "evidence": [
    {"result_id": "ground", "path": "calculation.energy_per_cell"},
    {"result_id": "spectrum", "path": "calculation.stability"}
  ]
}
~~~

answered_within_scope 必须有覆盖 requested_tasks 的当前模型结果、存在的证据路径和明确范围。partial、inconclusive 用于尚未完成的问题。程序检查证据引用、结果状态和任务覆盖；结论的物理解释仍是宿主 agent 的责任，不是自动证明。

## 当前接通的范围

| 模型/任务 | 当前能力与限制 |
| --- | --- |
| 普通自旋 | 完整双线性交换张量；有限周期定长经典搜索、谐波谱、MC、尺寸比较、有限簇量子低能谱、Fourier 诊断 |
| 保留 N 能级 | 同一局域维数、完整 Hermitian onsite 矩阵和一般 pair matrix；CP 局域射线优化与 Python GSWT，保留全部 N-1 激发 |
| 单独偶极任务 | model.kind=dipolar_geometry，显式 lattice_vectors、fractional_positions、moments；task=dipolar_ewald |
| 不支持项 | 完整模型含当前求解器不支持的项时停止，保存原项；不截断为双线性模型 |
| 显式指定其它后端 | 当前 Research 适配层不自动替换后端。Sunny 等既有单独命令保留；未连接到此入口的请求返回 backend-not-connected |

矩阵单位基的对称作用用 dimension² × dimension² 的显式 symmetry_actions 表示；它对局域算符矩阵按 row-major 的 (bra,ket) 索引作用。pair_matrix 存储为 (left_bra,right_bra;left_ket,right_ket)，换端是交换两个 Hilbert 因子，不是 Hermitian 转置。

历史接口也用 pair_matrix 名称存储算符基上的系数张量。规范化会记录 coefficient_representation，区分 full_pair_operator 与 operator_coefficient_tensor；只有前者进入新的保留能级求解器。原有系数张量的对称变换语义保持兼容。

MC 接口保留温度、误差、相关时间和有效样本数。已有采样器没有证实平衡性，因此单次 MC 输出为 inconclusive，不能据此宣布临界温度或临界指数。有限簇量子谱要求有限 Hilbert 空间、内存上限与本征残差；周期映像落到同一个自旋的量子配置会明确拒绝。

Ewald 必须提供 alpha、real_cutoff、reciprocal_cutoff、boundary（tin_foil 或 vacuum_sphere），以及需要通过的 cutoff_tolerance。它只计算显式偶极几何，不会混入短程 Hamiltonian 或其它求解器；截断比较不是严格误差界。

## 诊断与继续

- 驻点残差大：加强收敛，或把已有状态作为新经典搜索的 seed。不能直接用于谐波谱。
- 独立初态能量不同：增加初态并记录竞争解；向量不同本身不证明不同相。
- 有限尺寸或波矢采样不足：扩大相应检查范围，保留原范围限制。
- 谱不稳定：返回参考态搜索，保留软模和复频诊断。
- MC 统计不足或平衡性未证实：增加独立运行、热化和采样，并解释仍欠缺的证据。
- 预算不足：保存结果并作 partial/inconclusive 评估；不把计算完成等同于问题解决。

## 保存与恢复

RUN 保留 request.json、source-provenance.json、state.json、decisions.jsonl、
models/model-NNNN 的原始/规范/可读模型，以及 steps/ACTION 的动作、输入、执行记录、日志与结果。
状态索引原子写入，输入和完成结果可独立读取。状态检查不启动新 worker。

同一 action_id 的相同提交幂等；同 ID 不同内容拒绝。不同 ID 但完整模型、设置、参考结果和代码/环境身份均相同的已完成计算会被复用。模型或单位/基底标签改变、相关代码或环境改变，旧参考不能当作兼容参考。活动 worker 的 PID、主机和进程开始时间一起检查，不能只靠 PID 判断。

报告只读取已有证据，输出 Markdown、谱 CSV 和采样数据。它不会补算缺失阶段；没有 assess 时明确显示研究问题尚未被评估。磁超胞、局域维数、统计限制、失败与建议动作随结果保留。

## 可复跑检查

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider scripts/research/tests
PYTHONPATH=scripts python -B -m research.examples --output-dir NEW_INPUT_DIRECTORY
~~~

examples 只生成模型与请求，不携带预期物理答案。验收测试的期望值留在测试层。实际宿主操作与输出位置见 stage-one-acceptance.md。
