# 数据源资格矩阵 v0.2：XAU/USD 与 COMEX GC

- 状态：Accepted for dual-track runtime（GC 部分于 2026-07-31 改为 Kaggle 数据集）
- 日期：2026-07-31
- 适用标的：OANDA `XAU_USD`；COMEX Gold Futures `GC`（Kaggle 数据集）
- 关联决策：[ADR-0004](../decisions/ADR-0004-github-harness-private-evidence-runtime.md)、[ADR-0006](../decisions/ADR-0006-separate-comex-gc-contract-track.md)（Superseded）、[ADR-0009](../decisions/ADR-0009-kaggle-gc-dataset-track.md)

## 1. 结论

XAU/USD 继续执行 [v0.1 矩阵](data-source-qualification-matrix-v0.1.md)。GC 研究轨的唯一数据源是公开 Kaggle 数据集 `youneseloiarm/comex-gold-futures-dataset-gc-contract`，通过官方 `kaggle` CLI 下载。该数据集派生自 TradingView，不是交易所官方数据，因此 GC 轨整体资格为 **exploratory / Q0**，不参与 certified。

| 研究轨 | 主价格 | 辅助价格 | 资格 |
|---|---|---|---|
| XAU/USD | OANDA `XAU_USD` complete midpoint D | 同源 H4 | 延续 v0.1 conditional pass |
| COMEX GC | Kaggle 数据集 daily OHLCV 的 `Close` | 无（daily-only） | **Exploratory / Q0，certified 不适用** |

## 2. GC 数据语义硬门

每次 GC run 由 `prepare-gc` 程序强制：

- `instrument=GC`、`provider_id=kaggle`、`source_type=kaggle_dataset`；
- `dataset_ref` 默认且文档统一为 `youneseloiarm/comex-gold-futures-dataset-gc-contract`；
- 主参考价格为数据集 `Close`；**不声称** Close 是 CME 官方 settlement；
- **不声称**数据属于某个明确交割月份，也不声称是非连续合约；
- 行级时间语义为 `dataset_observation_date`（数据集只有日期，不伪造 `available_at` 或交易所结算时刻）；
- 日期可解析、升序、唯一；OHLC 为正且边界一致；volume 非负；
- 至少 278 条完整日线（ATR20 + 5 日 horizon + 252 个 baseline origin）；
- 数据过旧（默认 10 天，`freshness_max_days` 可配置）时 blocked，预测弃权；
- 原始 ZIP、解压文件与规范化日线仅保存在 private root，公开目录只保留哈希与派生冻结量。

## 3. 下载与完整性

`prepare-gc` 通过官方 Kaggle CLI（`subprocess`，无 shell）执行 `kaggle datasets metadata` 与 `kaggle datasets download`，保留 metadata 与原始 ZIP，记录 CLI 版本、下载时间、dataset ref、文件名、大小与 SHA-256，并安全解压（拒绝路径穿越）。CSV 由列结构自动识别；多个候选时必须失败，不静默取第一个。

## 4. 认证与留存

Kaggle 认证完全由官方 CLI 处理（`kaggle auth login`、`KAGGLE_API_TOKEN`、`~/.kaggle/access_token`、旧版 `~/.kaggle/kaggle.json`）。DAO 不解析或保存 token；任何配置、manifest、日志和异常信息中都不得出现 token。

官方宏观与事件快照仍由 prepare 命令从白名单官方 HTTPS `source_locator` 自动下载并保存到 gitignored private root，许可、时点、freshness、哈希和 schema 门不变。

数据集在 Kaggle 页面上的许可条款由使用者自行核验；manifest 中许可字段记录为 `unknown`，程序不会因为文件可下载就升级数据资格。

## 5. 运行模式

GC 默认且仅支持 `automated` 模式；数据资格记录为 exploratory/Q0，`certified_eligible=false`。GC run 不允许输出声称为 CME 官方认证的 Q1 认知帧。数据缺失或过旧时必须 blocked，Forecast 弃权。XAU/USD 的 certified 能力不受影响。
