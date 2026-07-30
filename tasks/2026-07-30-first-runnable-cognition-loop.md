---
id: 2026-07-30-first-runnable-cognition-loop
status: completed
owner: codex
created_at: 2026-07-30
updated_at: 2026-07-30
---

# 首个可运行黄金趋势认知闭环

## 问题

项目已有认知与评估契约，但用户还不能让 AI 读取 GitHub Harness 后按统一入口执行一次真实黄金趋势认知。数据许可、私有证据与 GitHub 记录之间也没有明确边界。

## 范围

- 完成数据源资格矩阵 v0.1。
- 确定首期 XAU/USD 与后续 GC 的边界。
- 定义 GitHub Harness 与私有证据分层。
- 建立每日运行手册、Prompt、run manifest schema 与模板。
- 用“无合格行情时阻断”样例验证不补数、不伪造概率。

## 非目标

- 不创建或保管用户 API token。
- 不下载或提交许可受限原始行情。
- 不生成当前真实黄金预测。
- 不自动下单。
- 不宣称 OANDA、任何 AI 或概率流程具有预测优势。
- 不把 Q0 样例升级为 Q1/Q2。

## 必要上下文

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `evals/evaluation-contract-v0.2.md`
- `docs/harness/QUALITY_GATES.md`
- `schemas/`

## 输入与输出契约

- 输入：现有 v0.2 认知/评估契约、候选数据源官方文档与许可。
- 输出：ADR-0004、数据源矩阵、每日运行 Prompt/Runbook、Cognition Run schema、模板和阻断样例。
- `as_of` / `data_cutoff`：运行时由每个 run 冻结；本任务不创建真实市场 run。

## 计划

- [x] 核验价格、宏观和事件候选源。
- [x] 选择首期条件通过的数据组合。
- [x] 定义 GitHub 与私有证据边界。
- [x] 定义 certified/exploratory 运行门。
- [x] 建立调用入口、run contract 与模板。
- [x] 增加阻断干跑样例和自动检查。
- [x] 更新 Harness、状态和决策记录。

## 完成定义

- [x] AI 有唯一的每日运行入口。
- [x] 数据源、许可、时区、bar 语义和首次可得时间有资格结论。
- [x] 许可受限原始数据不会进入公开仓库。
- [x] certified 模式缺少核心证据时不能继续预测。
- [x] 无基线时不能填充占位概率。
- [x] `make validate` 通过。

## 验证

- 自动：新文件、run schema 字段、阻断样例状态、缺失原因与输出边界。
- 人工：数据许可结论是否与官方条款一致；Prompt 是否会诱导 AI 从网页补行情。
- 基线或反方检查：以“GitHub 只有 Harness、没有私有数据”的情况干跑，预期必须 blocked。

## 结果

首个运行协议已经形成。用户可让 AI 读取 GitHub Harness，并附加私有 evidence bundle 执行 XAU/USD 每日认知。数据不合格时系统只保留 Q0 研究记录并预测弃权。

## 决策与风险

- 决策：接受 ADR-0004；首期使用 provider-qualified XAU/USD，原始受限数据私有留存。
- 残余风险：尚未提供账户级 OANDA 快照，因此还没有执行首个真实 certified run；概率基线仍需下一任务冻结。
- 后续任务：准备首个私有 evidence bundle 和朴素基线，执行第一份真实 Q1 候选认知帧。
