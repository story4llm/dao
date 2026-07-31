---
id: 2026-07-31-automated-gold-futures-agent
status: completed
owner: codex
created_at: 2026-07-31
updated_at: 2026-07-31
---

# 自动黄金期货 Agent 运行

## 目标

让 Agent 能在已有 API 凭据和可访问数据源时自动下载、规范化并生成单月 COMEX GC 的趋势预测，不要求人类每次提供快照路径或重复许可确认。

## 实施范围

- 增加 `automated` ready/completed 运行模式。
- 许可状态从阻断门改为 provenance 元数据。
- GC source 配置支持 `url` 自动下载并保留本地文件回放兼容。
- 自动运行仍校验合约月份、时间边界、数据完整性、哈希和冻结基线。

## 尚未完成

- 需要一个包含实际 GC 合约、价格源 URL/API 凭据的本地配置，才能生成真实期货方向预测。

## 已完成

- [x] 默认 `automated` 模式；OANDA/GC 许可信息不再是启动阻断。
- [x] GC `source_files` 支持 `url`/`source_locator` 自动下载，并兼容离线 `path`。
- [x] GC `as_of`、`data_cutoff`、`resolution_sessions` 和自动下载源的抓取时间可由运行器生成。
- [x] 新增 `generate-baseline-forecast`，从 ready bundle 自动生成通过 Forecast Contract schema 的五 session 概率预测。
- [x] Schema、运行手册和测试已同步；`make validate` 通过。
