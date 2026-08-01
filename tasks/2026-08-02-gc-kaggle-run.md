---
id: 2026-08-02-gc-kaggle-run
status: completed
owner: codex
created_at: 2026-08-02
updated_at: 2026-08-02
---

# GC Kaggle 首次真实下载运行

## 范围

使用新版 GC daily-only 契约，通过官方 Kaggle CLI 下载默认数据集，生成并校验一次 ready run；不使用现货、网页行情或 CME settlement 旁路。

## 结果

- Kaggle CLI 2.2.4 已安装，`.env` 中的 `KAGGLE_API_TOKEN` 由 CLI 读取。
- 数据集下载、ZIP 保存、SHA-256、解压和 `GC_in_daily_new.csv` 自动识别均成功。
- 规范化得到 12,776 条 daily OHLCV 观测。
- 最后观测日为 `2025-10-14`；截至 `2026-08-01` 已陈旧约 291 天，超过默认 10 天 freshness 门。
- 运行正确生成 `blocked`，原因 `stale_dataset`；没有伪造 Forecast 概率。

## 残余风险

该 Kaggle 数据集当前未更新到可支持 2026-08-02 判断的日期。必须等待数据集更新或更换经新版 ADR/矩阵批准的数据集后，才能生成当前 GC 走势预测。
