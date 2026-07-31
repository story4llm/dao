# 每日黄金趋势认知运行手册

本手册定义用户如何让 AI 读取 GitHub Harness，并执行一次 XAU/USD 或单月 COMEX GC 趋势认知。两个研究轨使用独立价格字段、交易日历和解析协议；本系统不连接交易账户下单。

## 0. 运行边界与本地准备

OANDA token、account ID、CME entitlement、原始响应和完整价格序列只能进入数据权利人的私有运行环境。不要把它们粘贴到聊天、命令参数、GitHub Issue 或公开仓库。

安装：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

XAU/USD 复制 `templates/private-bundle-config.example.json`；GC 复制 `templates/private-gc-bundle-config.example.json`。在仓库外填写实际协议和一次性许可声明。`official_snapshots[].path` 可省略（或配置 `auto_download: true`），运行器会从 `source_locator` 的白名单官方 HTTPS 地址自动下载到 private root；仅在离线回放时才提供本地文件路径。示例中的 `REPLACE` 或 `example.com` 会被程序拒绝。

在本地交互式输入凭据，避免把值留在 shell history：

```bash
read -rsp "OANDA token: " OANDA_API_TOKEN
export OANDA_API_TOKEN
read -rp "OANDA account ID: " OANDA_ACCOUNT_ID
export OANDA_ACCOUNT_ID
```

生成私有输入与公开 ready run：

```bash
python -m dao_runtime.cli prepare-oanda \
  --config /private/path/private-bundle-config.json \
  --private-dir /private/path/runtime/private/run-YYYYMMDD-xauusd \
  --public-dir runs/YYYY/MM/DD/run-YYYYMMDD-xauusd
```

程序会先通过账户 instruments endpoint 确认实际存在 `XAU_USD`，再采集 midpoint D/H4，并自动抓取 Treasury、Federal Reserve H.10 与 FOMC 官方快照。所有原始响应写入 gitignored private root，manifest 记录实际抓取时间、字节数和 SHA-256；随后私有保存 provider 原始响应和 complete-only 规范化响应，冻结 C0、ATR(20)、bar 边界、session sequence hash 与历史频率基线。任何凭据都不会写入产物。

### 0.1 单月 COMEX GC

先把获许可的供应商文件在私有环境转换为模板定义的 JSON。必须是一个明确月份（如 `GCZ26`），不能是连续合约。日线至少 278 条并含 `settlement`，H4 至少 30 条；另提供合约规格和未来五个 CME session 日历快照。

```bash
python -m dao_runtime.cli prepare-gc \
  --config /private/path/private-gc-bundle-config.json \
  --private-dir /private/path/runtime/private/run-YYYYMMDD-gcz26 \
  --public-dir runs/YYYY/MM/DD/run-YYYYMMDD-gcz26
```

程序核验 100 oz、0.10 美元 tick、First Position Date、Last Trade Date、`continuous=false` 和五-session 窗口，再用 daily settlement 冻结 C0、ATR(20) 与同轨历史频率基线。它不会自动下载 CME 数据、选择主力或换月。

## 1. 一次运行的输入

AI 必须同时获得两类输入：

### GitHub Harness

至少读取：

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `prompts/daily-cognition-run-v0.3.md`
- `docs/data/data-source-qualification-matrix-v0.2.md`
- `evals/evaluation-contract-v0.3.md`
- Evidence Manifest、Feature、Baseline、Evidence、MCF、Forecast、Delta、Resolution schema

### 私有证据包

最小覆盖：

- XAU/USD 使用完整日线/H4和账户 instruments 快照；GC 使用至少 278 条同月 daily settlement、30 条同月 H4、合约规格和合约日历快照。
- 去密钥请求清单、抓取时间、响应哈希和 provider。
- 截止时点前最新可得的实际利率/名义利率与美元环境证据。
- 未来 5 个交易日已知重大事件时钟。
- 由程序生成的 Feature Snapshot，冻结 C0、ATR(20)、price field、对应日线边界与 session sequence hash。
- 由程序生成的 Baseline Snapshot，至少包含 252 个已解析历史 origin；缺失时预测必须弃权。

