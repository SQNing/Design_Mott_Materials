# 机制干预与物理解释

第三阶段在完整模型上检验可明确表述的物理机制。宿主 agent 提出假设、选择对照和观测量，程序执行数值实验并保存支持或反驳的证据。此功能可用于任意符合已有模型契约的新模型，无须文献或 benchmark 登记。

典型接续：第二阶段发现某项虽然系数小、能量影响小，却显著改变指定低能谱；第三阶段逐步减弱、关闭该项，并检验其它相互作用的替代解释。相同完整模型及实验可以复用第二阶段已保存的计算。

## 1. 定义干预组与强度点

~~~json
{
  "action_id": "couplings",
  "type": "propose_mechanism",
  "reason": "区分各向异性与各向同性交换对所选激发的作用。",
  "question": "哪组相互作用控制指定波矢的频率？",
  "groups": [
    {"group_id": "anisotropy", "term_refs": ["anisotropy:x"], "description": "选定的完整各向异性交换项。"},
    {"group_id": "exchange", "term_refs": ["exchange:x","exchange:y","exchange:z"], "description": "各向同性交换背景。"}
  ],
  "points": [
    {"point_id": "control", "factors": {"anisotropy": 1, "exchange": 1}},
    {"point_id": "anisotropy-off", "factors": {"anisotropy": 0, "exchange": 1}},
    {"point_id": "anisotropy-half", "factors": {"anisotropy": 0.5, "exchange": 1}},
    {"point_id": "exchange-off", "factors": {"anisotropy": 1, "exchange": 0}},
    {"point_id": "exchange-half", "factors": {"anisotropy": 1, "exchange": 0.5}}
  ]
}
~~~

示例 term_ref 需替换为实际完整规范模型中的项。每组须有物理说明；组间不能重叠。每个点必须显式声明所有组的有限实数乘因子，恰有一个点全部为 1。乘因子为 0 时保留该项的表示和来源，完整系数变为零；负因子允许显式改变符号。

每个点只改变选定完整项的系数，局域维数、基底、晶格与原结构对称性保持原约定。若某个单独项属于结构对称性关联的一组，必须选择能保持该对称性的完整干预组；系统不会自动降群或修复。任何点不能通过对称性检查时，计划 status=rejected，不启动部分模型的计算。

当前干预单位是完整 term。若多个物理分量合并在同一个交换矩阵中，此接口会缩放整个矩阵；需要针对分量研究时，应先在输入模型中明确、忠实地分项，并重新通过完整模型与结构对称性检查。

完整模型仍是唯一的原始对照。第三阶段不自动把第二阶段候选用于新的耦合范围；某一参数点的近似验证不代表整个干预范围有效。

## 2. 指定实验、观测量与假设

~~~json
{
  "action_id": "response",
  "type": "calculate",
  "task": "mechanism_test",
  "reason": "计算匹配的参考态与谱，并检验指定响应。",
  "settings": {
    "mechanism_id": "couplings",
    "reference_tolerance": 1e-7,
    "experiments": [
      {
        "case_id": "reference",
        "task": "classical_ground_state",
        "settings": {"supercell_shape": [1,1,1], "spin_length": 0.5, "starts": 3, "seed": 18}
      },
      {
        "case_id": "modes",
        "task": "harmonic_spectrum",
        "reference_case": "reference",
        "settings": {"spin": 0.5, "reduced_momenta": [[0,0,0],[0.25,0,0]]}
      }
    ],
    "observables": [
      {"observable_id": "frequency", "case_id": "modes", "kind": "harmonic_frequency", "q": [0,0,0], "band_index": 0}
    ],
    "hypotheses": [
      {
        "hypothesis_id": "anisotropy-response",
        "statement": "增强各向异性会提高所选频率。",
        "kind": "monotonic_response",
        "group_id": "anisotropy",
        "observable_id": "frequency",
        "direction": "increasing",
        "min_effect": 0.015,
        "numerical_tolerance": 1e-7
      },
      {
        "hypothesis_id": "exchange-insensitive",
        "statement": "该频率在所采样范围内对各向同性交换不敏感。",
        "kind": "insensitive_response",
        "group_id": "exchange",
        "observable_id": "frequency",
        "max_change": 1e-5,
        "numerical_tolerance": 1e-7
      }
    ]
  }
}
~~~

这些数值只是可运行协议的示例，实际阈值必须来自研究问题。每个干预点使用相同实验设置，谱直接引用该点已保存的参考态。保留局域多能级的经典实验改用 starts、seed、max_linear_size、max_sweeps；max_linear_size 必须明确且有限，谱不传 spin。现有后端的完整项支持边界仍适用。

每个 observable 必须被至少一个假设引用。可以用多个实验检查不同有限尺寸或独立初态，但不能把单一尺寸的结论扩展到未计算尺寸。

### 可读观测量

| kind | 定义与参数 |
| --- | --- |
| energy_per_cell | 指定经典实验的每原胞能量 |
| harmonic_frequency | 指定 q 上排序后的第 band_index 条频率，索引从 0 开始；q 必须已在谱网格中计算且选择唯一 |
| quantum_gap | 有限量子簇第 level 个排序本征值相对最低本征值的差，level 从 1 开始；必须请求足够 eigenvalues |
| local_population | 保留局域空间中 basis_index 对应态的占据概率；按已保存局域射线计算，平均所有胞和位点，或用 site 选择一种基底位点 |
| mc_energy_per_site | 指定 temperature 的 MC 证据入口；当前适配层未验证平衡性，观测量不能成为机制支持证据，原始样本保留在子结果中 |

