# M1 五类协议试标

本目录包含五个 Q0 协议试标，用于验证[金标准标注指南](../gold-standard-annotation-guide-v0.1.md)和[评估契约 v0.2](../evaluation-contract-v0.2.md)，不用于证明预测能力。

## 样本矩阵

| 盲标 ID | 选择目标 | `data_cutoff` | 初步状态 | 主要测试问题 | 认证 |
|---|---|---|---|---|---|
| `pilot-a17` | 趋势扩张 | 2024-03-14 00:00Z | `up + expansion + stable` | 强价格趋势与短期宏观反向信号如何共存 | Q0 |
| `pilot-b04` | 衰竭 | 2024-04-20 00:00Z | `up + exhaustion + fragile` | 衰竭是否会被误写成已反转 | Q0 |
| `pilot-c22` | 区间 | 2024-07-04 00:00Z | `range + maturity + fragile` | 中期无位移与短期突破尝试如何组合 | Q0 |
| `pilot-d09` | 弃权 | 2024-09-18 16:00Z | `uncertain + transition + critical` | 临近未建模事件时是否拒绝伪精确 | Q0 |
| `pilot-e31` | 转换 | 2024-11-07 00:00Z | `down + transition + critical` | 一次结构破坏何时只是转换而非新趋势 | Q0 |

“选择目标”只用于回顾性覆盖设计。正式双盲时，文件名和输入物中不得出现该列。

## 数据与限制

价格证据来自公开的 XAU/USD 历史数据副本，日线和 4 小时数据包含 OHLCV，但来源页面未充分说明时区、bar 时间戳语义、首次可得时间和生产使用许可。宏观辅助证据来自 FRED 当前下载的历史序列，但本轮未取得完整 vintage。

因此：

- 所有 `available_at` 都是保守推定，不是生产级证明。
- 所有样本都标记 `availability_verified=false`。
- 结构已迁移到 v0.2，但认证仍为 Q0。
- `pilot-d09` 只对未来预测弃权，条件场景概率为 `null`。
- 事后已知结果未写入 frame。
- 样本选择是 `retrospective_target_sampling`，不得计入命中率、Brier 或模型优势统计。

## 文件

- `evidence/*.json`：截止时点证据包。
- `frames/*.json`：符合当前 Market Cognition Frame 契约的 Q0 帧。
- `pilot-findings.md`：试标暴露的问题与下一步。

## 来源

- [XAU/USD 历史数据集](https://huggingface.co/datasets/ZombitX64/xauusd-gold-price-historical-data-2004-2025)
- [FRED 10 年期实际利率 DFII10](https://fred.stlouisfed.org/series/DFII10)
- [FRED 广义美元指数 DTWEXBGS](https://fred.stlouisfed.org/series/DTWEXBGS)
- [Federal Reserve 2024 FOMC 日历](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
