# 任务：GC 轨迁移到 Kaggle 数据集单一实现

- 日期：2026-07-31
- 状态：完成
- 关联决策：ADR-0009（取代 ADR-0006 的 CME 管线）

## 目标

删除基于 CME/DataMine/授权供应商 JSON 的旧 GC 数据管线，将 `prepare-gc` 原地重写为 Kaggle 数据集（`youneseloiarm/comex-gold-futures-dataset-gc-contract`）+ 官方 kaggle CLI 的唯一实现；GC 语义改为 daily-only、Close 主参考价、`dataset_observation_date`、exploratory/Q0。OANDA XAU/USD 轨保持不变。

## 非目标

- 不新增 `prepare-kaggle-gc` 等第二命令，不做 provider 分支或 CME fallback。
- 不改变 XAU/USD 的价格语义与认证流程。
- 不宣称 Kaggle 数据具有 CME 官方认证或 certified 资格。

## 交付

- 新增 `dao_runtime/kaggle_gc.py`（CLI 检查、下载、安全解压、CSV 自动识别与校验、bundle 生成）；删除 `dao_runtime/futures.py`。
- 新协议 `gc-kaggle-daily-direction-5d:0.1.0`；schema、bundle 校验、forecast 生成同步更新；GC 帧禁止 Q1。
- 新模板 `templates/private-gc-bundle-config.example.json`（Kaggle 结构）；删除四个 gc-*source 模板。
- `pyproject.toml` 可选依赖 `.[kaggle]`；`.gitignore` 增加 runs CSV/ZIP 防护。
- `tests/test_kaggle_gc.py` 23+ 项测试（mock subprocess 与本地 ZIP/CSV fixture，不访问网络）；全套 46 项测试通过。
- README、DAILY_RUNBOOK、数据资格矩阵 v0.2、评估契约 v0.3、Prompt v0.3、QUALITY_GATES、OPEN_QUESTIONS、PROJECT_STATE、AGENTS.md 同步更新；ADR-0006 标记 Superseded。

## 验证

- `make validate`（harness 校验 + 46 项 unittest）通过。
- `git grep` 确认 `cme-licensed-snapshot`、`gc-single-contract-direction-5d`、`prepare-kaggle-gc` 不再出现在活动代码与主流程文档（仅 Superseded ADR-0006 与本记录保留历史提及）。

## 残余风险

- Kaggle 数据集为 TradingView 派生，列结构与更新频率不受本仓库控制；首次真实下载运行尚未执行。
- 数据集序列的合约拼接方式未知，ATR 与基线可能受换月跳空影响；已通过 exploratory/Q0 资格与文档明示。
