# 质量门

## Gate 1：问题契约

- 问题有明确标的、时间尺度和决策用途。
- 结果空间可解析，情景互斥且尽量完备。
- 已定义基线、验证区间和成功标准。

## Gate 2：证据可追溯

- 关键事实有来源、发布时间和观测时点。
- 观察、推断、假设和决策被明确区分。
- 传统材料只支持认知框架，不支持未经验证的数值结论。

## Gate 3：Point-in-time 数据

- `event_time`、`available_at`、`ingested_at` 不混用。
- 回放只使用当时已经可获得的数据版本。
- 修订数据和最终值不得穿越进入历史预测。
- 每次运行记录 source policy 版本、去密钥请求清单、原始响应哈希和私有位置引用。
- 冻结 Feature Snapshot 与 Baseline Snapshot，记录 C0、ATR(20)、price field、bar 边界、session sequence、历史窗口和代码版本。
- GC run 额外冻结 Kaggle `dataset_ref`、原始 ZIP SHA-256、数据集 `Close` 字段与观测日期序列；数据过旧或列异常时 blocked，Close 不得表述为官方 settlement。
- 公开网页或截图只能进入 exploratory/Q0，除非其时点、bar 语义和许可另有证明。

## Gate 4：模型与概率

- 与朴素基线比较，使用时间顺序的样本外验证。
- 记录 Brier score、log loss、校准曲线和覆盖率。
- 多 Agent 共享同一证据时去重，不能把重复叙述当独立证据。
- 非预测弃权时情景概率总和为 1；状态弃权与预测弃权必须显式分开。
- 没有冻结基线或校准记录时不得填写占位概率。

## Gate 5：风险与失效

- 每个判断有可观察的失效条件。
- 风险等级与研究姿态匹配，不使用交易动作语义。
- 数据陈旧、极端波动或模型冲突时降级或弃权；状态与预测分别守门。
- 不输出确定收益、无风险或必然涨跌等措辞。

## Gate 6：解释

- 解释忠实于结构化结果，不擅自改概率。
- 同时展示支持证据、反方证据、数据缺口和观点变化原因。
- 对用户清楚说明研究辅助边界。

## Gate 7：工程与交付

- schema、示例、实现和文档保持同步。
- 每个 JSON 实例通过标准 JSON Schema Draft 2020-12 与 date-time format 检查。
- certified bundle 在持有原始文件的私有环境通过引用、时间、概率、哈希、冻结量和 Resolution 重算检查。
- XAU/USD 与 GC 使用独立 protocol、价格字段和交易日历；任何跨轨 Feature/Baseline/Forecast/Resolution 引用失败。
- 状态标注、未来概率和信念修正使用物理分离的评估记录。
- 测试、验证脚本和人工检查通过。
- 任务状态、项目状态和决策记录已更新。
- 仓库中没有密钥、付费数据或大体积原始数据。
- 仓库中没有许可受限的完整行情响应；`runtime/private/` 与 `runs/**/raw/` 被忽略。
- `certified` 与 `exploratory` 由数据门决定，不能由 Agent 自行宣称。
- GitHub Actions 自动执行 Harness 与反例测试；CI 不接触许可受限原始行情。
