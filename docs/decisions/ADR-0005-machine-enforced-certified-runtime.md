# ADR-0005：Certified 由 Schema 与跨文件程序共同判定

- 状态：Accepted
- 日期：2026-07-30

## 背景

ADR-0004 定义了 GitHub Harness 与私有证据分层，但 v0.1 的机器实现只检查 Schema 文件能否解析及顶层字段是否存在。单个 JSON Schema 也无法完整表达概率和、跨文件引用、哈希匹配、结果重算和时间先后关系。

这使无效 run 仍可能被接受，例如：所有数据门失败却标记 completed、三项概率各为 0.9、重复三个 `up` outcome、或 resolved 记录没有价格与评分。

## 决策

采用两层、默认拒绝的 certified 判定：

1. 所有 JSON 产物必须先通过标准 JSON Schema Draft 2020-12 实例验证与 date-time format 检查。
2. 整个 run bundle 必须再通过跨文件语义验证，覆盖引用、时间、概率、哈希、冻结量和解析重算。
3. `certified` 的 ready/completed/resolved 状态必须同时具备：
   - 账户实际返回的 `XAU_USD` 品种证明；
   - 日线、H4、利率、美元环境和事件时钟五类 snapshot；
   - 许可人本地保存的原始/规范化私有文件与 SHA-256；
   - 冻结的 C0、ATR(20)、bar 边界、交易日历和 Feature Snapshot；
   - 截止时点前历史样本生成的冻结 Baseline Snapshot。
4. OANDA 采集器只从环境变量读取 token 与 account ID，不把它们写入参数、日志、manifest 或仓库。
5. OANDA 原始响应和完整规范化 candles 只写入显式私有目录；GitHub 只接收许可允许的 manifest、哈希和派生冻结量。
6. 首个运行的预测概率先等于冻结历史频率基线。LLM 可以形成状态解释和竞争假设，但在校准实验前不得自行改动程序概率。
7. ATR(20) 的操作定义固定为：用最近 21 个完整日线 bar 形成 20 个 True Range，并对这 20 个 TR 取 Wilder 初始均值；冻结值和输入 snapshot hash。该定义不改变 20 期窗口，只消除第一个 TR 需要前收盘价的歧义。
8. snapshot 的 `available_at <= data_cutoff`、`captured_at <= as_of`。采集时刻可以晚于某根 bar 的结束时刻，但不能晚于 run 的 `as_of`；因此不把 `captured_at <= data_cutoff` 错当成普遍规则。
9. `as_of` 表示本次市场状态的观察时点，不是 AI 完成写作的时刻；Forecast 的 `created_at` 必须不早于 `data_cutoff`，允许晚于 `as_of`。

## 后果

### 正面

- `certified` 从文档承诺变为可重复执行的机器判定。
- 无效概率、重复结果、时间穿越、哈希错配和伪 Resolution 会被自动拒绝。
- 私有数据不进入 GitHub，仍可通过哈希与冻结量审计。
- 第一份真实运行的阻塞项可以精确定位，不再由 AI 自行解释为“基本通过”。

### 代价

- 运行环境必须安装 `jsonschema`。
- 公开仓库无法独立重算许可受限行情；最终 certified 校验必须在持有原始文件的私有环境执行。
- 首个 bundle 仍需要用户本地的 OANDA token、account ID、区域许可证明和三类官方宏观/事件快照。

## 被拒绝的方案

- **只强化 JSON Schema**：不能可靠处理概率和、哈希、跨文件引用和评分重算。
- **只写自定义校验器**：会丢失通用 Schema 契约和工具互操作性。
- **把原始 OANDA 数据提交 CI**：违反私有留存与许可边界。
- **以 TradingView 或非官方下载器替代账户源**：不能满足许可和 point-in-time certified 标准。
