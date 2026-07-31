# 评估框架

本项目评估“是否形成可靠、校准、可解释的趋势认知”，而不是只看一次交易盈亏。

当前 M1 入口：

- [金标准趋势认知标注指南 v0.1](gold-standard-annotation-guide-v0.1.md)
- [评估契约 v0.3](evaluation-contract-v0.3.md)
- [评估契约 v0.2（XAU/USD 原协议）](evaluation-contract-v0.2.md)
- [五类 Q0 协议试标](pilots/README.md)
- [试标发现](pilots/pilot-findings.md)

## 1. 概率质量

- Brier score
- Log loss
- Reliability / calibration curve
- 不同置信区间的样本数与命中率
- 相对朴素基线的 skill score

## 2. 状态识别

- 按时间顺序的样本外混淆矩阵
- 状态持续时间与频繁跳变率
- 变化点检测延迟
- 生命周期标签的人际一致性

## 3. 覆盖与弃权

- 预测覆盖率
- 弃权率及原因分布
- 弃权样本与强行预测样本的误差对比
- 数据陈旧、模型冲突和分布外检测召回率

## 4. 解释质量

- 解释中的数字是否与结构化帧完全一致
- 每项关键结论是否有证据引用
- 是否展示反方证据和失效条件
- 是否存在无来源的新事实
- 用户能否正确复述状态、概率和风险

## 5. 时间回放规范

1. 按 `data_cutoff` 重建当时可见信息。
2. 冻结特征、模型、Prompt 和融合规则版本。
3. 先冻结 Market Cognition Frame，再按是否预测弃权生成 Forecast Contract。
4. 到期后按 `xauusd-direction-5d:0.2.0` 追加独立 Resolution Record。
5. 只追加评分，不改写原预测。
6. 按月或足够样本量后检查校准与漂移。

## 6. 基线

每个复杂模型至少比较：

- 无变化 / 持续当前状态
- 历史无条件频率
- 简单移动平均或趋势规则
- 单一主驱动模型

复杂系统只有在样本外稳定优于基线、且维护成本合理时才保留。
