# 每日黄金趋势认知运行手册

本手册定义用户如何让 AI 读取 GitHub Harness，并执行一次 XAU/USD 趋势认知。它不要求建设前端，也不连接交易账户下单。

## 1. 一次运行的输入

AI 必须同时获得两类输入：

### GitHub Harness

至少读取：

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `prompts/daily-cognition-run-v0.1.md`
- `docs/data/data-source-qualification-matrix-v0.1.md`
- `evals/evaluation-contract-v0.2.md`
- 六类输出 schema

### 私有证据包

最小覆盖：

- XAU/USD 完整日线至少 60 个交易日。
- XAU/USD 完整 4 小时 bar 至少 30 条。
- 去密钥请求清单、抓取时间、响应哈希和 provider。
- 截止时点前最新可得的实际利率/名义利率与美元环境证据。
- 未来 5 个交易日已知重大事件时钟。
- 与结果协议一致的最后完整日线收盘和冻结 ATR(20) 输入。
- 预先冻结的朴素基线概率；缺失时预测必须弃权。

私有证据可以作为当前会话附件提供，也可以由有权限的本地 Agent 从 `runtime/private/` 读取。不得把 token 发在聊天中。

清单结构以 `schemas/evidence-manifest.schema.json` 为准，可从 `templates/evidence-manifest.json` 创建。模板中的 URL、日期、字节数、哈希和 request ID 都必须替换为本次真实值。

## 2. 标准运行顺序

1. **Load**：读取 Harness 和上一份有效认知帧。
2. **Freeze**：确认 `as_of`、`data_cutoff` 和最后完整 bar。
3. **Gate**：检查许可、时区、完整性、陈旧度、首次可得时间和哈希。
4. **Observe**：只写来源直接支持的观察，不做趋势叙事。
5. **Compete**：至少建立两个能被证据区分的假设。
6. **Cognize**：形成方向、生命周期、稳定性和“形、势、机、时、位、信”。
7. **Forecast**：从冻结基线出发生成三类情景概率；无基线或未校准时弃权。
8. **Challenge**：检查反方证据、重复来源、事件风险和分布外状态。
9. **Delta**：与上一帧比较；首帧明确记录无前序帧。
10. **Emit**：输出 run manifest、Evidence、MCF、Forecast、Delta 与简短忠实解释。
11. **Resolve**：第 3 个完整交易日只诊断；第 5 个完整交易日追加正式 Resolution Record。

## 3. Certified 与 Exploratory

| 模式 | 核心证据 | 允许输出 |
|---|---|---|
| `certified` | 价格源、时点、许可和快照全部通过 | Q1 候选 MCF、可冻结 Forecast；Q2/Q3 仍需审议和到期解析 |
| `exploratory` | 可使用截图或公开网页，但至少一项硬门未通过 | Q0 观察与竞争假设；核心价格不合格时预测概率必须为 `null` |

模式不能由语言风格决定，只能由数据门决定。

## 4. 可直接使用的调用 Prompt

将私有证据包作为附件添加后，对已连接 GitHub 的 AI 发送：

```text
@GitHub 读取 story4llm/dao 的 AGENTS.md、
prompts/daily-cognition-run-v0.1.md 和其中列出的最小上下文。

以我本次附加的私有证据包执行一次 XAU/USD 每日趋势认知：
- mode: certified
- horizon: 截止后第 5 个完整交易日
- 日线为主，4 小时辅助

先运行数据资格门，再生成 Market Cognition Frame、Forecast Contract；
若存在上一帧则生成 Cognition Delta。严格使用 data_cutoff 前证据，
不要自行从公开网页补行情。任何硬门失败时改为 blocked/exploratory，
明确缺失项并预测弃权，不要填占位概率。
```

没有私有证据包时，可把 `mode` 改为 `exploratory`。此时系统用于研究问题，不形成可评分预测。

## 5. 每次运行的最小输出

建议目录：

```text
runs/YYYY/MM/DD/<run_id>/
├── run.json
├── evidence-manifest.json
├── market-cognition-frame.json
├── forecast-contract.json
├── cognition-delta.json
└── explanation.md
```

受限原始行情不进入上述 GitHub 目录。`evidence-manifest.json` 只保存哈希、边界和质量摘要。

## 6. 发布与回写

- AI 先在会话或本地工作区生成产物并校验。
- 只有许可允许的派生记录才能回写 GitHub。
- 原始 MCF 和 Forecast 冻结后不可事后覆盖；新证据产生新帧和 Delta。
- 到期只追加 Resolution Record。
- ChatGPT 的 GitHub 连接若只读，则下载产物后由用户或本地 Git 客户端提交；运行协议不依赖连接器写权限。
