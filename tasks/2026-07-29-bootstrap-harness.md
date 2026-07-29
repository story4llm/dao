---
id: 2026-07-29-bootstrap-harness
status: in_progress
owner: codex
created_at: 2026-07-29
updated_at: 2026-07-29
---

# 初始化 DAO Harness 工程

## 问题

已有完整研究报告，但缺少可让不同 AI 工具和后续会话稳定接续的工程结构、状态记忆、契约和质量门。

## 范围

- 将研究报告纳入 `docs/research/`。
- 建立统一的 `AGENTS.md` 与轻量工具入口。
- 建立产品、架构、Harness、状态、任务、评估和模板目录。
- 定义 Evidence Item、Forecast Contract 与 Market Cognition Frame schema。
- 提供无第三方依赖的仓库校验脚本。
- 发布到 `story2u/dao` 的独立分支并创建 Draft PR。

## 非目标

- 不实现实时数据接入。
- 不选择最终业务技术栈。
- 不训练状态识别或概率模型。
- 不实现前端、自动交易或经纪商连接。

## 必要上下文

- `upload/系统设计.md`
- 用户提供的 Harness 工作流参考
- `AGENTS.md`

## 输入与输出契约

- 输入：研究报告、Harness 工作流原则、空 GitHub 仓库。
- 输出：可校验、可扩展、可跨工具使用的仓库骨架。
- `as_of` / `data_cutoff`：本任务不生成市场判断，不适用。

## 计划

- [x] 定义目录与主规范。
- [x] 纳入研究报告。
- [x] 建立领域本体与 Agent 协议。
- [x] 建立 schema、模板和质量门。
- [x] 建立状态与任务记忆。
- [x] 运行 Harness 校验。
- [ ] 推送分支并创建 Draft PR。

## 完成定义

- [x] 所有规定入口与契约存在。
- [x] 内部 Markdown 链接与 JSON schema 基础结构通过校验。
- [x] 明确不自动交易、point-in-time、证据分层与弃权约束。
- [ ] GitHub Draft PR 可供人工审阅。

## 验证

- 自动：`make validate`
- 人工：检查规范是否保持“趋势认知而非价格喊单”的产品边界。
- 基线或反方检查：确认没有为了完整感提前生成未经选择的业务技术栈。

## 结果

本地 Harness 校验已通过，待完成 GitHub 发布。

## 决策与风险

- 决策：先建设 Harness，再通过后续 ADR 选择 MVP 技术栈。
- 残余风险：三个 schema 目前只做结构约束；概率和、时间先后关系仍需业务校验器。
- 后续任务：PRD v0.1、数据源可用性矩阵、人工金标准认知帧。

