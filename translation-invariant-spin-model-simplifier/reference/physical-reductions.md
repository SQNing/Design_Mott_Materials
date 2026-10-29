# 有对照证据的物理简化

第二阶段通过同一个 Research 入口连接候选生成、完整模型对照、数值比较与报告。宿主 agent 根据研究问题提出候选、选择观测量并解释结果。用户不需要手写内部 JSON；下面是宿主调用协议。

## 1. 明确候选

删去指定的完整 canonical term：

~~~json
{
  "action_id": "omit-selected-term",
  "type": "propose_reduction",
  "reason": "检验指定相互作用能否在本次低能问题中省略。",
  "transformation": {"kind": "drop_terms", "term_refs": ["weak:exchange"]}
}
~~~

term_ref 必须来自当前完整模型。系数小只提供候选理由，不提供通过判据。删项后仍须满足原结构对称性；不允许自动降群、补回或平均修复。

对保留局域多能级的模型，选择三维空间中的前两维：

~~~json
{
  "action_id": "two-level",
  "type": "propose_reduction",
  "reason": "检验明确选定的两能级子空间。",
  "transformation": {
    "kind": "project_local_space",
    "isometry": [[1,0],[0,1],[0,0]],
    "basis_labels": ["g","e1"]
  }
}
~~~

isometry 的列在完整局域基底中表示保留态，必须正交归一，也支持复数列。所有局域空间需有相同维数；支持完整 onsite 矩阵及一般 pair operator，保留所有矩阵元。子空间须在已声明结构对称性下封闭。更高体项或算符系数张量等不支持表示明确拒绝。

这是直接子空间投影。没有加入虚激发生成的相互作用，不把任意两能级自动解释成物理自旋。原模型及全部历史记录独立保留。

## 2. 对照相同实验

以下动作适用于上面的 retained-local 候选。数值容差与能量单位必须根据实际研究问题选择，示例数值不是通用阈值。

~~~json
{
  "action_id": "compare-two-level",
  "type": "calculate",
  "task": "reduction_validation",
  "reason": "检查有限胞参考态及指定窗口内的低能谱。",
  "settings": {
    "candidate_id": "two-level",
    "energy_window_max": 2.0,
    "experiments": [
      {
        "case_id": "reference",
        "task": "classical_ground_state",
        "settings": {"starts": 3, "seed": 6, "max_linear_size": 1, "max_sweeps": 100},
        "metrics": {"energy_per_cell": 0.01, "full_energy_penalty": 0.01, "projector_distance": 0.05}
      },
      {
        "case_id": "modes",
        "task": "harmonic_spectrum",
        "reference_case": "reference",
        "settings": {"reduced_momenta": [[0,0,0],[0.25,0,0]]},
        "metrics": {"spectrum": 0.01}
      }
    ]
  }
}
~~~

每个实验用同一组设置计算完整模型和候选模型。至少包含经典态以及谐波谱或已有普通自旋有限簇量子谱。可以声明多组尺寸、波矢或种子，但它们必须各有唯一 case_id。每个谱引用之前的经典实验，继承各自已保存的态。若两边搜索选出的磁超胞不同，本次匹配不充分；不能静默把不同折叠的谱支对齐。

普通自旋经典态使用 supercell_shape、spin_length、starts、seed，态观测量改为 spin_correlations；其谐波谱 settings 还需 spin。保留能级经典态用 max_linear_size 限制既有有限尺寸搜索，不支持任意 supercell_shape 请求。有限量子实验 task=quantum_low_energy，settings 指定 supercell_shape、spin、eigenvalues、seed，metrics 为 quantum_gaps。保留局域多能级的有限量子 ED 尚未接到此入口。

## 3. 如何读判据

| 观测量 | 比较方法与限制 |
| --- | --- |
| energy_per_cell | 完整模型与候选模型每原胞能量之差的绝对值；可显式提供 energy_offset_per_cell，加到候选能量上，禁止自动拟合常数抵消误差 |
| full_energy_penalty | 把候选态嵌回完整模型后，相对完整模型参考态的能量惩罚；若反而更低，说明完整模型搜索不足，本次及依赖它的谱比较为 inconclusive |
| projector_distance | 局域射线密度矩阵差的最大 Frobenius 范数；消去整体相位影响，但不自动对齐不同对称代表 |
| spin_correlations | 同一超胞所有成对自旋点积之差的最大值，按自旋长度平方归一；不单独区分整体自旋取向 |
| spectrum | 相同波矢、同一超胞中排序后的激发能最大绝对差；投影必须声明 energy_window_max；窗口内模式数不同给出失败，模糊边界或空窗口给出 inconclusive |
| quantum_gaps | 相同有限量子簇与本征值数量中的激发间隙最大差；要求求解器残差等诊断合格 |
| mc_energy_per_site | 可请求已有 MC 作为额外证据；当前求解器尚未证实平衡性，所以这一项保持 inconclusive，不能据有限样本让候选通过 |

full_reference_tolerance 是识别“完整模型参考能量更高”的数值误差阈值，默认 1e-7，独立于物理容差。谱窗口的边界模糊带采用该谱的绝对容差。所有容差必须非负有限；投影窗口必须正且有限。

输出中的三个状态分别回答不同问题：

- execution_status：比较 worker 是否执行完成。
- scientific_status：该结果能否用于当前有限范围的科学判断。
- validation_status：accepted_within_scope / rejected / inconclusive。

可靠反例产生 rejected，同时可以是 usable_within_scope。这允许 agent 用 assess 明确回答“这一近似不满足要求”。控制计算不合格不能当作拒绝近似的可靠反例；其依赖谱也保持不确定。若另一项独立且合格的比较已有反例，仍可以据那个反例拒绝。

通过仅限记录的模型参数点、有限胞、采样波矢、能量窗口及观测量。它不证明无限体系基态、全参数范围或相等价，也不提供自动机制解释。

## 4. 成本、复用和接续

两模型各做一次经典态、一次谱，最多需要四次真实求解，启动前预留全部未缓存调用的预算。只改变误差容差或能量窗口，复用已有物理计算；改变物理设置、模型或实现环境则采用新的证据。缓存保留模型、参考、代码环境和内容摘要。失败的调用计入预算，但不写入可复用的成功缓存。无合格参考时不启动对应谱。

candidate_id 绑定完整模型身份。provide_input 改变完整模型后，需要重新提出候选；旧模型和结果不删除。活动 worker 的同一 action_id 可由另一进程接续，不重复启动；中断后可使用新动作继续复用已经保存的子实验。

report 只读取 records、metrics、scope 和子实验路径，不重新计算。status 展示候选、当前父模型身份与各次验证记录。完整模型不会被候选自动替换。

## 5. 可复跑验收

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider scripts/research/tests/test_reductions.py

PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_reduction_acceptance.py --output-dir NEW_DIRECTORY
~~~

验收输入和预期判断只在测试范围内；不通过文献身份或预期答案影响求解。

