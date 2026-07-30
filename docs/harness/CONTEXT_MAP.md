# 上下文地图

目标是让 Agent 读取“足够完成任务的最小上下文”，避免把整个仓库塞入一个会话。

## 所有任务

必读：

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- 当前任务文件

## 按任务路由

| 任务类型 | 追加读取 | 通常需要更新 |
|---|---|---|
| 产品范围、用户输出 | `docs/product/vision.md`、`docs/product/prd-v0.1.md`、研究报告第四/五阶段 | 产品文档、项目状态、必要的 ADR |
| 趋势认知能力与评测 | `docs/product/trend-cognition-spec-v0.1.md`、`schemas/`、`evals/README.md`、`evals/evaluation-contract-v0.2.md` | 认知规格、评估样本、错误分类、必要的契约 |
| 东方思想映射 | 研究报告第一阶段、`docs/architecture/domain-ontology.md`、研究政策 | 研究记录、本体、决策日志 |
| 概率或状态模型 | 研究报告第二/四阶段、`schemas/`、`evals/README.md`、评估契约 | 契约、评估、模型文档 |
| Agent 设计 | `docs/architecture/agent-protocol.md`、认知帧 schema、质量门 | Agent 协议、契约、ADR |
| 数据接入 | 研究报告数据架构、证据 schema、质量门 | 数据字典、来源许可、时滞说明 |
| 用户解释与报告 | 市场认知帧、产品愿景、质量门 | 模板、解释规则、评估样本 |
| Harness 本身 | `docs/harness/*`、`harness.yaml` | 主规范、状态、验证脚本 |
| 每日趋势认知 | `prompts/daily-cognition-run-v0.2.md`、数据源资格矩阵、评估契约、八类输出 schema、上一帧 | run manifest、Evidence Manifest、Feature、Baseline、Evidence、MCF、Forecast、Delta、解释 |

## 深入研究的加载原则

1. 先读目录和摘要，再定位相关章节。
2. 需要外部资料时，优先一手与官方来源。
3. 记录“来源说了什么”和“项目推断了什么”，不要混写。
4. 某项事实会随时间变化时，必须重新核验，不依赖旧会话记忆。

## 冲突优先级

1. 用户在当前任务中的明确要求
2. `AGENTS.md` 的安全、证据和工程约束
3. 已接受的 ADR
4. 公共 schema 与接口契约
5. 产品、架构与研究文档
6. 任务计划和临时笔记

发现冲突时停止扩散修改，记录冲突并请求或形成明确决策。