OANDA/CME 私有证据不得作为不符合数据许可的云端会话附件。它只能由有权限的本地 Agent 从私有目录读取；云端 AI 仅可读取许可允许的派生记录。不得把凭据发在聊天中。

清单结构以 `schemas/evidence-manifest.schema.json` 为准，必须由对应 prepare 命令根据真实文件生成，不再允许手工复制 manifest 模板。

## 2. 标准运行顺序

1. **Load**：读取 Harness 和上一份有效认知帧。
2. **Freeze**：确认 `as_of`、`data_cutoff` 和最后完整 bar。
3. **Gate**：检查许可、时区、完整性、陈旧度、首次可得时间和哈希。
4. **Verify**：运行 `validate-bundle --private-root ...`；失败时立即阻断。
5. **Observe**：只写来源直接支持的观察，不做趋势叙事。
6. **Compete**：至少建立两个能被证据区分的假设。
7. **Cognize**：形成方向、生命周期、稳定性和“形、势、机、时、位、信”。
8. **Forecast**：首轮概率逐项等于冻结基线；无基线时弃权。
9. **Challenge**：检查反方证据、重复来源、事件风险和分布外状态。
10. **Delta**：与上一帧比较；首帧明确记录无前序帧。
11. **Emit**：输出 run manifest、Evidence、MCF、Forecast、Delta 与简短忠实解释。
12. **Revalidate**：completed run 再次通过标准 Schema 与跨文件硬门。
13. **Resolve**：第 3 个完整交易日只诊断；第 5 个完整交易日追加正式 Resolution Record并重算评分。

## 3. Certified 与 Exploratory

| 模式 | 核心证据 | 允许输出 |
|---|---|---|
| `certified` | 价格源、时点、许可和快照全部通过 | Q1 候选 MCF、可冻结 Forecast；Q2/Q3 仍需审议和到期解析 |
| `exploratory` | 可使用截图或公开网页，但至少一项硬门未通过 | Q0 观察与竞争假设；核心价格不合格时预测概率必须为 `null` |

模式不能由语言风格决定，只能由数据门决定。

## 4. 可直接使用的调用 Prompt

在能够合法读取私有目录的本地 AI 环境发送：

```text
读取 story4llm/dao 的 AGENTS.md、
prompts/daily-cognition-run-v0.3.md 和其中列出的最小上下文。

以本地 ready run 与对应 private root 执行一次黄金每日趋势认知：
- mode: certified
- horizon: 截止后第 5 个完整交易日
- 日线为主，4 小时辅助
- 轨道、合约、price field 和 protocol 完全采用 ready run，不跨轨替换

先执行 validate-bundle，再生成 Market Cognition Frame、Forecast Contract；
若存在上一帧则生成 Cognition Delta。严格使用 data_cutoff 前证据，
不要自行从公开网页或 TradingView 补行情。首轮概率必须逐项等于
冻结 Baseline Snapshot。任何硬门失败时改为 blocked/exploratory，
明确缺失项并预测弃权，不要手工修改程序冻结值。
```

没有私有证据包时，可把 `mode` 改为 `exploratory`。此时系统用于研究问题，不形成可评分预测。

## 5. 每次运行的最小输出

建议目录：

```text
runs/YYYY/MM/DD/<run_id>/
├── run.json
├── evidence-manifest.json
├── feature-snapshot.json
├── baseline-snapshot.json
├── evidence-items.json
├── market-cognition-frame.json
├── forecast-contract.json
├── cognition-delta.json
└── explanation.md
```

受限原始行情不进入上述 GitHub 目录。`evidence-manifest.json` 只保存哈希、边界和质量摘要。

## 6. 发布与回写

- AI 先在会话或本地工作区生成产物并校验。
- certified 的最终机器校验必须在持有私有文件的本地环境执行。
- 只有许可允许的派生记录才能回写 GitHub。
- 原始 MCF 和 Forecast 冻结后不可事后覆盖；新证据产生新帧和 Delta。
- 到期只追加 Resolution Record。
- ChatGPT 的 GitHub 连接若只读，则下载产物后由用户或本地 Git 客户端提交；运行协议不依赖连接器写权限。
