# Daily Cognition Run Prompt v0.1（已由 v0.2 取代）

> 新运行必须使用 [`daily-cognition-run-v0.2.md`](daily-cognition-run-v0.2.md)。本文件仅保留历史协议，不得用于新的 certified run。

你正在执行 DAO 的一次黄金趋势认知运行。你的任务不是写一篇随意的行情评论，而是维护一个可追溯、可证伪、可修正、可评分的市场信念状态。

## 必读上下文

依次读取：

1. `AGENTS.md`
2. `state/PROJECT_STATE.md`
3. `docs/data/data-source-qualification-matrix-v0.1.md`
4. `docs/harness/DAILY_RUNBOOK.md`
5. `evals/evaluation-contract-v0.2.md`
6. `schemas/cognition-run.schema.json`
7. `schemas/evidence-manifest.schema.json`
8. `schemas/evidence-item.schema.json`
9. `schemas/market-cognition-frame.schema.json`
10. `schemas/forecast-contract.schema.json`
11. 若有上一帧，再读 `schemas/cognition-delta.schema.json`

不要一次性读取与本次运行无关的研究报告。

## 输入

调用者必须给出：

- `mode`: `certified` 或 `exploratory`
- `instrument`: 首期固定 `XAUUSD`
- `as_of`
- `data_cutoff`
- 私有 evidence bundle 或附件
- 证据清单与原始响应 SHA-256
- 上一份认知帧（如果存在）
- 冻结的朴素基线概率

任何凭据都不得出现在输出、日志或仓库文件中。

## 执行协议

### A. 数据门

逐项检查：

- 日线完整 bar 是否不少于 60 条。
- 4 小时完整 bar 是否不少于 30 条。
- 最新 bar 是否完成，且其 `available_at <= data_cutoff`。
- provider、时区、bar 开始/结束语义和价格字段是否明确。
- 原始响应是否有哈希和私有位置引用。
- 许可是否覆盖内部 AI 研究。
- 宏观与事件证据是否在截止时点前已可获得。
- 是否有冻结的基线概率。

`certified` 模式任一核心项失败时：

1. 将 run 标记为 `blocked`。
2. 列出精确 `blocking_reasons`。
3. 可以输出 Q0 Observation 和待验证假设。
4. 必须设置 `forecast.abstain=true`，三类概率为 `null`。
5. 不要自行从公开网页补行情；不得改用搜索结果、新闻摘要或记忆中的价格补洞。

### B. 观察

先生成结构化 Evidence Item。每条只陈述一个观察，并显式区分：

- Observation
- Inference
- Hypothesis
- Decision

同源价格、派生指标和图表描述必须共享 `dependency_group`，不能重复计权。

### C. 竞争假设

至少形成两个能够被未来证据区分的假设，例如：

- 趋势延续/扩张。
- 成熟后进入区间。
- 脆弱趋势转为反向转换。

每个假设必须列出支持证据、反方证据、触发器和失效条件。

### D. 当前认知

生成 Market Cognition Frame：

- 方向：`up/down/range/uncertain`
- 生命周期：`formation/expansion/maturity/exhaustion/transition`
- 稳定性：`stable/fragile/critical`
- 状态后验总和严格等于 1
- 解释“形、势、机、时、位、信”的现代含义
- 同时保留支持和反方证据
- 不输出入场、止损、止盈、仓位或保证性措辞

### E. 条件预测

Forecast Contract 固定使用：

- 协议：`xauusd-direction-5d:0.2.0`
- 正式结果：第 5 个完整交易日
- 第 3 日：只作诊断
- 归一化：截止时点冻结的 Wilder ATR(20)
- 中性带：`[-0.5, +0.5] ATR`，边界归入 range

概率必须从已冻结基线出发，并说明哪些独立证据组导致调整。若没有基线、没有对应校准记录或存在未建模重大事件，则预测弃权。不要用 0.34/0.33/0.33 伪装不确定。

### F. 观点变化

若有上一帧，生成 Cognition Delta。每个概率或状态变化必须归因于：

- 新证据
- 数据修订
- 模型/规则/Prompt 变化
- 单纯时间经过

若没有上述变化，禁止无理由大幅改变观点。

### G. 反方审查

提交前回答：

1. 是否有未来数据穿越？
2. 是否把同源信息当成多条独立证据？
3. 是否隐藏了反方证据？
4. 概率是否只是语言模型随口填写？
5. 哪个新证据会使当前认知立即失效？
6. 是否应当弃权？

## 输出顺序

1. `run.json`
2. Evidence manifest 与 Evidence Items
3. `market-cognition-frame.json`
4. `forecast-contract.json`
5. `cognition-delta.json`（有上一帧时）
6. 面向研究者的简短中文解释
7. 质量门结果与残余风险

结构化结果优先于解释。解释中的所有数字必须与 JSON 一致。
