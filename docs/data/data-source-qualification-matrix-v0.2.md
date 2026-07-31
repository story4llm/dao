# 数据源资格矩阵 v0.2：XAU/USD 与 COMEX GC

- 状态：Accepted for dual-track runtime
- 日期：2026-07-31
- 适用标的：OANDA `XAU_USD`；单一明确月份的 COMEX Gold Futures `GC`
- 关联决策：[ADR-0004](../decisions/ADR-0004-github-harness-private-evidence-runtime.md)、[ADR-0006](../decisions/ADR-0006-separate-comex-gc-contract-track.md)

## 1. 结论

XAU/USD 继续执行 [v0.1 矩阵](data-source-qualification-matrix-v0.1.md)。新增 GC 研究轨只条件接受账户持有人已获许可的 CME DataMine、CME API 或等价供应商私有快照。公开延迟网页、图表和未声明 roll rule 的“主力连续”代码仍只能用于 Q0 探索。

| 研究轨 | 主价格 | 辅助价格 | 资格 |
|---|---|---|---|
| XAU/USD | OANDA `XAU_USD` complete midpoint D | 同源 H4 | 延续 v0.1 conditional pass |
| COMEX GC | 单一上市月份的官方/授权 daily settlement | 同一月份的 H4 trade OHLC | **Conditional pass** |
| GC 连续合约 | 需独立 ILA、roll rule 和 point-in-time constituent | 不适用 | 暂不支持 certified |

## 2. GC 合约身份硬门

每次 GC run 必须冻结：

- `GC<month-code><2-digit-year>` 合约代码，例如 `GCZ26`；
- 产品 `GC`、venue `COMEX`、合约月份；
- First Position Date 与 Last Trade Date；
- 100 金衡盎司、美元/盎司、0.10 美元 tick；
- `continuous=false`、`roll_policy=none`；
- `America/Chicago`、`cme-gc-settlement:0.1.0`；
- 截止后五个完整交易所 session 及其 SHA-256。

五日窗口必须完全早于 First Position Date 与 Last Trade Date。无法证明时阻断，不能静默换月。

## 3. 私有输入格式

`prepare-gc` 接收四类授权 JSON 源文件：

1. `instrument_spec`：合约规格和交割生命周期；
2. `contract_calendar`：准确的未来五个完整交易 session；
3. `price_daily`：至少 278 条同一合约完整日线，OHLC、`settlement`、`available_at`、volume/open interest；
4. `price_h4`：至少 30 条同一合约完整 H4 trade OHLC 与 `available_at`。

每日主参考字段只能是 `settlement`。H4 的 `close` 只用于辅助结构，不得替代 settlement 或与另一月份拼接。输入转换器保存源文件和规范化文件的独立哈希。

## 4. 许可与留存

CME 官方资料说明 DataMine 通过获授权 API ID 提供已购买历史文件；连续价格序列需要相应 Information License Agreement。用户必须依据自己的实体、用途和交付方式核验许可，程序不会因为文件可读取就自动判定可用于 AI。

私有环境保存原始/规范化行情、凭据和 entitlement 信息。GitHub 只保存许可允许的合约边界、哈希、记录数和派生 Feature/Baseline/MCF，不保存可还原的完整 CME 行情。

官方参考：

- [GC 合约规格](https://www.cmegroup.com/market-regulation/files/gold-futures-and-options-fact-card.pdf)
- [DataMine API](https://www.cmegroup.com/datamine/datamine-api.html)
- [DataMine List API](https://www.cmegroup.com/datamine/datamine-list-api.html)
- [CME Continuous Price Series](https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html)
- [CME 数据许可](https://www.cmegroup.com/market-data/license-data.html)

## 5. Certified / Exploratory

GC certified 必须同时通过合约身份、许可、日线/H4 完整性、逐记录可得时间、源文件哈希、合约日历、宏观/事件覆盖、Feature 与 Baseline 冻结。任一失败时输出 blocked/Q0；预测弃权，概率为 `null`。

真实 GC 数据尚未经过本仓库的账户级运行，因此本矩阵只接受软件管线的条件资格，不代表已取得数据权利或预测优势。