谐波频率是指定磁超胞中的排序频率，没有谱展开或本征矢连续追踪。能级交叉时，同一 band_index 未必代表同一物理模。量子 level 指定的是排序能级差；不自动排除基态简并或替用户定义激发隙。能量与频率阈值按输入模型的能量约定解释，局域占据无量纲。

### 三种假设

- monotonic_response：至少三个互不相同的独立乘因子点；direction 为 increasing/decreasing；所有相邻采样响应须符合该方向，并且端点有向变化超过 min_effect。
- insensitive_response：至少两个独立点；相对完整对照的最大绝对变化小于 max_change。
- necessary_in_context：完整对照中的观测量须明确高于 present_above；关闭该组后须明确低于 absent_below。要求 present_above 大于 absent_below，二者非负；只使用完整对照与独立关闭点。例：
  ~~~json
  {
    "hypothesis_id": "required-for-frequency",
    "statement": "在其余耦合固定时，该组对指定非零频率是必要的。",
    "kind": "necessary_in_context",
    "group_id": "anisotropy",
    "observable_id": "frequency",
    "present_above": 0.01,
    "absent_below": 0.0001,
    "numerical_tolerance": 1e-7
  }
  ~~~

每个单组假设只使用其它组都保持完整对照值的点。其它组也变化的点明确列为 excluded_confounded_points；不能用相关趋势填补缺失的独立对照。必要性假设不要求不相关中间点收敛，使用的两个端点必须合格。

numerical_tolerance 是明确声明的比较分辨率，不能冒充经过证明的数值误差界。接近判据阈值的结果为 inconclusive；完整模型中现象本来就不明确时，也不能通过“关闭后不存在”宣称必要性。必要性不等于充分性或唯一性。

## 3. 区分直接能量作用与态重排

对每组经典实验保存四个能量：

1. 完整哈密顿量下的完整参考态。
2. 干预哈密顿量下仍固定使用完整参考态。
3. 干预哈密顿量下重新优化后的态。
4. 把重新优化后的态放回完整哈密顿量。

前两者之差是固定态下的直接能量变化；第二与第三之差是态重新优化造成的变化，两者之和等于总能量变化。这些量帮助宿主区分“能量贡献变了”与“态发生重排”，不把能量大小直接当作谱机制的证据。

若其它已有态能显著降低完整参考能量，完整搜索就不足，相关经典观测量及依赖该参考的谱均为 inconclusive。若完整参考态在干预模型下反而优于干预优化结果，则该干预参考不足。reference_tolerance 默认 1e-7，用于这种数值一致性检查；它与假设的物理效应阈值分开。

局域占据使用已声明的基底，不能自动解释成某个物理轨道、自旋方向或实验响应。退化参考态可能选出不同代表；宿主需要把对称性和取样限制写入物理解释。

## 4. 结论与证据

每个假设返回：

- status：supported_within_scope / refuted_within_scope / inconclusive。
- response：实际乘因子、观测值、变化幅度和相关判据。
- used_points、excluded_confounded_points、unused_isolated_points：用于当前判据的点及没有使用的点。
- evidence：子结果路径、数值指纹和观测量选择方式。
- reason 与 explanation：支持、反驳或缺证据的具体理由。

每个机制结果另有 observations、energy_responses、validated_scope。至少一个请求假设尚不确定时，整项 scientific_status=inconclusive；全部请求假设得到可靠支持或反驳时，为 usable_within_scope。反驳也是可以用于回答问题的科学证据。

宿主通过 assess 引用 calculation.hypotheses、calculation.observations 等路径，连接假设、观测和解释。应根据诊断选择进一步的独立对照、尺寸或波矢，不自动放宽阈值使假设通过。

## 5. 预算、复用和报告

五个干预点各做一次经典态和一次谱，最多需要十次求解。相同完整模型的第二阶段计算可以复用；启动前预留所有未缓存调用。固定态能量评估没有再启动优化器。失败的求解计入预算，不能作为成功计算缓存；无合格参考时不启动对应谱。

同一物理计算可以在改变假设阈值、观测波矢选择或观测量定义后复用，但新观测必须已经包含在保存的计算中。要增加未计算波矢、改变有限胞或基底约定，需要新的实验或模型版本。旧模型的机制计划不能用于修订后的模型。

报告只读取保存的模型与证据，不启动计算。包含假设表、逐点响应、固定态与重新优化能量、证据链接及有限范围。该流程支持模型内物理解释，不提供无限系统证明、自动高阶有效哈密顿量或全参数范围的机制结论。

## 可复跑检查

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider scripts/research/tests/test_mechanisms.py

PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_mechanism_acceptance.py --output-dir NEW_DIRECTORY
~~~

验收 fixture 与预期判断只在测试范围内，数值输入不包含预期答案。

验收脚本需要 pytest，并可用 --resume 在同一目录接续已经保存的动作与结果；模型或请求不兼容时仍会拒绝接续。

