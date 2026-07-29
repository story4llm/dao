# Agent 协作协议

## 设计目标

多 Agent 的价值是职责隔离、证据对抗和可审计性，不是让多个 LLM 重复总结同一批新闻。

## 角色边界

| Agent | 主要输入 | 结构化输出 | 不得做 |
|---|---|---|---|
| Orchestrator | 任务、数据快照、版本清单 | 执行图、截止时点、依赖 | 修改专业结论 |
| Trend Observer | 价格与波动特征 | 方向、生命周期、结构证据 | 解释宏观因果 |
| Macro Analyst | 实际利率、美元、宏观事件 | 驱动力、情景、反证 | 直接计算技术指标 |
| Positioning Analyst | ETF、CFTC、资金流 | 拥挤度、资金变化 | 用滞后数据冒充实时 |
| Event Analyst | 新闻、讲话、日历 | 事件事实、影响假设 | 虚构未确认事件 |
| Analog Matcher | point-in-time 历史状态 | 相似片段和差异 | 把相似当因果 |
| Transition Detector | 多模型状态序列 | 变化点风险、触发器 | 宣布必然反转 |
| Challenger | 所有候选结论 | 反方情景、重复证据、漏洞 | 为反对而捏造证据 |
| Probability Fuser | 去重后的模型输出 | 情景概率、分歧、弃权 | 让 LLM 任意调概率 |
| Risk Gate | 概率、波动、事件与数据质量 | 风险等级、允许动作、阻断 | 被解释层绕过 |
| Explainer | 已批准的认知帧 | 面向用户的条件化解释 | 改写结构化数值 |
| Calibrator | 预测账本与实际结果 | 评分、漂移、调整建议 | 用单次成败评价模型 |

## 输入信封

每次调用至少提供：

```json
{
  "run_id": "run-2026-07-29-xauusd-d1",
  "agent": "trend-observer",
  "instrument": "XAUUSD",
  "horizon": "P3D",
  "as_of": "2026-07-29T12:00:00Z",
  "data_cutoff": "2026-07-29T11:55:00Z",
  "input_refs": ["snapshot:prices:v1"],
  "contract_version": "1.0.0"
}
```

## 输出信封

```json
{
  "run_id": "run-2026-07-29-xauusd-d1",
  "agent": "trend-observer",
  "status": "ok",
  "claims": [],
  "evidence_refs": [],
  "counterevidence_refs": [],
  "confidence": 0.62,
  "data_gaps": [],
  "warnings": [],
  "model_version": "trend-model:0.1.0",
  "generated_at": "2026-07-29T12:00:05Z"
}
```

`status` 为 `ok`、`degraded`、`abstain` 或 `error`。`confidence` 表示本 Agent 对其限定任务的置信度，不等于市场上涨概率。

## 汇合规则

1. 先根据 `evidence_refs` 去重和识别共同数据源。
2. 数值模型结果与文本推断分别保留，不做无依据平均。
3. Challenger 的反方情景必须进入认知帧或被明确驳回并记录理由。
4. Probability Fuser 只能使用已版本化的融合规则。
5. Risk Gate 在解释生成前执行，其阻断结果不可覆盖。
6. Explainer 只能引用最终帧中的字段，不得生成新事实或新概率。

## 失败与降级

- 输入数据过期：`degraded` 或 `abstain`
- 关键来源缺失：列入 `data_gaps`，降低覆盖率
- Agent 输出 schema 不合法：拒绝进入融合
- 概率无法归一或模型严重冲突：弃权
- 事件状态未确认：保留“待核实”，不得当作事实

