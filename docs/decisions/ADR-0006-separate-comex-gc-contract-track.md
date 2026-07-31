# ADR-0006：以单一明确月份合约建立独立 COMEX GC 研究轨

- 状态：Accepted
- 日期：2026-07-31

## 背景

现有 DAO 第一研究轨固定为 OANDA `XAU_USD` midpoint、纽约 17:00 日线和 `xauusd-direction-5d:0.2.0`。COMEX Gold Futures（`GC`）是可交割期货，具有具体合约月份、First Position Date、Last Trade Date、官方 settlement、交易所日历和数据许可。把 GC 直接映射成 `XAUUSD`，或把不同月份机械拼成连续价格，会把基差和换月跳空错误地解释为趋势。

CME 官方资料确认标准 GC 每张合约代表 100 金衡盎司，按美元/金衡盎司报价，最小价格变动为 0.10 美元。历史数据可通过 DataMine 等授权渠道取得；CME Continuous Price Series 需要相应 Information License Agreement。软件可验证许可证明和哈希，但不能替账户持有人判断其具体授权范围。

## 决策

1. 保留 XAU/USD 现货研究轨，新增独立的 COMEX GC 研究轨；两者不得共享 Forecast、Feature、Baseline 或 Resolution。
2. 第一版 GC 只接受一个明确上市月份，规范标识为 `GC<month-code><2-digit-year>`，例如 `GCZ26`。产品代码固定 `GC`、venue 固定 `COMEX`。
3. 第一版不生成连续合约、不自动选择主力、不自动换月，`continuous=false`、`roll_policy=none` 是 certified 硬门。
4. 日线主价格字段固定为交易所或获授权供应商给出的 `settlement`；H4 使用同一月份合约的 OHLC close，只作辅助结构观察，不替代 settlement。
5. GC 使用独立解析协议 `gc-single-contract-direction-5d:0.1.0`。仍以截止后第 5 个完整交易所交易日正式解析、第 3 日诊断，使用截止时冻结的 settlement C0 与 ATR(20)，中性带 `[-0.5,+0.5] ATR`。
6. run 必须冻结合约月、First Position Date、Last Trade Date、100 oz 合约单位、0.10 美元 tick、`America/Chicago` 交易所时区和 CME 日历版本。
7. 第 3/5 日窗口必须完全早于 First Position Date 和 Last Trade Date；准备器无法证明时阻断，不静默换到另一月份。
8. 输入由账户持有人在私有环境提供。原始 CME/DataMine/经纪商文件不得进入公开仓库；公开产物只保留许可允许的派生量、边界、哈希和不含凭据的来源标识。
9. 在真实授权数据和样本外校准完成前，首轮概率仍逐项等于同一 GC 合约方法生成的冻结历史频率基线；软件支持不等于预测优势。

## 后果

### 正面

- GC 的合约身份、交割生命周期、价格字段和许可不会被现货语义掩盖。
- 换月跳空不会在第一版中被误计为趋势或 ATR。
- 现有认知帧、弃权和评分方法可以在独立协议下复用。
- 后续连续合约研究可以明确比较不同 roll policy，而不追溯改写已冻结预测。

### 代价

- 用户必须选择具体合约并提供同一月份的足够历史；远月合约可能缺少 252 个有效 origin。
- 单一合约历史频率可能受流动性生命周期影响，首版基线主要用于管线校验。
- 真实 certified 运行需要 CME/DataMine 或等价来源的实际授权和私有快照。

## 被拒绝的方案

- **把 GC 当成 XAUUSD 的别名**：价格字段、交易日历、交割与许可均不同。
- **默认使用网页上的“主力连续”代码**：roll rule、首次可得时间和再分发许可不可审计。
- **自动按成交量换月**：需要 point-in-time 全合约成交量、明确切换时刻和独立回测协议。
- **让 LLM 选择合约或补 settlement**：违反证据先于叙事和程序冻结原则。

