# 项目状态

- 最后更新：2026-07-31
- 当前阶段：Runtime Readiness
- 当前里程碑：M3 First Certified Cognition Run
- 总体状态：进行中

## 已完成

- 完成《从易经“观变”到 AI 黄金趋势智能系统》研究报告。
- 明确传统思想只提供认知框架，计算结论必须可验证。
- 建立 Harness 主规范、上下文路由、工作流和质量门。
- 建立“形、势、机、时、位”领域本体初稿。
- 建立 Evidence、Forecast、Market Cognition Frame 三类 schema 初稿。
- 建立多 Agent 输入、输出、汇合和失败协议。
- 完成 PRD v0.1，确定第一位用户、首要流程和 MVP 边界。
- 建立 L0—L5 趋势认知能力分级、认知测试矩阵和错误分类。
- 明确认知帧是可证伪、可修正的市场信念状态，代码只承担数据、回放、校验和评分。
- 完成金标准标注指南 v0.1，定义双阶段盲标、双人审议、后见偏差防护和弃权硬门。
- 建立 Q0—Q3 认证等级，避免把协议样例、单人标注和已解析金标混为一谈。
- 完成趋势扩张、衰竭、区间、事件前弃权和状态转换五类 Q0 试标。
- 将试标的概率和、证据引用、时间边界、覆盖类别和弃权状态加入自动质量门。
- 完成评估契约 v0.2，分离状态认知、未来概率和信念修正三条评估链。
- 预注册 `xauusd-direction-5d:0.2.0`：第 5 个完整交易日正式评分，第 3 日只作诊断。
- 将 Evidence 与 Market Cognition Frame 升级到 v0.2，并新增 Cognition Delta、Annotation Record、Resolution Record schema。
- 将状态弃权与预测弃权拆分；预测弃权不再填充占位概率。
- 将五份试标迁移到 v0.2 结构并继续锁定为 Q0，未打开未来窗口计算成绩。
- 完成数据源资格矩阵 v0.1，选择 OANDA REST v20 `XAU_USD` 作为首期条件通过价格源。
- 明确 Treasury、Federal Reserve、BLS、BEA 与 CFTC 原始来源的前瞻证据用途。
- 因当前条款与 AI 运行方式不兼容，排除 FRED/ALFRED 运行时接入。
- 接受 ADR-0004，将 GitHub Harness、派生认知记录与许可受限私有原始证据分层。
- 建立 `certified` / `exploratory` 双运行模式、每日 Runbook、固定 Prompt 与 Cognition Run schema。
- 完成“没有合格行情与基线时必须 blocked”的端到端安全干跑样例。
- 接受 ADR-0005，将 certified 判定升级为标准 JSON Schema Draft 2020-12 与跨文件程序双硬门。
- 新增 Feature Snapshot 与 Baseline Snapshot，冻结 C0、ATR(20)、mid.c、NY17 bar 边界、session sequence hash、历史窗口和代码版本。
- 实现 OANDA 私有准备器：从环境变量读取 token/account ID，先核验账户 `XAU_USD`，再采集 D/H4，保留 provider 原始响应与 complete-only 规范化响应。
- 实现 certified bundle 校验器，覆盖引用、时间、核心角色、概率和、outcome 唯一性、私有文件哈希、冻结量一致性与 Resolution 重算。
- 建立 18 项反例/数值/私有准备/凭据防泄漏/解析重算/畸形输入测试与 GitHub Actions；原先五类已知伪 certified 对象均被拒绝。
- 完成 runtime 评审 must-fix：收窄配置占位符门、统一 Resolution Decimal 边界复现、明确拒绝弃权 Forecast 评分，并稳定处理 CLI 畸形上游结构错误。
- 接受 ADR-0006 与 PRD v0.2，建立独立 COMEX GC 研究轨（其 CME 管线后被 ADR-0009 取代）。
- 接受 ADR-0009：删除 CME/DataMine 单月合约管线，GC 唯一数据源改为 Kaggle 数据集 `youneseloiarm/comex-gold-futures-dataset-gc-contract`，经官方 kaggle CLI 下载。
- 重写 `prepare-gc`：检查 Kaggle CLI → 下载 metadata 与原始 ZIP（保留并哈希）→ 安全解压 → 自动识别唯一 OHLCV CSV → 校验规范化 → 冻结 C0/ATR(20)/基线 → 生成 ready run 并通过 bundle 校验；数据过旧时输出 blocked。
- 预注册 `gc-kaggle-daily-direction-5d:0.1.0`：daily-only、Close 为主参考价（非官方 settlement）、按数据集后续完整日线顺序解析，不依赖 CME 日历。
- 更新 schema 与 bundle 校验：GC instrument 固定 `GC`、provider `kaggle`、无 H4/合约日历/交割生命周期要求；GC 帧禁止声称 Q1；XAU/USD 轨保持不变。
- 建立共 46 项自动测试，覆盖 Kaggle CLI mock、ZIP 路径穿越、CSV 列变体/冲突/过期、token 防泄漏、公开/私有边界与 XAU/USD 回归。

