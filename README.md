# DAO：AI 黄金趋势认知系统

DAO（道）是一个面向黄金市场的 AI 趋势认知项目。它把中国传统思想中的“观变、审时、度势”转译为可定义、可验证、可校准的软件模型，并用概率预测、金融数据与多 Agent 协作持续修正判断。

它不回答“明天黄金一定涨还是跌”，而回答：

- 当前市场处于什么状态？
- 哪些力量正在主导市场？
- 趋势处于形成、扩张、衰竭还是转换阶段？
- 哪些证据支持或反对当前判断？
- 什么条件出现时，当前判断必须失效？
- 当前更适合观察、等待、试探还是回避？

> 本项目用于研究与决策辅助，不提供确定性价格预测，不构成投资建议，也不直接执行交易。

## 当前阶段

仓库目前处于 `research-to-design` 阶段：研究报告已经形成，正在把其中的概念拆解为领域本体、数据契约、Agent 协议、评估方法和可实施的 MVP。

核心研究报告：

- [《从易经“观变”到 AI 黄金趋势智能系统》](docs/research/system-design.md)

## Harness 如何工作

本项目把上下文、约束、状态和验收标准都保存在仓库中，使 Codex、Claude Code、GitHub Copilot 或人类协作者可以在不同会话中稳定接续工作。

```mermaid
flowchart TD
    A["任务与问题"] --> B["加载最小上下文"]
    B --> C["计划与预测契约"]
    C --> D["实现或研究"]
    D --> E["反方审查"]
    E --> F["质量门验证"]
    F --> G["更新状态与决策"]
    G --> H["人工审阅 / PR"]
```

关键入口：

| 文件 | 用途 |
|---|---|
| [AGENTS.md](AGENTS.md) | 所有 Agent 的唯一主规范 |
| [harness.yaml](harness.yaml) | 工程清单、阶段和验证命令 |
| [上下文地图](docs/harness/CONTEXT_MAP.md) | 按任务类型加载最小上下文 |
| [工作流](docs/harness/WORKFLOW.md) | 从立项到提交的标准循环 |
| [质量门](docs/harness/QUALITY_GATES.md) | 研究、数据、模型和输出的验收标准 |
| [项目状态](state/PROJECT_STATE.md) | 当前进展、下一步与阻塞项 |
| [任务模板](tasks/TEMPLATE.md) | 每项工作的范围与完成定义 |

## 目录结构

```text
.
├── AGENTS.md
├── CLAUDE.md
├── harness.yaml
├── docs/
│   ├── architecture/     # 领域本体与 Agent 协议
│   ├── decisions/        # 不可轻易覆盖的架构决策
│   ├── harness/          # 工作流、上下文与质量门
│   ├── product/          # 产品目标与边界
│   └── research/         # 研究报告与研究记录
├── evals/                # 预测与系统评估规范
├── schemas/              # 机器可验证的数据契约
├── scripts/              # Harness 校验工具
├── state/                # 跨会话项目记忆
├── tasks/                # 一次一个主题的任务记录
└── templates/            # 研究、预测与认知帧模板
```

## 开始一次工作

1. 阅读 `AGENTS.md` 和 `state/PROJECT_STATE.md`。
2. 根据 `docs/harness/CONTEXT_MAP.md` 只加载本任务需要的文档。
3. 从 `tasks/TEMPLATE.md` 建立一个任务文件，先写清目标、非目标和完成定义。
4. 研究或实现后运行：

```bash
make validate
```

5. 更新项目状态、决策日志和任务结果，再提交一个主题明确的 PR。

## 核心约束

- 传统思想提供问题框架与命名，不进入未经验证的概率引擎。
- 每个市场判断都必须带 `as_of`、`data_cutoff`、证据、概率、反方情景和失效条件。
- LLM 组织证据与解释，不虚构行情，不替代数值模型计算概率。
- 训练、回测和评估必须使用当时可获得的数据，防止前视偏差。
- 没有优势或证据冲突过大时，系统必须能够弃权。

## 下一里程碑

第一阶段不追求自动交易，而是交付一个可回放、可评分的每日/事件驱动“市场认知帧”研究原型。具体范围见 [项目愿景](docs/product/vision.md) 与 [项目状态](state/PROJECT_STATE.md)。

