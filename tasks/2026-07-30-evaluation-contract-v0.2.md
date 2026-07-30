---
id: 2026-07-30-evaluation-contract-v0.2
status: completed
owner: codex
created_at: 2026-07-30
updated_at: 2026-07-30
---

# 评估契约 v0.2

## 问题

M1 已形成五类 Q0 试标，但 Evidence 与 Market Cognition Frame 仍把关键审计信息放在自由文本中，单一 `abstain` 混淆当前状态与未来预测，且 Cognition Delta、Annotation Record、Resolution Record 尚无机器契约。没有预注册的 3—5 日解析规则，任何概率评分都容易受到后见偏差和选择性解释影响。

## 范围

- 修订 Evidence Item、Forecast Contract 和 Market Cognition Frame schema。
- 新增 Cognition Delta、Annotation Record、Resolution Record schema。
- 分离状态认知、未来概率和信念修正三条评估链。
- 预注册 XAU/USD 第 5 个完整交易日的三分类解析规则，第 3 日只作诊断。
- 将五份 Q0 试标迁移到 v0.2 结构，但不升级认证。
- 将新契约加入 Harness 质量门。

## 非目标

- 不寻找或采购生产数据源。
- 不把五份 Q0 样本解析为历史成绩。
- 不扩展到 20—30 个样本。
- 不实现实时数据、完整 Agent 运行时、前端或交易功能。
- 不宣称 ATR 中性带或任何模型具有预测优势。

## 必要上下文

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `evals/gold-standard-annotation-guide-v0.1.md`
- `evals/pilots/pilot-findings.md`
- `docs/product/trend-cognition-spec-v0.1.md`
- `schemas/`

## 输入与输出契约

- 输入：五份 Q0 证据快照、五份 Q0 MCF、标注指南和三类 v0.1 schema。
- 输出：ADR-0003、评估契约 v0.2、六类 schema、迁移后的 Q0 样本与更新后的自动质量门。
- 时点：任何 Resolution Record 必须在预测窗口到期后追加；本任务不创建真实历史解析结果。

## 计划

- [x] 核对试标暴露的契约缺口。
- [x] 决定状态、预测和观点修正的评估边界。
- [x] 预注册 5 日主评分与 3 日诊断规则。
- [x] 修订并新增 schema。
- [x] 迁移 Q0 样本。
- [x] 扩展质量门并运行验证。
- [x] 更新项目状态和任务结果。

## 完成定义

- [x] Evidence 关键审计字段不再只存在于 notes。
- [x] 状态弃权与预测弃权可以独立表达。
- [x] range 生命周期组合由 schema 与校验器约束。
- [x] Forecast、Delta、Annotation、Resolution 的概率、时点与引用规则可自动检查。
- [x] 五份 Q0 样本仍为 Q0，且事件样本不再携带占位预测概率。
- [x] `make validate` 通过。

## 验证

- 自动：JSON 语法、schema 必需字段、概率和、证据引用、时间顺序、弃权一致性、Q0 认证和解析协议版本。
- 人工：结果空间是否互斥；未来结果是否仍与状态标注分离；阈值是否在看结果前冻结。
- 反方检查：确认单一样本分数不会被描述为预测优势。

## 结果

完成 ADR-0003 与评估契约 v0.2；三类原有 schema 已修订，并新增 Cognition Delta、Annotation Record、Resolution Record。五份 Q0 样本完成结构迁移：

- Evidence 审计字段已结构化。
- 所有 MCF 使用 `research_posture`。
- 状态与预测弃权已拆分。
- `pilot-d09` 的未来概率已从占位数字改为 `null`。
- 所有样本继续认证为 Q0，不产生历史评分。

自动质量门现检查 36 个必要入口、6 个 schema、15 条证据、5 份 MCF、概率和、统一结果映射、时间边界、弃权一致性、研究姿态与 Q0 认证锁。

## 决策与风险

- 决策：采用 ADR-0003 的三链评估；正式评分固定在第 5 个完整交易日，第 3 日只作诊断。
- 风险：ATR(20) 的 0.5 中性带只是预注册协议选择，仍需样本外检验；数据源资格仍阻塞 Q1。
- 后续任务：建立数据源资格矩阵 v0.1，不直接扩展样本或计算 Q0 历史成绩。
