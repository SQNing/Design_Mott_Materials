# 阶段一实施与验收记录

验收日期：2026-10-30（Asia/Hong_Kong）。实现位于 feature/literature-evidence-audit 工作树，起始 HEAD 为 98ff48c762600b3a6d5e1a075855aa5b74a9974d。原有未提交的 3D 模块及 spin-only bridge 三行修复保留。

## 交付内容

- prepare/status/step/report 统一入口与对应 Python API。
- 原始输入、完整规范模型、对称性检查、保真可读视图、模型版本和决策记录。
- 普通自旋与保留局域能级两条真实计算路径，经典参考态直接接续谱。
- 有限温采样、有限簇量子低能谱、Fourier 诊断及独立 Ewald 路由。
- 后台 worker、相同动作幂等、相同计算复用、代码/环境和模型兼容性检查、时间/内存/调用数预算。
- execution_status、scientific_status、answer_status 分开记录；报告只读取已有证据。
- 缺少物理约定时的补答流程；不支持项与预算不足的明确停止。

新增 retained-local 适配还暴露并修复了两个共享层缺口：onsite 矩阵通过同一个严格对称性与 Hermiticity 检查；完整 pair operator 按局域矩阵单位变换并正确交换 Hilbert 因子。历史的算符系数张量通过显式 representation 区分，原有接口回归通过。

## 自动检查

最终相关回归结果：96 passed，36.66 s。包含 15 个新研究流程/物理约定测试及 81 个相关既有检查。23 条警告来自已有 Matplotlib/Pyparsing 和 spglib 弃用接口；没有失败。

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider \
  scripts/research/tests \
  tests/test_operator_family_symmetry.py \
  tests/test_hamiltonian_symmetry_cli.py \
  tests/test_hamiltonian_symmetry_completion.py \
  tests/test_canonical_hamiltonian.py \
  tests/test_hamiltonian_symmetry_action.py \
  tests/test_hamiltonian_symmetry_gate.py \
  tests/test_hamiltonian_symmetry_pipeline.py \
  tests/test_hamiltonian_solver_routing.py \
  scripts/three_dimensional/tests
~~~

测试范围包括：完整项保留、参考态复用、缺信息补答、陈旧参考拒绝、预算停止、后台恢复、报告无计算、一般复数局域矩阵、矩阵单位对称作用、换端不变的物理矩阵元和 onsite Hermiticity。没有把预期答案放进计算输入。git diff --check 通过。

## 五类实际使用任务

持久化结果根目录：

~~~text
artifacts/research-stage-one-20261030-001/
~~~

| 任务 | 实际执行与证据 | 结果及边界 |
| --- | --- | --- |
| A：新多子晶格模型 | 四个不等价磁性位点、三斜原胞、18 个不同交换张量；初次搜索→增加独立初态→保存参考→三点谱→评估与报告 | 每原胞能量 -4.4252325；四条谱支；仅检验的有限周期胞与波矢范围 |
| B：保留三能级 | onsite 3×3 矩阵与含复数非对角元的 9×9 一般 pair operator；局域射线优化→Python GSWT | 每原胞能量 -0.51；现场项和 pair 项各 1 个；保留全部两个局域激发，无隐式自旋化 |
| C：原始文档 | 宿主读取原文→needs_input→读取示范研究者补答→提取完整模型→经典态→复用参考算谱→解释报告 | 每原胞能量 -0.6975；驻点残差 6.42×10⁻¹⁴；结构化控制输入具有相同模型身份；共 2 次求解 |
| D：恢复 | worker 活动时从第二个宿主进程提交同一动作，完成后再从另一个进程重复 | 同一 result_id，实际 solver_runs=1；没有重复计算 |
| E：采样与量子 | 小周期系统两温度 MC；8 个 spin-1/2 的有限簇量子低能谱 | 量子残差约 4.49×10⁻¹⁴、2.62×10⁻¹⁵；短 MC 没有证实平衡性，任务评估为 partial |

各任务的 report.md、manifest.json、完整步骤输入、日志和结果都保存在对应 A/B/C/D/E 目录。summary.json 汇总结果。五类任务均无遗留活动 worker；结构化控制输入只准备模型，不启动计算。

A/B/D/E 的可复跑脚本：

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_acceptance.py --output-dir NEW_ACCEPTANCE_DIRECTORY
~~~

### C 的宿主实际操作记录

本例是合成研究任务，补答是明确标注的验收 fixture，不代表项目所有者在本轮提交了一个新物理模型或作出了新的物理选择。

1. 宿主实际读取 scripts/research/fixtures/host-document-C.txt。文档明确了简单立方晶格、48 个结构对称操作、最近邻各向同性交换 -0.93、每条无向键计一次、2×2×2 超胞及两个波矢，但保留了自旋/Pauli 归一化问题。
2. prepare 经已有文档归一化器返回 needs_input，问题为 spin-only / retained multiplet 路线选择，未调用求解器。C-prepare-view.json 保存原始返回。
3. 宿主识别到需要明确 ordinary spin-1/2 的算符约定；读取 host-clarification-C.txt 的示范补答后，才以 provide_input 提交完整模型及自然语言答复。C-host-landing-action.json 保留输入和来源。
4. 经典搜索返回 usable_within_scope，能量 -0.6975000000000002，驻点残差 6.421083105632721×10⁻¹⁴。宿主读取结果后，选择以这个参考继续谐波谱。
5. 谱实际复用 host-ground；没有 classical_optimization 重跑。最小 BdG Hessian 本征值约 -9.44×10⁻¹⁶、最大频率虚部约 3.80×10⁻¹⁶，均在数值容差内。
6. 宿主评估明确注明 2×2×2 超胞的谱折叠，不把两个 q 点相同的折叠谱误认成原胞激发没有色散。报告生成后 solver_runs 仍为 2。

原始文档与示范补答均随代码保存。下面脚本重放上述已经记录的宿主选择；它不是新的自动文档理解器。实际宿主理解和选择步骤是在本轮工具操作中完成的，不是只验证一个返回预制 JSON 的 mock callback。

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/replay_host_document.py --output-dir NEW_DOCUMENT_REPLAY
~~~

## 范围说明

本轮实际验收的是接通的 Python 数值路线。Sunny 的既有独立命令保留，未声称经新的 Research 接口完成 Sunny 验收：默认 Julia 缺 Sunny，项目 Julia 入口的环境探测在 40 s 限时内未完成。没有安装依赖或把其它后端的成功当作 Sunny 成功。

完整模型中出现不支持项时仍会停止；MC 的有限样本和平衡性限制被保留。阶段二的物理删项/截断验证、阶段三的机制干预与自动无限范围研究不在此次交付内。实现没有建立新的集群调度系统。
