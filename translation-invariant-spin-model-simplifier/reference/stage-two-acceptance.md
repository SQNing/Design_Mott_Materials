# 第二阶段实施与验收记录

验收日期：2026-10-30。实现继续位于 gpulzh 的 feature/literature-evidence-audit 工作树，起始 HEAD 为 98ff48c762600b3a6d5e1a075855aa5b74a9974d。完整模型、阶段一记录及原有未提交修改保留；本轮没有提交或合并 Git 变更。

## 已接通的能力

- propose_reduction：独立保存显式删项或局域子空间投影候选，绑定完整模型身份。
- 完整结构对称性复查、投影列正交检查、子空间封闭检查，以及全部 onsite / pair operator 的一致投影。
- reduction_validation：相同设置下计算完整模型与候选，比较每原胞能量、候选态在完整模型中的能量惩罚、相关量或局域密度矩阵、谐波谱及已有有限量子簇间隙。
- 低能窗口内的模式数检查，模糊窗口边界和空窗口明确返回 inconclusive。
- 区分执行、科学可用性与近似验证结论。可靠反例可以用于回答“近似不成立”。
- 每次真实求解分别计费；子实验按模型、设置、参考和实现环境复用。容差或窗口调整不触发重复物理计算。
- 子求解失败仍计入成本，但不作为可复用的完成证据；不合格参考不会启动其谱计算。
- 原模型修订后拒绝旧候选；同一动作可跨进程接续。报告读取已保存证据，不补算。

使用协议与示例见 [physical-reductions.md](physical-reductions.md)。

## 最终相关回归

112 passed，23 warnings，42.66 s，进程退出码 0。其中第二阶段新增 16 项测试，原阶段一与相关共享层检查共 96 项。下面另有完整持久化物理工作流验收。git diff --check 退出码为 0。

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

最终日志：artifacts/stage-two-regression-20261030-002.log。

覆盖的新增行为包括复数 isometry 的独立矩阵元验证、保持完整模型、破坏结构对称性的删项拒绝、不封闭子空间拒绝、有限经典与量子比较、MC 未证实平衡时保留不确定性、失败重试成本、缓存内容完整性、容差调整复用、预算预留及旧模型候选拒绝。

## 六类实际工作流

最终持久化结果：

~~~text
/data/work/zhli/soft/spinforge/.worktrees/literature-evidence-audit/translation-invariant-spin-model-simplifier/artifacts/research-stage-two-20261030-002/
~~~

| 案例 | 实际操作 | 结果 |
| --- | --- | --- |
| A-weak-exchange | 在三个主交换项之外加入 0.001 的弱交换，提出删除它，比较经典态及两点谱 | accepted_within_scope；每原胞能量误差约 0.00025，最大谱误差约 0.001，分别小于 0.01 和 0.005 的容差 |
| B-small-anisotropy | 删除 0.02 的各向异性项 | rejected；能量误差约 0.005，低于 0.01 的容差；谱误差约 0.02，超过 0.005 的容差 |
| C-two-level | 将含现场项与一般复数 pair operator 的三能级模型投影到前两级 | 窗口上限为 2 时 accepted_within_scope；收紧误差容差额外求解 0 次；把窗口扩大到 20 后因模式数不匹配 rejected，额外求解仍为 0 次 |
| D-wrong-subspace | 投影到不含真实最低局域态的两维子空间 | rejected；能量误差和完整模型能量惩罚均约 1.11；拒绝证据为 usable_within_scope，可通过 assess 回答本次近似问题 |
| E-resume | 启动比较后，由另一宿主进程接续并重复同一动作 | 恢复同一结果，总共 4 次求解，没有重复计算 |
| F-budget | 完整比较需预留 4 次求解，只给 3 次预算 | 启动前返回 solver-run-budget-exhausted，实际求解 0 次 |

每个案例保存完整模型、候选、动作、比较输入、子结果、代码身份、误差与范围、评估及报告。summary.json 汇总六类案例和窗口对照。所有验收案例结束时均无活动 worker；SSH shell 保持打开。

可复跑脚本：

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_reduction_acceptance.py --output-dir NEW_DIRECTORY
~~~

目录 001 是首次验收记录，予以保留。002 是加入失败重试回归后的最终代码验收，退出码 0。

## 实现身份与适用边界

最终验收的 source_hash：

~~~text
f51c5df4f17983fe187863982a332e5976f58b73efbbbfe906271815dcca382b
~~~

运行环境：Python 3.9.13、NumPy 1.23.5、SciPy 1.13.1。程序实际调用 /data/home/zhli/anaconda3/bin/python。阶段二仍使用已经接通的 Python 求解路线。

通过只说明该模型参数点、已计算有限胞、采样波矢、给定窗口及观测量符合明确容差。一次驻点搜索不能证明全局基态；相位无关的局域投影比较也不自动对齐全部对称代表。谱比较尚不含展开权重或响应强度。直接子空间投影不包含虚激发导致的高阶有效相互作用。保留多能级的有限量子 ED、自动机制干预解释及全相图论证仍不属于本阶段交付。

