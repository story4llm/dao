# ADR-0009：GC 研究轨改为 Kaggle 数据集单一实现

- 状态：Accepted
- 日期：2026-07-31
- 取代：[ADR-0006](ADR-0006-separate-comex-gc-contract-track.md) 的 CME/DataMine 单月合约管线

## 背景

ADR-0006 设计的 GC 轨要求账户持有人提供 CME DataMine 或等价供应商的授权 JSON（合约规格、合约日历、daily settlement、同月 H4），并冻结单月合约身份与交割生命周期。实际运行中该前提无法满足：没有 CME 授权数据源，四个 source URL/API key 的配置成本让 GC 轨从未真实运行，合成测试数据也无法证明任何预测能力。

公开 Kaggle 数据集 `youneseloiarm/comex-gold-futures-dataset-gc-contract`（派生自 TradingView）提供可自动下载的 GC daily OHLCV 历史。它不是交易所官方数据，没有 settlement、交割月份和逐行可得时间，但足以支撑一条诚实标注为 exploratory 的日线方向研究轨。

## 决策

1. 删除 CME/DataMine 管线：`source_files.*`、`token_env`、`GC<month-code><year>` 校验、First Position/Last Trade Date、`continuous=false`、`roll_policy=none`、100 oz/0.10 tick 硬门、daily settlement、同月 H4、CME 五-session 日历与 `provider_id=cme-licensed-snapshot` 全部移出运行代码、schema、模板与主流程文档。不保留 fallback，不做 provider 分支。
2. GC 的唯一数据源是 Kaggle 数据集，唯一入口仍是 `python -m dao_runtime.cli prepare-gc`；下载通过官方 `kaggle` CLI（可选依赖 `.[kaggle]`），认证完全交给 CLI，DAO 不接触 token。
3. 新数据语义：`instrument=GC`、`provider_id=kaggle`、daily-only OHLCV、主参考价格 `Close`、`timestamp_semantics=dataset_observation_date`。不伪造 settlement、交割月份、合约日历或行级 `available_at`。
4. 新解析协议 `gc-kaggle-daily-direction-5d:0.1.0`：C0 为最新完整 daily Close；ATR(20) 用 daily OHLC；第 5 个后续完整 daily 观测正式解析、第 3 个仅诊断；解析按数据集中后续完整日线顺序，不依赖 CME session 日历；中性带沿用冻结 ATR ±0.5 倍（见评估契约 v0.3）。
5. 完整性要求：原始 ZIP 保留并记录 SHA-256；安全解压防路径穿越；CSV 由列结构自动识别（多候选必须失败）；日期升序唯一、OHLC 边界、volume 非负、≥278 条历史；数据过旧（默认 10 天，可配置）时 blocked 且 Forecast 弃权。
6. 资格定级：exploratory/Q0，`certified_eligible=false`；GC 默认 `automated` 模式，不支持 certified，不允许输出声称 CME 官方认证的 Q1。数据可下载不等于资格升级。
7. OANDA XAU/USD 研究轨的价格语义与认证流程不变。

## 后果

### 正面

- GC 轨第一次拥有可以真实运行的数据通路，一条命令完成下载、校验、冻结与验证。
- 数据身份诚实：不再用 schema 强迫使用者伪造 settlement 或合约月份。
- 私有/公开边界更简单：ZIP、CSV 和完整规范化日线只在 private root。

### 代价

- 数据质量依赖 Kaggle 数据集维护者；来源为 TradingView 派生，无官方审计链。
- 失去交割生命周期语义；期现基差和换月效应无法在本轨中区分。
- GC 轨永久停留在 exploratory 资格，除非未来引入官方授权数据源（届时需新 ADR）。

## 被拒绝的方案

- **保留 CME 管线作为 fallback 或 provider 分支**：两套实现的维护与审计成本远高于收益，且 CME 路径从未真实运行。
- **新增 `prepare-kaggle-gc` 第二命令**：用户入口翻倍、文档翻倍；`prepare-gc` 原地重写即可。
- **让 AI 手工下载 CSV 粘贴入仓**：绕过哈希与来源审计，违反证据先于叙事原则。
