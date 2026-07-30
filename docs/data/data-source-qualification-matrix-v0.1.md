# 数据源资格矩阵 v0.1

- 状态：Accepted for first runtime
- 日期：2026-07-30
- 适用标的：`XAU/USD`
- 适用尺度：日线为主、4 小时辅助、未来 3—5 个完整交易日
- 关联决策：[ADR-0004](../decisions/ADR-0004-github-harness-private-evidence-runtime.md)

## 1. 结论

第一阶段不把 COMEX GC 改成主标的，也不把公开网页报价当作可回放行情源。

首个可运行组合为：

| 层 | 首选来源 | 结论 |
|---|---|---|
| XAU/USD 日线与 4 小时 | OANDA REST v20 `XAU_USD` | 条件通过；只允许账户持有人内部研究，原始响应不得进入公开仓库 |
| 名义/实际利率 | 美国财政部每日收益率与实际收益率曲线 | 前瞻采集通过；历史首次可得时间需以留存快照证明 |
| 美元环境 | Federal Reserve H.10 原始发布 | 前瞻采集条件通过；记录发布批次和实际抓取时间 |
| FOMC 事件 | Federal Reserve FOMC calendar / statement pages | 前瞻事件时钟通过 |
| CPI、就业 | BLS release calendar 与原始发布页 | 前瞻事件时钟通过 |
| PCE、GDP | BEA release schedule 与原始发布页 | 前瞻事件时钟通过 |
| 期货持仓 | CFTC COT 原始文件与 release schedule | 条件通过；必须区分周二报告时点与周五发布时间 |

这是一项数据与运行边界决策，不代表上述来源已经证明模型具有预测优势。

## 2. Q1 硬门

某个数据项只有同时满足以下条件，才能进入 Q1 证据包：

1. 能识别具体标的、字段、单位和频率。
2. 能证明时区和时间戳表示开盘、收盘、事件还是发布时间。
3. 价格 bar 已完成，不能把正在形成的 bar 当作完整事实。
4. `available_at <= data_cutoff`，并保留支持该判断的响应元数据。
5. 能冻结原始响应或等价快照，并计算 SHA-256。
6. 能说明许可范围；受限数据只在许可人私有运行环境中使用。
7. 历史回放时能重建当时版本；不能用今天的最终值覆盖旧预测。
8. 缺失、陈旧、修订或交易日异常都有显式状态。

只满足“网页现在能看到”不等于通过 Q1。

## 3. 价格源

| 候选源 | 频率与语义 | 时点与回放 | 许可与存储 | 资格 |
|---|---|---|---|---|
| OANDA REST v20 `XAU_USD` | 提供历史 candle；可选 bid/ask/mid；candle 带 `complete`；返回时间为 UTC；日线可用 `dailyAlignment` 与 `alignmentTimezone` 固定边界 | 官方介绍称历史价格可追溯至 2005 年，单页最多 5000 条；每次运行必须保存请求参数、响应头 `RequestID`、抓取时间和响应哈希 | API 协议限定内部使用，不得向第三方发布或提供价格；原始响应只能进入 `runtime/private/` | **Conditional pass**，首期选择 |
| 经纪商 MT5/Exness 导出 | 可导出 XAUUSD bar，但服务器时区、夏令时、合约定义和历史修订依赖经纪商 | 若同时保存 symbol specification、服务器时间说明和导出时点，可用于探索 | 未核验具体数据许可；不能默认可回放或公开 | Q0；补齐文件后重审 |
| 公开图表、截图、聚合网页 | 常能观察当前价与图形，但 bar 边界和首次可得时间通常不完整 | 无法稳定重建历史版本 | 页面展示权不等于数据再利用权 | 仅 exploratory；不得升级 Q1 |
| CME DataMine / 官方 GC 数据 | 有官方 settlement、成交和更细粒度数据；期货还需具体合约、交易日历与换月规则 | 官方历史源，可购买和提取；适合未来 GC 独立研究轨 | 非展示研究与分发分别需要相应许可；连续合约还需要 ILA | **Future conditional pass**；不作为本期 XAU/USD 主源 |
| CME 公开延迟页面 | 可核对部分日结算 | 不提供本项目所需的稳定 H4 回放契约 | 页面访问不代表可建立公开历史数据库 | 不满足首期 Q1 |

