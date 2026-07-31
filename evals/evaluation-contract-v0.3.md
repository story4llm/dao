# 评估契约 v0.3：XAU/USD 与单月 COMEX GC

- 状态：Pre-registered dual-track research contract
- 日期：2026-07-31
- 继承：[评估契约 v0.2](evaluation-contract-v0.2.md)
- 新增协议：`gc-single-contract-direction-5d:0.1.0`

## 1. 不变规则

状态认知、条件预测和信念修正继续物理分离。第 5 个完整交易 session 正式评分，第 3 个只诊断；三分类仍为：

- `up`：\(d_5>0.5\)
- `down`：\(d_5<-0.5\)
- `range`：\(-0.5\le d_5\le0.5\)

仍使用冻结 ATR(20)、平均多分类 Brier、log loss、冻结基线 Brier 与 BSS。预测弃权时概率为 `null` 且不评分。

## 2. GC 冻结量

GC Forecast 必须冻结：

- 单一明确月份合约代码；
- 截止前最后完整交易日的 `settlement` \(C_0\)；
- 同一合约 settlement OHLC 计算的 \(ATR_{20,0}\)；
- First Position Date、Last Trade Date；
- 截止后五个交易所 session sequence hash；
- `America/Chicago` 与 `cme-gc-settlement:0.1.0`；
- 同一 GC 方法生成的历史频率基线。

到期 \(C_3,C_5\) 必须来自同一合约、同一 settlement 字段。任何换月、连续合约回调、不同供应商字段替换或跨交割生命周期窗口都标记 `unresolvable`，不得补值。

## 3. 基线与解释边界

第一版 GC 基线至少使用 252 个已解析 origin；每个 origin 使用同一合约序列和当时 ATR。由于单月合约流动性随生命周期变化，该基线首先用于管线校验，不足以宣称稳定优势。LLM 不得按叙事强弱调整冻结概率。

状态解释可以引用 settlement 结构、H4 trade bars、成交量、open interest、宏观和事件证据，但必须去重；H4 close 不能被表述为官方 settlement。

## 4. 协议隔离

`xauusd-direction-5d:0.2.0` 只能解析 `XAUUSD/mid.c/oanda-xauusd-ny17`。  
`gc-single-contract-direction-5d:0.1.0` 只能解析 `GC<month-year>/settlement/cme-gc-settlement`。

任何跨轨 Feature、Baseline、Forecast 或 Resolution 引用都是硬错误。