## 当前决策

- 先做离线、可回放、可评分的认知帧，不做自动交易。
- 第一研究轨为 XAU/USD（日线为主、H4 辅助）；第二研究轨为 Kaggle 数据集 COMEX GC（daily-only，exploratory/Q0）。
- 第一位用户是内部趋势研究者；首要场景是每日离线认知帧。
- v0.1 目标是稳定达到 L3 条件化推理，并建立可审计的 L4 信念修正。
- 先用 5 个试标样本修正标注规范，再扩展到 20—30 个金标准样本。
- 本轮五个样本只认证为 Q0；在时区、bar 语义、许可和历史可得时间可证明前，不得升级为金标准或用于性能统计。
- 金标准必须经过 point-in-time 冻结、双人独立标注、分歧审议和预注册解析。
- 当前状态由 Q2 审议标注评估，不能用未来涨跌作为唯一真值。
- 未来方向概率使用独立 Forecast/Resolution Contract 评分。
- 研究风险输出使用 `research_posture`，不再使用交易动作语义。
- `AGENTS.md` 是唯一主规范；其他工具入口保持轻量。
- 技术栈在数据许可、契约和 MVP 切片明确后再决定。
- GitHub 保存规则、清单、哈希与许可允许的派生记录；原始 OANDA/经纪商行情只在私有运行环境使用。
- GC 只有一套实现：Kaggle 数据集 + 官方 kaggle CLI；不声称 settlement、交割月份或 CME 认证，不支持 certified，数据过旧时 blocked/弃权。
- certified 运行必须提供合格私有 evidence bundle 和冻结基线；缺失时不得从网页补行情或填写占位概率。
- 首轮 Forecast 的概率必须逐项等于程序冻结的历史频率基线；未经新校准协议，LLM 不得凭叙事调整概率。
- OANDA 原始数据与 Kaggle 下载文件只允许由符合许可的本地 Agent 读取，不上传至不符合许可的第三方 AI 会话；官方宏观/事件快照由 prepare 命令从白名单官方 HTTPS 地址自动下载到私有目录。
- Agent 默认使用 `automated` 模式：API key 是调用授权，许可字段仅作 provenance；`certified` 仍可显式启用以要求完整审计证明。

## 下一步

1. 数据权利人在仓库外选择 XAU/USD 或一个明确 GC 月份，填写实际许可证明。
2. XAU/USD 执行 `prepare-oanda`；GC 安装 `.[kaggle]` 并完成 `kaggle auth login` 后执行 `prepare-gc`，数据集与官方宏观/事件快照由运行器自动下载。
3. 在同一本地环境执行 `validate-bundle --private-root ...`，确认十个硬门、真实文件哈希与实际基线。
4. 由符合数据许可的本地 AI 按 `prompts/daily-cognition-run-v0.3.md` 生成对应轨道的首份 completed Q1 候选。
5. 再次通过 bundle 校验并进行人工时间完整性与反方审查。
6. 到第 3 日追加诊断，到第 5 日追加正式 Resolution Record。

## 阻塞与风险

- 本次 XAU/USD 运行已从 `.env` 读取账户凭据，并自动下载 Treasury、Federal Reserve H.10、FOMC 官方快照；输出位于本地 gitignored private root，未提交原始响应。
- GC 轨尚未对真实 Kaggle 数据集执行首次下载运行；数据集为 TradingView 派生、exploratory/Q0，不能证明真实预测优势。
- OANDA 条件通过只覆盖内部使用；完整价格响应不能放入公开 GitHub。
- 基线算法与契约已实现，但尚未在用户实际 OANDA 快照上冻结，因此当前仍没有可评分真实 Forecast。
- GitHub 连接无法访问私有行情；OANDA 原始数据与 Kaggle 下载文件不应上传云端，必须由符合许可的本地 Agent 读取私有目录。
- ATR(20) 的 0.5 中性带只是 v0.2 预注册选择，尚未通过样本外数据检验。
- 生命周期与稳定性主要依赖 Q2 专家审议，尚无市场唯一真值。
- 小规模金标准用于验证任务定义，不能证明统计优势。
- 传统概念映射仍需通过操作定义和样本外实验筛选。
- 宏观数据修订与新闻事件时间戳可能造成前视偏差。

## 恢复工作时

优先按 `docs/harness/DAILY_RUNBOOK.md` 在数据权利人的本地环境执行对应 prepare 命令与 `validate-bundle`。不要把 API token、account ID、CME entitlement 或原始受限行情提交到仓库/云端会话；不要用 TradingView、连续合约网页代码或公开报价补洞。
