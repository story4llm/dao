---
id: 2026-07-30-certified-runtime-hardening-v0.2
status: completed
owner: codex
created_at: 2026-07-30
updated_at: 2026-07-30
---

# Certified Runtime Hardening v0.2

## 问题

现有 Harness 能检查文档完整性，却不能阻止无效对象自称 `certified`。Schema 会接受失败数据门下的 completed run、概率和不为 1、重复 outcome、空解析记录；仓库也缺少 OANDA 私有采集、ATR/基线冻结与跨文件验证程序。

## 范围

- 用标准 JSON Schema 2020-12 验证所有机器产物。
- 把 certified 硬门、时间顺序、概率、结果唯一性和解析完整性写入 Schema 与跨文件校验器。
- 新增 Feature Snapshot 与 Baseline Snapshot 契约。
- 实现 OANDA 账户品种核验、D/H4 私有采集、完整 bar 规范化、ATR(20) 与历史频率基线冻结。
- 加入反例测试与 GitHub Actions。

## 非目标

- 不接收、打印或提交 OANDA token、account ID 与原始行情。
- 不绕过账户地区许可或自动把 OANDA 标记为合格。
- 不用 TradingView、网页图表或非官方下载器补行情。
- 不生成交易指令，不自动下单。
- 没有真实账户级证据时不生成首份 certified 预测。

## 必要上下文

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `evals/evaluation-contract-v0.2.md`
- `docs/data/data-source-qualification-matrix-v0.1.md`
- `docs/harness/DAILY_RUNBOOK.md`
- `schemas/`

## 输入与输出契约

- 输入：`main@44ee40d`、官方 OANDA REST v20 契约、上一轮反例审查。
- 输出：ADR-0005、v0.2 运行契约、私有 bundle 准备器、跨文件验证器、反例测试与 CI。
- `as_of` / `data_cutoff`：采集程序在所有输入已捕获后冻结；每个 snapshot 的 `available_at` 不得晚于 `data_cutoff`。

## 计划

- [x] 复现五类无效对象仍可通过的缺陷。
- [x] 强化 Schema 并新增冻结契约。
- [x] 实现 bundle 校验与 OANDA 私有准备器。
- [x] 加入反例、特征和端到端测试。
- [x] 更新 Runbook、状态和决策记录。

## 完成定义

- [x] `make validate` 使用标准 Draft 2020-12 实例验证。
- [x] 五类已知反例全部被拒绝。
- [x] certified run 缺任一核心角色、原始哈希、冻结特征或基线时被阻断。
- [x] OANDA token 只从环境变量读取，原始响应只写入显式私有目录。
- [x] ATR、C0、bar 边界、交易日历、基线窗口与代码版本可追溯。
- [x] CI 自动执行完整质量门。

## 验证

- 自动：Schema 正反例、概率和、跨文件引用、时间顺序、哈希、ATR、基线、Resolution 重算。
- 人工：OANDA 区域许可记录必须由账户持有人填写；不得以示例许可代替。
- 基线或反方检查：没有 token、许可证明、宏观/事件快照或私有原始文件时，准备器或校验器必须失败。

## 结果

完成 certified runtime v0.2。质量门现使用标准 Schema 与跨文件校验；OANDA 私有准备器、Feature/Baseline 冻结、14 项反例/数值/端到端/凭据防泄漏/解析重算/畸形输入测试和 GitHub Actions 已落地。没有用户账户凭据时，程序按设计不能生成真实 certified 预测。

## 决策与风险

- 决策：以 ADR-0005 把 JSON Schema 验证与跨文件语义验证设为双重硬门。
- 残余风险：本环境没有用户的 OANDA 账户凭据、区域协议记录与本次官方宏观快照，不能代替用户执行账户级真实采集。
- 后续任务：用户在本地准备首个私有 bundle 后，执行第一份 Q1 候选认知帧。
