# Daily Cognition Run Prompt v0.3

你正在执行 DAO 的一次黄金趋势认知运行。任务是维护可追溯、可证伪、可修正、可评分的市场信念状态，不是输出交易指令。

## 必读

1. `AGENTS.md`
2. `state/PROJECT_STATE.md`
3. `docs/data/data-source-qualification-matrix-v0.2.md`
4. `docs/harness/DAILY_RUNBOOK.md`
5. `evals/evaluation-contract-v0.3.md`
6. `schemas/` 中 run、manifest、feature、baseline、evidence、MCF、forecast 和 delta 契约

## 输入与轨道选择

调用者必须提供 `prepare-oanda` 或 `prepare-gc` 生成的 ready run 及对应 private root。先读取 `run.instrument`：

- `XAUUSD`：使用 `xauusd-direction-5d:0.2.0`、`mid.c` 与 OANDA NY17 日历。
- `GC`：使用 `gc-kaggle-daily-direction-5d:0.1.0`、Kaggle 数据集 daily `close` 与 `kaggle-gc-observed-daily` 观测日历。

绝不能把两个轨道的价格、ATR、基线或解析记录混用。

## 执行

1. 在持有私有文件的本地环境执行 `validate-bundle --private-root`。
2. 任一门失败时标记 blocked/Q0，预测弃权，三项概率为 `null`；不从网页补行情。
3. 先写 Observation，再形成至少两个竞争假设。
4. 生成方向、生命周期、稳定性和“形、势、机、时、位、信”，保留反方证据和失效条件。
5. 首轮 Forecast 概率逐项等于冻结 Baseline，不由 LLM 修改。
6. GC 必须再次确认 `dataset_ref`、原始 ZIP 哈希与数据新鲜度；`Close` 不得表述为 CME 官方 settlement，GC 帧不得声称 Q1。
7. 若有上一帧，只有同一 instrument 才生成 Delta。
8. completed run 必须再次通过 bundle 校验。

所有输出保持研究与决策辅助边界，不提供入场、止损、止盈、仓位或保证性措辞。

