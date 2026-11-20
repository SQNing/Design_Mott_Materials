# 第三阶段实施与验收记录

验收日期：2026-10-30。实现继续位于 gpulzh 的 feature/literature-evidence-audit 工作树。阶段一、阶段二的完整模型、结果与原有未提交修改保留。本轮未提交、合并或推送 Git 变更。

## 已实现的研究能力

- propose_mechanism：以完整 term_ref 定义相互作用组与明确乘因子点，保存完整模型对照，并逐点检查原结构对称性。
- mechanism_test：复用经典态、谐波谱、有限量子簇及已有 MC 路线，保存观测量响应。
- 三种显式机制假设：有最小效应要求的单调响应、其余耦合固定时的必要性、指定容差内的不敏感。
- 逐条返回 supported_within_scope / refuted_within_scope / inconclusive；结论附带原始数值、判据、所用点、被排除的同时变化点与证据路径。
- 区分固定原参考态时的直接能量变化和重新优化态后的能量变化，并检查两边参考态是否充分。
- 第二、第三阶段共用子实验缓存、预算和持久化 worker。改变假设或选择已计算观测量不重算物理。
- report 与 assess 连接假设、观测和解释；报告本身不启动计算。

调用协议见 [mechanism-workflow.md](mechanism-workflow.md)，设计范围见 [stage-three-design.md](stage-three-design.md)。

## 最终回归

131 passed，23 warnings，47.86 s，进程退出码 0。新增 19 项机制相关检查，前两阶段及相关共享层检查共 112 项。

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B -m pytest --disable-warnings -q -p no:cacheprovider \
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

日志：artifacts/stage-three-regression-20261030-001.log。

检查覆盖复数矩阵缩放、原模型保持、未知项与重叠分组、重复点与缺失对照、对称性拒绝、旧模型计划拒绝、观测量变化复用、跨阶段复用、效应阈值边界、必要性端点选择、参考态不足、完整三能级、有限量子簇以及 MC 不确定性。

新增自由命名的实验与干预点暴露了证据文件名碰撞问题。回归先实际复现 FileExistsError，再改为按实验目录、干预点文件保存；相关检查及全套回归随后通过。变更源文件通过语法与尾随空白检查，git diff --check 退出码 0。

## 七类持久化物理工作流

结果根目录：

~~~text
/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-three-20261030-001/
~~~

| 案例 | 实际研究与结果 | 求解次数 |
| --- | --- | --- |
| A-reduction-to-mechanism | 第二阶段拒绝删除小各向异性项，第三阶段进一步支持其控制区心频率；交换主导该区心频率的假设被反驳，而交换对另一采样波矢的频率响应得到支持 | 合计 12；其中删项验证 4，机制研究新增 8；切换已采样波矢新增 0 |
| B-retained-levels | 完整三能级现场项与一般复数 pair operator；现场矩阵乘因子为 0.5、1、1.5 时，所选频率约为 1.12、1.52、1.92，所选局域态占据均为 1 | 6 |
| C-finite-quantum | 八个自旋 1/2 的有限周期簇，显式比较第 3 个排序本征值相对最低本征值的间隔；随各向异性乘因子 0、0.5、1 约为 0、0.01、0.02 | 3 |
| D-confounded-controls | 两组耦合同时减弱，缺少单组独立对照；全部单组机制假设保持 inconclusive | 6 |
| E-resume | 活动机制 worker 由另一个宿主进程接续，完成后再重复同一动作；恢复相同结果，无重复求解 | 6 |
| F-mc-uncertainty | 短 MC 样本未验证平衡性；不把样本响应判为机制支持，结果为 inconclusive | 3 |
| G-budget | 五个点各需经典态与谱，共需预留 10 次求解，但预算为 9；启动前停止，结果为 inconclusive | 0 |

上述能量与频率使用模型约定的单位。量子簇三组实验的最大本征对残差约为 9.34e-11。报告包含各自有限胞、波矢、基底标签、乘因子、阈值与证据路径。

A 案例中，各向异性关闭、减半、保持原值时，区心频率约为 0、0.01、0.02；关闭或减半各向同性交换，区心频率仍约为 0.02。对于另一个已采样波矢 [0.25,0,0]，交换乘因子 0、0.5、1 给出约 0.02、0.52、1.02。这些不同响应支持在所测范围内区分两组相互作用的作用。

每个案例保存输入、完整模型与干预模型、数值结果、观测量、假设判断、评估及报告。summary.json 汇总全部案例。所有案例结束时均无活动 worker；原 SSH shell 保持打开。

## 接续记录

第一次持久化验收已完成 A–F 与 G 的预算停止；验收脚本在保存 G 的评估时遗漏非空 limitations，被已有接口拒绝。修复验收脚本后，在原目录使用 --resume 完成记录，不改变产品求解代码：

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_mechanism_acceptance.py \
  --output-dir artifacts/research-stage-three-20261030-001 --resume
~~~

接续退出码 0，求解计数前后均为 36，新增求解为 0。日志：artifacts/stage-three-acceptance-resume-20261030-001.log。已有物理结果与历史记录保留。

新目录可复跑完整验收：

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_mechanism_acceptance.py --output-dir NEW_DIRECTORY
~~~

## 实现身份与边界

最终产品代码 source_hash：

~~~text
c3a8f9e1ec92808b87777795cd95eae97b12f3d851e541bc20e0f8518eaa0ba2
~~~

最终验收脚本 SHA-256：

~~~text
8c0f8c4aa83e7ff121b80c96b9290c1a127809ade3a211731d293e841378a26c
~~~

运行环境为 Python 3.9.13、NumPy 1.23.5、SciPy 1.13.1，解释器为 /data/home/zhli/anaconda3/bin/python。没有安装新求解后端或 LLM 服务。

这些机制判断仅覆盖显式完整项的干预、已采样参数点、有限胞和观测量。当前不自动拆解一个矩阵内部的物理分量，不证明唯一机制或无限体系结论；谐波频率没有展开权重和本征矢连续跟踪。数值比较容差不是严格误差界。虚激发修正、高阶有效哈密顿量与全相图论证仍不在本阶段范围内。

