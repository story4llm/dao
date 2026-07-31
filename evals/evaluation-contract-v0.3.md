# 评估契约 v0.3：XAU/USD 与 COMEX GC（Kaggle）

- 状态：Pre-registered dual-track research contract（GC 部分于 2026-07-31 更新为 Kaggle 数据集协议）
- 日期：2026-07-31
- 继承：[评估契约 v0.2](evaluation-contract-v0.2.md)
- 新增协议：`gc-kaggle-daily-direction-5d:0.1.0`

## 1. 不变规则

状态认知、条件预测和信念修正继续物理分离。第 5 个完整交易 session 正式评分，第 3 个只诊断；三分类仍为：

- `up`：\(d_5>0.5\)
- `down`：\(d_5<-0.5\)
- `range`：\(-0.5\le d_5\le0.5\)

仍使用冻结 ATR(20)、平均多分类 Brier、log loss、冻结基线 Brier 与 BSS。预测弃权时概率为 `null` 且不评分。中性区间为冻结 ATR 的 ±0.5 倍、边界取 `inclusive_range`，这一预注册选择对两条轨道一致，且未经过样本外检验。

## 2. GC 冻结量

GC Forecast 必须冻结：

- 截止前数据集中最后一条完整 daily 观测的 `Close` \(C_0\)；
- 同一数据集 daily OHLC 计算的 \(ATR_{20,0}\)；
- `dataset_ref`（`youneseloiarm/comex-gold-futures-dataset-gc-contract`）与原始 ZIP 的 SHA-256；
- `kaggle-gc-observed-daily:0.1.0` 观测日历与最近 21 条观测日期的 sequence hash；
- 同一数据集方法生成的历史频率基线。

解析按数据集中后续出现的完整日线顺序计算：第 3 个后续完整 daily 观测只用于诊断，第 5 个用于正式解析；不依赖预先提供的 CME session 日历。到期 \(C_3,C_5\) 必须来自同一 `dataset_ref` 的同一 `Close` 字段。数据缺失、列异常、日期重复或数据过旧时标记 `unresolvable` 或弃权，不得补值。

## 3. 基线与解释边界

第一版 GC 基线至少使用 252 个已解析 origin；每个 origin 使用同一数据集序列和当时 ATR。该数据集派生自 TradingView，非交易所官方数据，基线只用于管线校验，不足以宣称稳定优势。LLM 不得按叙事强弱调整冻结概率。

状态解释可以引用 daily OHLCV 结构、volume（若数据集提供则 open interest 为可选字段）、宏观和事件证据，但必须去重；数据集 `Close` 不能被表述为 CME 官方 settlement。

## 4. 协议隔离

`xauusd-direction-5d:0.2.0` 只能解析 `XAUUSD/mid.c/oanda-xauusd-ny17`。  
`gc-kaggle-daily-direction-5d:0.1.0` 只能解析 `GC/close/kaggle-gc-observed-daily`。

任何跨轨 Feature、Baseline、Forecast 或 Resolution 引用都是硬错误。GC 轨资格为 exploratory/Q0，评分结果不得表述为 CME 官方认证结论。
