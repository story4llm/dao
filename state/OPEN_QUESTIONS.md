# 开放问题

## 已决产品问题

- 第一位用户：内部趋势研究者。
- 首要场景：XAU/USD 日线/H4 与 COMEX GC（Kaggle 数据集，daily-only）的每日离线认知帧。
- 产品重心：可证伪、可修正的趋势认知，不输出买卖点位和仓位。
- 对外措辞：使用“研究状态”和“重新评估”，不展示交易动作。

详见 `docs/product/prd-v0.2.md`、ADR-0002 与 ADR-0009（ADR-0006 已被取代）。

## 认知契约

以下问题已由评估契约 v0.2 与 ADR-0003 决定：

- Cognition Delta 记录相邻帧、证据增减、三轴迁移、后验增量、场景变化、修正驱动和时间审计。
- 风险字段使用 `research_posture`。
- 状态弃权与预测弃权分开表达；预测弃权时概率为 `null`。
- Annotation Record 与 Resolution Record 已有最小 schema。
- `direction=range` 只允许 `formation`、`maturity` 或 `transition`。

仍待研究：

- “主导力量”应如何表达为可追溯关系，而不是 LLM 因果叙事？
- 多时间尺度状态如何组合而不重复计权？

## 数据

- 第一研究轨为 provider-qualified XAU/USD；第二研究轨为 Kaggle 数据集 GC（exploratory/Q0），两者不在同一 Forecast Contract 混用。
- OANDA REST v20 已被选为首期条件通过价格源；原始数据只允许账户持有人内部运行，不进入公开 GitHub。
- 政府宏观与事件证据优先直接使用 Treasury、Federal Reserve、BLS、BEA 和 CFTC 原始来源。
- FRED/ALFRED 当前条款与 DAO 的 AI 运行方式不兼容，不作为运行数据源。
- GitHub 保存规则、证据清单、哈希和派生认知；许可受限原始行情保存在私有运行环境。
- GC 唯一数据源为 Kaggle `youneseloiarm/comex-gold-futures-dataset-gc-contract`：daily `Close`、`dataset_observation_date` 语义，不声称 settlement、交割月份或 CME 认证。

仍待解决：

- 用户实际 OANDA/等价账户所在地区是否提供 `XAU_USD`，接受的协议版本是什么？
- Kaggle GC 数据集的更新频率、列结构稳定性与长期可用性如何监控？
- 首个 evidence bundle 的私有存储位置和保留周期是什么？
- 首期冻结字段已定为 OANDA midpoint `mid.c`，日线边界固定为 `America/New_York` 17:00。
- 第 5 个完整交易日按本次冻结的 OANDA complete daily session sequence 计数；仍需用首个真实 run 验证假日异常处理。
- Kaggle GC 序列（TradingView 派生）能否提供稳定的 252 个已解析 origin，其拼接方式对 ATR 与基线的影响是什么？
- 新闻、讲话和经济日历如何获得可靠的首次发布时间？
- 政府数据未来页面快照如何自动留存，且不依赖条款不兼容的聚合服务？

## 模型

- 第一版状态标签由规则、HMM/Markov switching 还是监督学习产生？
- 首个朴素基线已定义为同源历史 complete daily bar 的 5-session、0.5 ATR 三分类频率，至少 252 个已解析 origin；实际账户基线仍待本地冻结。
- 弃权阈值如何根据校准与业务效用确定？

## 评估

- 趋势生命周期、稳定性、双人分歧和弃权硬门已在 `evals/gold-standard-annotation-guide-v0.1.md` 定义，下一轮需用 Q1/Q2 检验可操作性。
- 首批五个 Q0 试标已覆盖扩张、衰竭、区间、弃权和转换；同五个时点是否适合在取得合格数据后升级为 Q1？
- 3—5 日方向情景已使用 `xauusd-direction-5d:0.2.0`：第 5 个完整交易日主评分，第 3 日诊断，0.5 倍截止 ATR(20) 为中性带。
- 状态认知与未来方向预测已物理分离：前者由 Q2 审议，后者由 Forecast/Resolution Contract 评分。
- ATR 中性带在多大样本上显示稳定、何时需要发布新协议版本？
- 用户决策质量如何评估，而不以短期盈亏作为唯一目标？
- 如何度量解释忠实度和 Agent 的证据重复？
