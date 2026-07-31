# ADR-0007：运行时自动采集官方宏观与事件快照

- 状态：accepted
- 日期：2026-07-31

## 背景

每次运行前由人手复制 Treasury、Federal Reserve 与 FOMC 文件，容易造成路径错误、时间戳漂移和重复劳动。运行器已经负责 OANDA/CME 私有数据采集，因此官方公开快照也应由同一运行流程在本地生成。

## 决策

1. `prepare-oanda` 与 `prepare-gc` 对 `official_snapshots` 默认启用自动下载；若配置中的 `path` 已存在且未设置 `auto_download: true`，继续兼容本地文件复制。
2. 自动下载只允许 HTTPS 且只允许 `home.treasury.gov`、`federalreserve.gov` 及其 `www` 子域。下载地址来自配置的 `source_locator`，不使用搜索结果、新闻页面或第三方代理。
3. 下载的原始响应写入 gitignored 的 private root，使用稳定的 role 文件名，并在 manifest 中记录 SHA-256、实际抓取时间和字节数。`available_at` 由成功收到响应的时间生成，不信任未来或手工填写的时间戳。
4. 下载失败、空响应、非官方地址、过期、未来时间、哈希不一致或 schema/跨文件校验失败仍然阻断 certified 运行。
5. 自动下载不等于自动接受许可。OANDA 凭据和账户持有人一次性许可声明仍必须由本地环境提供；运行器不会猜测、修改或绕过这些声明。

## 后果

- 每次运行无需人工准备三个官方文件，且可复现地保留原始响应和哈希。
- 官方页面格式变化会使运行明确失败，需要更新解析器或配置；不会静默使用不确定数据。
- 私有原始快照仍不进入 GitHub，公开产物只包含 provenance、时间边界和哈希。
