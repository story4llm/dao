---
id: 2026-07-30-runtime-review-must-fixes
status: completed
owner: codex
created_at: 2026-07-30
updated_at: 2026-07-30
---

# Runtime Review Must-Fixes

## 问题

外部评审发现 certified runtime 有四个健壮性问题：合法配置可能被宽泛占位符检查误杀、Resolution 复现路径混用 float/Decimal、弃权 Forecast 在解析时触发模糊 TypeError，以及 CLI 对畸形上游结构暴露 traceback。

## 范围

- 收窄配置占位符识别，只拒绝明确模板标记。
- Resolution normalized change 与分类统一使用 Decimal 重算。
- resolved Resolution 遇到弃权 Forecast 时输出明确语义错误并跳过评分。
- CLI 将 KeyError、TypeError 转为稳定的用户错误。
- 为四项修复加入回归测试。

## 非目标

- 不处理评审中的建议项 5–8。
- 不改变公共 Schema、评估口径、产品目标或安全边界。
- 不改变 OANDA 私有数据留存策略。

## 必要上下文

- `AGENTS.md`
- `state/PROJECT_STATE.md`
- `tasks/2026-07-30-certified-runtime-hardening-v0.2.md`
- `docs/harness/CONTEXT_MAP.md`
- `docs/harness/WORKFLOW.md`
- `docs/harness/QUALITY_GATES.md`

## 输入与输出契约

- 输入：runtime 评审意见 1–4 与现有 v0.2 实现。
- 输出：最小实现补丁、回归测试、任务与项目状态记录。
- `as_of` / `data_cutoff`：不改变市场数据契约；本任务只修复验证与错误处理。

## 计划

- [x] 核对四个问题的控制流和现有测试。
- [x] 实现最小修复。
- [x] 增加边界、弃权、占位符与 CLI 错误回归测试。
- [x] 运行定向测试与 `make validate`。
- [x] 完成反方检查并更新项目记录。

## 完成定义

- [x] 合法值包含小写 `replace` 不再被占位符门误杀，模板中的明确 `REPLACE` 仍被拒绝。
- [x] ±0.5 边界使用 Decimal 语义分类。
- [x] 弃权 Forecast 的 resolved Resolution 返回明确错误，不进入概率评分。
- [x] CLI 捕获 KeyError、TypeError 且不输出 traceback。
- [x] `make validate` 通过。

## 验证

- 自动：新增四类回归测试；运行完整 Harness 与 unittest。
- 人工：检查错误消息不含凭据、账户 ID 或 traceback。
- 基线或反方检查：确认非弃权 Resolution 的现有评分重算仍然执行并拒绝错误分数。

## 结果

完成评审 must-fix 1–4。占位符门改为递归检查明确的 `REPLACE` / `REPLACE_ME` 标记与 `example.com` 域名；Resolution 的 close、ATR、normalized change 和分类统一使用 Decimal；弃权 Forecast 的 resolved Resolution 返回明确错误并跳过评分；CLI 稳定捕获畸形上游结构的 KeyError、TypeError。新增正负 0.5 边界、弃权解析、合法 replace 文本和 CLI 错误回归测试。

## 决策与风险

- 决策：修复不改变公共契约，因此不新建 ADR。
- 残余风险：评分指标本身仍使用 float，与现有评分契约一致；本任务只统一影响边界分类的 normalized change 复现路径。
- 后续任务：建议项 5–8 如需实施，另建任务。