OANDA 参考：

- [REST v20 Introduction](https://developer.oanda.com/rest-live-v20/introduction/)
- [Pricing / candle alignment](https://developer.oanda.com/rest-live-v20/pricing-ep/)
- [Candlestick definition](https://developer.oanda.com/rest-live-v20/instrument-df/)
- [API authentication](https://developer.oanda.com/rest-live-v20/authentication/)
- [API licence agreement](https://legal.oanda.com/?code=api_license_agreement_oau&language=en)

CME 参考：

- [CME DataMine](https://www.cmegroup.com/datamine.html)
- [CME data licensing](https://www.cmegroup.com/market-data/license-data.html)
- [CME continuous price series](https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html)

## 4. 宏观与事件源

| 来源 | 使用规则 | 首次可得时间 | 资格 |
|---|---|---|---|
| U.S. Treasury daily par / real yield curves | 直接使用 Treasury 页面、CSV 或 XML；记录观测日期、抓取时间和快照哈希 | Treasury 说明输入报价约在每个工作日 3:30 PM 取得；运行时仍以实际抓取时点为准 | 前瞻 Q1 |
| Federal Reserve H.10 | 直接使用 Board 原始发布，不通过二次聚合页；记录周度发布批次 | Board 说明双边数据通常每周一 4:15 PM 更新至前一周五 | 前瞻 Q1，接口变化时重审 |
| Federal Reserve FOMC | 保存会议日历、statement/press conference 的正式发布时间和访问时点 | 官方页面给出会议与发布时刻 | 前瞻 Q1 |
| BLS / BEA calendars | 保存未来 5 个交易日内事件名称、计划时间、时区和页面快照 | 计划可能变更，必须每次运行重新抓取 | 前瞻 Q1 |
| CFTC COT | `report_date` 与 `published_at` 分开保存 | 通常周五 3:30 PM ET 发布周二持仓；假日可能延迟 | 前瞻 Q1 |
| FRED / ALFRED | 不进入 DAO AI 运行证据 | 虽具备 vintage 能力，但当前服务条款禁止将 FRED 内容用于 AI 系统开发或训练 | **Rejected for AI runtime** |

政府来源参考：

- [Treasury interest-rate statistics](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics)
- [Treasury XML feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed)
- [Federal Reserve H.10](https://www.federalreserve.gov/releases/h10/hist/)
- [FOMC calendars](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
- [BLS release schedule](https://www.bls.gov/schedule/)
- [BEA release schedule](https://www.bea.gov/news/schedule)
- [CFTC COT release schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)
- [FRED legal terms](https://fred.stlouisfed.org/legal/)

## 5. 私有证据留存

受限原始数据必须保存在仓库之外的私有运行位置。GitHub 只保存：

- 数据源 ID 与资格版本。
- 请求参数的去密钥版本。
- `observed_at`、`available_at`、`recorded_at`。
- 原始响应 SHA-256 和字节数。
- bar 数量、首末时间和缺失检查。
- 许可名称、版本、范围和核验日期。
- 由许可允许公开的少量派生研究结论。

GitHub 不保存：

- API token、账号 ID 或经纪商凭据。
- OANDA/经纪商完整日线或 4 小时原始序列。
- 付费 CME 数据或可还原数据集的大量逐行摘录。
- 许可不允许向第三方提供的原始响应。

## 6. 运行模式

### `certified`

必须提供通过本矩阵的私有证据清单与哈希。核心价格证据缺失时不得生成可评分 Forecast Contract。

### Exploratory

允许使用用户截图或公开页面帮助形成问题和竞争假设，但所有产出保持 Q0。若核心价格序列或可用时点不能证明，`forecast.abstain=true`，概率为 `null`。

## 7. 残余风险

- OANDA 的具体可交易品种和协议主体随用户地区变化，运行前必须核对账户实际返回 `XAU_USD`，并保存用户实际接受的区域协议版本。
- 经纪商现货金是做市商价格，不是唯一的全球“现货真值”；研究中必须把 provider 写入标的定义。
- Treasury 与 Board 数据适合日级宏观背景，不应伪装成实时市场变量。
- 政府日历会修订；计划发布时间不是实际发布时间。
- GC 若进入第二研究轨，必须另建 ADR 定义具体合约、换月和连续合约规则。
