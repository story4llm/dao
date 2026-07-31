---
id: 2026-07-31-comex-gc-trend-track
status: completed
owner: codex
created_at: 2026-07-31
updated_at: 2026-07-31
---

# COMEX GC 黄金期货趋势研究轨

## 问题

现有 runtime、schema 与评估协议只接受 OANDA `XAU_USD`。用户需要在不混用现货价格、交易日历和许可的前提下，对标准 COMEX Gold Futures（产品代码 `GC`）形成独立、可回放、可弃权的趋势判断。

## 范围

- 保留 XAU/USD 现货研究轨，新增单一明确月份 GC 合约研究轨。
- 定义 GC 合约身份、结算价、日线/H4、到期安全门、许可与私有留存边界。
- 从调用者提供的、已获许可的私有 GC 快照生成 ready run、Feature Snapshot 与 Baseline Snapshot。
- 扩展公共 schema 与 bundle 交叉校验，使 XAU/USD 与 GC 各自使用独立协议。
- 更新运行手册、Prompt、模板、测试与项目状态。

## 非目标

- 不自动选择“主力合约”、不自动换月、不拼接或回调连续合约。
- 不下载、提交或再分发未获许可的 CME 原始行情。
- 不接入实盘、保证金、持仓或下单。
- 不把 GC 与 XAU/USD 的价格字段、ATR、基线或解析记录混用。
- 不因完成软件支持而宣称 GC 模型已有预测优势。

## 必要上下文

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `docs/data/data-source-qualification-matrix-v0.1.md`
- `docs/harness/DAILY_RUNBOOK.md`
- `evals/evaluation-contract-v0.2.md`
- `schemas/`
- ADR-0004、ADR-0005

## 输入与输出契约

- 输入：单一 `GC<month-code><2-digit-year>` 合约的授权私有日线结算与 H4 快照、合约规格快照、三类官方宏观/事件快照及许可证明。
- 输出：独立 GC ready run、Evidence Manifest、Feature/Baseline Snapshot，以及可由 AI 补全的 MCF/Forecast 契约。
- `as_of` / `data_cutoff`：所有输入捕获后冻结；记录 `available_at`，且预测窗口不得跨越 First Position Date 或 Last Trade Date。

## 计划

- [x] 核验当前现货专用边界与 CME 官方合约/许可资料。
- [x] 接受 ADR-0006，冻结第一版 GC 合约与不换月决策。
- [x] 扩展 schema 和跨文件校验。
- [x] 实现私有 GC 快照规范化、特征/基线冻结和 CLI。
- [x] 增加模板、文档和正反例测试。
- [x] 运行完整质量门并完成反方审查。

## 完成定义

- [x] 一个合格的合成 GC 私有 evidence bundle 可以生成并通过 ready-run 校验。
- [x] GC 合约代码、合约月、First Position Date、Last Trade Date、venue、单位、tick、价格字段和日历可追溯。
- [x] 日线以 `settlement` 冻结 C0/ATR/基线；H4 只作辅助，不冒充 settlement。
- [x] 预测窗口可能跨 First Position Date 或 Last Trade Date 时必须拒绝。
- [x] XAU/USD 原有正例继续通过，GC/现货交叉引用和连续合约输入被拒绝。
- [x] `make validate` 通过，文档与状态同步。

## 验证

- 自动：schema、单一合约身份、日线/H4 完整性、Decimal ATR/基线、概率、哈希、到期安全门、跨轨混用反例。
- 人工：CME/DataMine/经纪商许可必须由数据权利人核验；本仓库测试只使用合成数据。
- 基线或反方检查：没有授权私有快照、合约身份不唯一、历史样本不足或窗口触及交割生命周期时必须阻断/弃权。

## 结果

完成 XAU/USD/GC 双研究轨 runtime v0.3。新增 `prepare-gc`、GC 私有规范化输入、合约/日历/交割生命周期硬门、settlement Feature/Baseline、独立 Forecast/Resolution protocol、schema 与跨文件隔离校验。合成 GC ready 和 completed cognition bundle 均通过；连续合约、合约月错配、缺日历、跨交割窗口和跨轨语义反例均被拒绝。

验证：激活 `.venv` 后执行 `make validate`，26 项测试全部通过；Harness 检查通过 65 个必需文件、10 个 schema、内部链接和 guardrails；`git diff --check` 与模板 JSON 解析通过。

## 决策与风险

- 决策：第一版只支持单一明确月份的标准 COMEX GC，不支持连续合约或自动换月。
- 残余风险：尚无用户授权的真实 CME/经纪商 GC 快照；当前只证明软件闭环，不证明数据许可、真实运行或预测优势。
- 后续任务：在实际数据许可下执行第一份 GC Q1 候选；连续合约需另立 ADR 与独立评估协议。
