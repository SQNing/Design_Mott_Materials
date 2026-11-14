# 研究可靠性修复与验收记录

验收日期：2026-11-14（Asia/Hong_Kong）。基于已发布的 8938234942c587c395338c456c97bb480abe7c18，落实本轮优先的两项改进：中断任务耗时记账，以及有限胞基态证据和可行 Fourier 补救。原有研究记录保留。

## 实现

### 中断耗时

- 本地监督 worker 按约 0.25 秒的间隔保存单调时钟耗时，正常完成与受控失败保存终止耗时。
- 监督进程丢失而计算子进程已完成时，可从子结果恢复耗时。
- 已确认中断的任务按最后计时检查点固定记账，之后的闲置时间不再增长。
- 检查点之后未观测到的故障尾段标为 uncertain；不把最后一次检查点当成精确结束时刻。
- 没有检查点的历史中断记录，保守采用原 timeout_seconds 的固定预留，明确它不是实测耗时。原执行记录不重写。
- 重复动作与缓存复用仍不重复计费，报告展示记账来源。这里使用本地进程，不提交 Slurm 作业。

### 基态证据与补救

- 分别保存 stationarity、有限周期胞下界饱和状态、无限晶格认证状态。
- 有限胞状态为 bound_saturated / not_certified / inconsistent_bound。前者是已声明数值分辨率内的下界饱和证据，非区间算术证明。
- 正的 LT 差距不自动否定真实基态；松弛下界可能不可达到。
- 默认在初次未认证时尝试从本模型的最低 Fourier 模构造补充初态。所有局域长度、完整模型能量和驻点残差须合格；不接受明显不等幅模式的逐站点投影作为认证。
- 最多额外优化一个可行初态。initial_search 保留初次态与各初态记录，recovery 保留候选与采用情况。设置 fourier_seed_recovery=false 可关闭。
- assess.claim_level=finite_cell_ground_state 需要所引经典结果的有限胞饱和证据；stationary_reference 只要求已记录的驻点证据。当前有限计算不能支持 answered_within_scope 的 thermodynamic_ground_state 声明。
- 保留多能级路线继续提供驻定变分参考，没有借用普通自旋的 LT 认证。

协议见 [research-workflow.md](research-workflow.md)。

## 回归

最终相关回归：**145 passed，23 warnings，59.37 s，退出码 0**。包含原 131 项和本轮 14 项。

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

新增用例覆盖：闲置时钟变化、检查点固定记账、丢失监督进程后的子结果计时、慢文件读取不重复计入启动耗时、公共接口恢复预算、明确的有限／无限结论门槛、报告不补算、驻定高能态补救、显式关闭补救、不等局域长度的不可饱和 LT 模、一般交换张量、复数双子晶格 Fourier 相位、低于数值下界的异常。

修复前已观察到计时从 4000 增至 499000 秒、驻定高能态不被补救、有限结果被直接用于无限体系声明等失败。有限胞声明用例在更正测试模型的矩阵输入格式后，另以 red-claim.log 确认修复前确实未拒绝过度声明。首轮定向检查为 13 passed，8.49 s；随后补充慢读取边界测试，实际复现首版计时逻辑把 4 秒计为 7 秒，修正后纳入最终 145 项回归。完整红／绿日志和修正前 worker 源码均保留。

最终日志根目录：`artifacts/research-reliability-20261114-002/`。001 保留早期回归、验收和慢读取修正的失败证据；002 对最终实现重新完成全部相关回归与三类实际验收。

## 三类实际工作流

~~~sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -B scripts/research/tests/run_reliability_acceptance.py \
  --output-dir NEW_DIRECTORY
~~~

默认新建目录；--resume 可在相同实现和输入下接续已有动作。验收代码位于测试目录，不构成产品模型路由。

| 案例 | 实际过程 | 结果 |
| --- | --- | --- |
| A：真实中断与恢复 | 启动本次专用 worker，确认身份与计时检查点后中断其监督进程及子进程；随后用公共接口继续同一研究任务 | 中断记账在闲置前后均为 0.6081531047821045 s，uncertain=true；新动作正常完成并饱和其有限胞下界 |
| B：原蜂窝模型 | 原 J1=1、J2=0.3、J3=0.05，12×12 原胞，6 个初态、seed=83；由公共接口自动补救 | 初始每原胞能量 -0.42498789285113153，LT 差距 1.2107148868567563e-5；额外一个可行初态后能量 -0.4249999999999998，差距 2.7755575615628914e-16；有限胞声明接受，无限体系声明拒绝 |
| C：不可饱和下界 | 三个不等价子晶格的独立交换链，2×1×1 原胞；真实定长态无法把全部范数分配到最强子晶格的 LT 模 | 每原胞能量 -0.3125，下界 -0.75，差距 0.4375；驻点参考可用，保持 not_certified，不启动不满足局域约束的补救，不接受有限胞认证声明 |

上述能量是自旋长度 0.5 下的每原胞输入单位。B 是两站点原胞，换成单位长度经典自旋的每站点能量需乘 2。它验证的是 12×12 胞，不能据此宣布无限晶格或尺寸收敛。

三类验收均已完成评估并生成报告，无活动 worker；预算记录共 4 次后端尝试，其中 1 次为本次注入的中断，3 次完成数值调用。A 只终止验收新建并核对身份的两个进程组。原始蜂窝模型与既有结果只读使用。

工作流证据位于 `artifacts/research-reliability-20261114-002/workflows/`，summary.json 汇总计时、初始／最终能量、认证状态、声明拒绝原因和报告路径。

最终产品 source_hash：

~~~text
57095b3624575462f5db46c40e91c0a26619c14990ba48941c5413a5f095a0f5
~~~

运行环境：Python 3.9.13、NumPy 1.23.5、SciPy 1.13.1。未改变模型项、结构对称群、局域空间或既有数据；没有将有限胞认证升级为热力学极限证明。
