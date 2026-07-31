---
id: 2026-07-31-automatic-official-snapshot-download
status: completed
owner: codex
created_at: 2026-07-31
updated_at: 2026-07-31
---

# 自动下载官方快照

## 问题

运行前要求人类逐个复制官方宏观与事件快照，流程繁琐且容易引入错误时间戳。

## 范围

- 让 OANDA/GC prepare 命令从白名单官方 HTTPS 地址自动下载三个官方快照。
- 用实际响应时间、字节数和 SHA-256 生成 manifest 元数据。
- 保留一次性凭证与许可门，不自动猜测或绕过授权。
- 更新运行手册、数据资格说明、README 与测试。

## 非目标

- 不下载第三方行情、新闻或受限原始价格数据。
- 不把官方网页可见性升级为数据许可。
- 不自动下单或移除 certified 数据门。

## 验证

- 单元测试覆盖白名单、缺失 path 自动下载、失败响应与时间元数据。
- `make validate`。
- 在本地 `.env` 可用且官方端点可达时执行一次 prepare；失败必须留下可诊断错误。

## 结果

- [x] OANDA/GC 共用的官方快照复制器支持白名单 HTTPS 自动下载，并保留离线本地文件兼容路径。
- [x] `.env` 中的 OANDA 凭据可由 prepare 命令自动读取，不打印或写入产物。
- [x] 三个官方快照已在 `run-20260731-xauusd` 中下载并通过 `validate-bundle`。
- [x] `make validate` 通过（28 个单元测试）。
