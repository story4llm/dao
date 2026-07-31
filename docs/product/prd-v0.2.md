# DAO 产品需求文档 v0.2：现货与单月黄金期货双研究轨

- 状态：Accepted for research
- 日期：2026-07-31
- 继承：[PRD v0.1](prd-v0.1.md)
- 关联决策：[ADR-0006](../decisions/ADR-0006-separate-comex-gc-contract-track.md)

## 1. 产品目标

DAO 继续维护“给定 `as_of` 与 `data_cutoff` 的可证伪市场信念状态”，不输出交易指令。v0.2 在 XAU/USD 之外增加单一明确月份的 COMEX GC 黄金期货，使内部研究者可以在不混用现货和期货语义的前提下比较两个独立市场状态。

## 2. 支持范围

| 轨道 | 标的 | 主尺度 | 辅助尺度 | 主价格 |
|---|---|---|---|---|
| Spot | `XAUUSD` | OANDA complete D | 同源 H4 | `mid.c` |
| Futures | `GC<month><year>` | 单月 COMEX daily | 同月 H4 | `settlement` |

两个轨道复用 Evidence、MCF、Delta 和三分类认知方法，但 Feature、Baseline、Forecast、Resolution、日历和数据许可相互隔离。

## 3. GC 用户流程

1. 用户选择一个明确上市月份并提供获许可的私有合约规格、交易日历、daily settlement、H4 和宏观/事件快照。
2. runtime 核验合约身份、交割生命周期、逐记录可得时间、哈希和历史覆盖。
3. runtime 冻结 settlement C0、ATR(20)、五-session 日历和历史频率基线。
4. AI 形成竞争假设、状态三轴、“形势机时位信”、反方证据和失效条件。
5. 首轮概率严格等于冻结基线；窗口接近交割、数据不足或许可不明时弃权。
6. 到期用同一合约 settlement 追加解析，不自动换月。

## 4. P0 验收

- XAU/USD 原有 bundle 继续通过。
- 合格的单月 GC bundle 能生成 ready run 并通过 schema 与跨文件硬门。
- 连续合约、合约月份混用、GC/现货字段混用、跨 First Position/Last Trade Date 的窗口被拒绝。
- GC Forecast 冻结合约生命周期和五-session hash。
- 运行手册能让数据权利人在本地完成 prepare、validate、cognize、revalidate。

## 5. 非目标

- 自动选择主力、按成交量换月或构造连续合约；
- 分钟级/实时预测；
- 实盘、保证金、仓位与交割建议；
- 用公开网页替代授权快照；
- 在没有真实样本外评估时宣称 GC 预测优势。

