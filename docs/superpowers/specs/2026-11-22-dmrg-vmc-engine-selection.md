# DMRG / VMC 引擎选型决策记录（阶段 D0 / E1）

日期：2026-11-22
决策人：用户（"继续D和E吧"，采纳计划建议项）
记录：本文件

## DMRG 引擎：ITensor.jl（ITensors + ITensorMPS）

- **理由**：仓库已有 Julia/Sunny 基建（`.julia-env-v09`、`run_project_julia.sh`、`common/julia_environment.py` 探针 + fail-closed 约定），运维同构；`run_sunny_*.jl` 的"Julia 脚本 + Python driver + subprocess"模式可直接复制；ITensor 的 DMRG 成熟度与 MPS 原生纠缠熵访问满足 D3 需求。
- **备选未选**：TeNPy（纯 Python，部署简单，但与 Sunny/Julia 路线双栈，证据分级与进程模型要重造一套）。
- **环境**：独立环境 `.julia-env-dmrg/`（Project + Manifest 进 git，与 v09 同规则），不为 Sunny 环境增负。无 Julia 的机器（如 studio2）按既有探针约定返回 `backend-not-connected`，禁止静默回退。
- **范围**：2D 只承诺条带几何；条带结果 claim_level 最高 `finite_cell_ground_state`，禁止自动外推结论。有限温（METTS/purification）为可选延期项，不做时 status 保持 declared-not-connected。

## VMC 引擎：netket（Python/JAX）

- **理由**：成熟、JAX 生态；Python 包与现有 Python driver 体系同构，无第二语言进程模型。
- **备选未选**：自研 VMC（SR 优化器、采样器都要自己硬化，周期不可控）。
- **不可用路径**：环境探测失败时 `backend-not-connected`（与 Sunny/ITensor 同规则）。
