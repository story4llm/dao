# Daily Cognition Run Prompt v0.2

你正在执行 DAO 的一次黄金趋势认知运行。你的任务不是写随意行情评论，而是维护可追溯、可证伪、可修正、可评分的市场信念状态。

## 必读上下文

依次读取：

1. `AGENTS.md`
2. `state/PROJECT_STATE.md`
3. `docs/data/data-source-qualification-matrix-v0.1.md`
4. `docs/harness/DAILY_RUNBOOK.md`
5. `evals/evaluation-contract-v0.2.md`
6. `schemas/cognition-run.schema.json`
7. `schemas/evidence-manifest.schema.json`
8. `schemas/feature-snapshot.schema.json`
9. `schemas/baseline-snapshot.schema.json`
10. `schemas/evidence-item.schema.json`
11. `schemas/market-cognition-frame.schema.json`
12. `schemas/forecast-contract.schema.json`
13. 若有上一帧，再读 `schemas/cognition-delta.schema.json`

不要一次性读取与本次运行无关的研究报告。

## 输入

调用者必须给出：

- 由 `python -m dao_runtime.cli prepare-oanda` 生成的 ready run 目录。
- 对应的本地私有根目录；不得上传到不符合数据许可的第三方环境。
- 上一份认知帧（如果存在）。
- 运行模型与 Prompt 的精确版本。

任何凭据都不得出现在输出、日志、Prompt、manifest 或仓库文件中。

## 执行协议

### A. 先执行机器数据门

在能够访问私有根目录的本地运行环境执行：

```bash
python -m dao_runtime.cli validate-bundle \
  --run-dir <run-directory> \
  --private-root <private-directory>
```

只有 ready run 通过后才继续。不要通过文字判断替代该命令，不要手工把 gate 改成 `pass`。

任一核心门失败时：

1. 将 run 标记为 `blocked`。
2. 列出精确 `blocking_reasons`。
3. 可以输出 Q0 Observation 和待验证假设。
4. 必须预测弃权，三类概率为 `null`。
5. 不要自行从公开网页补行情；不得改用 TradingView、搜索结果、新闻摘要或记忆中的价格补洞。

### B. 观察

先生成 `evidence-items.json`。每条只陈述一个可追溯观察，并显式区分 Observation、Inference、Hypothesis、Decision。同源价格和派生指标必须共享 `dependency_group`。

程序冻结的以下值是只读的：

- `reference_close`
- `atr20_at_cutoff`
- Feature Snapshot hash
- Baseline Snapshot 的窗口、计数与概率
- bar 边界和交易日历版本

AI 不得重新计算、改写或用文字估计这些值。

### C. 竞争假设与当前认知

至少形成两个可被未来证据区分的假设。生成 Market Cognition Frame，包含：

- `up/down/range/uncertain`
- 生命周期与稳定性
- 状态后验，严格归一化为 1
- “形、势、机、时、位、信”的现代定义
- 支持与反方证据
- 可观察失效条件
- Q1 仅表示单次 point-in-time 候选，不表示预测优势

不输出入场、止损、止盈、仓位或保证性措辞。

### D. 首轮条件预测

固定使用 `xauusd-direction-5d:0.2.0`：

- 第 5 个完整交易日正式解析，第 3 日只诊断。
- 使用 Feature Snapshot 中的 C0 与 ATR(20)。
- 中性带为 `[-0.5,+0.5] ATR`，边界归入 `range`。
- 三个 outcome 必须恰好是 `up/down/range` 各一次。

在新的概率校准实验与协议版本完成前，三项预测概率必须逐项等于冻结 Baseline Snapshot。AI 可以解释状态和不确定性，但不得凭语言强弱调整概率。

### E. 观点变化与反方审查

若有上一帧，生成 Cognition Delta。每个变化必须归因于新证据、数据修订、模型/规则/Prompt 变化或单纯时间经过。

提交前检查：

1. 是否使用了 `data_cutoff` 后证据？
2. 是否重复计权同源信息？
3. 是否隐藏反方证据？
4. 是否修改程序冻结的数值？
5. 是否存在未建模重大事件？
6. 是否应当弃权？

### F. 输出并再次校验

输出顺序：

1. `run.json`
2. `evidence-manifest.json`
3. `feature-snapshot.json`
4. `baseline-snapshot.json`
5. `evidence-items.json`
6. `market-cognition-frame.json`
7. `forecast-contract.json`
8. `cognition-delta.json`（有上一帧时）
9. `explanation.md`

把 run 更新为 completed 后，必须再次执行 `validate-bundle`。任何失败都不能以人工说明覆盖。
