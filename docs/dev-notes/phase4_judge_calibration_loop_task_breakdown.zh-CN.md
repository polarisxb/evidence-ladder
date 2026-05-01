# Phase 4 开发任务清单
天鉴 · 衡 Phase 4（Judge Calibration Loop）开发任务拆解  
版本：`v0.1-draft`  
日期：`2026-03-29`

## 1. 文档目的

本文档将 [真实业务接入实施方案](./business_integration_implementation_plan.zh-CN.md) 中的 `Phase 4：Judge Calibration Loop` 拆成可以直接排期、分配、开发和验收的任务清单。

本清单只覆盖 Phase 4：

- `judge calibration samples`
- `judge snapshot normalization`
- `gold label ingestion`
- `production sampling`
- `calibration runs`
- `calibration summary`

本清单不覆盖后续阶段：

- `review_events` 不可变审计链重构
- 完整人工标注工作台
- 新的 judge 模型训练或自动调参
- bridge adapter、浏览器 agent、任意脚本 DSL

## 2. Phase 4 总目标

Phase 4 完成后，系统应满足：

- 平台能把生产 case 和人工确认样本沉淀为可复用的 `judge_calibration_samples`
- 平台能稳定区分：
  - 自动 judge 当时的输出
  - 人工 gold label
  - 当前 summary 指标
- 平台能运行至少一套 calibration run，并输出：
  - `Judge Precision@Gold`
  - `Judge False Positive Rate`
  - `Judge Recall@Gold`
  - `Manual Review Overturn Rate`
  - 按类别、目标类型、业务验证状态分层的误判分布
- calibration run 不会重新访问真实目标或重新执行 probe，而是基于已冻结的 case 证据快照进行评估
- 现有 scan、results、report、review 兼容链路保持可用

## 3. 当前基线与工程约束

在开始 Phase 4 前，需要明确几条硬边界。

### 3.1 Phase 1 到 Phase 3 已完成，Phase 4 必须建立在现有 case layer 之上

当前仓库已经具备：

- `attack_cases`
- `attack_case_variants`
- quartet 默认协议
- `adapter` 接入
- `business_verification_status`
- case/results/report 的兼容读链路

结论：

- Phase 4 不能绕开 `attack_case`
- calibration 的输入必须建立在当前 case 证据与 summary 字段之上
- `attack_results` 兼容层继续保留，不允许为了 calibration 打断 legacy API

### 3.2 Phase 4 的 “judge” 指的是自动判定层，不包含人工 review 和 probe

本期“judge”定义为：把 case 证据映射为最终自动 triage 结论的自动层。

Judge 输出的最小关注对象固定为：

- `verdict_status`
- `reportable`
- `review_required`
- `execution_mode`
- `blackbox_outcome`

其中：

- `probe` 仍属于业务验证层，不属于 judge 本体
- 人工 review 是 gold source，不属于 judge 本体

### 3.3 Calibration run 必须可重放、可比对、不可依赖实时目标

Phase 4 的 calibration run 不允许：

- 重新访问客户业务接口
- 重新执行 adapter invoke
- 重新执行 probe

Phase 4 的 calibration run 必须：

- 使用持久化的 case 证据快照
- 使用持久化的 gold label
- 生成可复核、可追踪的 run summary

### 3.4 本期不做 review event log 重构

总方案中已经提出 `review_events` 不可变事件链，但它不是本期主目标。

结论：

- Phase 4 只消费现有 review 结果作为 gold source 或人工确认来源
- 不在本期把 review API 改造成完整事件溯源模型
- “追加式审计链”作为后续阶段单独推进

### 3.5 继续保持 additive 变更

当前数据库仍通过 `Base.metadata.create_all()` 初始化，没有正式 migration 框架。

结论：

- Phase 4 继续优先采用新增表、新增列、JSON snapshot 的 additive 变更
- 不重写现有 `attack_results` 表结构
- 历史 case 不做一次性回填，按 read-path 或 sample 创建时兼容处理

## 4. 任务分组

本期任务分成 6 组：

1. Judge 数据契约与持久化
2. Gold label 与 sample 采集
3. Calibration run 执行与 summary 计算
4. 后端 API 与指标透出
5. 前端 summary 与运维视图
6. 验证与回归

## 5. 开发顺序建议

建议按下面顺序推进：

1. `P4-T01` 统一 judge snapshot 与 case 判定投影
2. `P4-T02` 新增 calibration tables 与 schema
3. `P4-T03` 定义 gold label 契约与来源规则
4. `P4-T04` 实现 production sampling 与 sample ingest
5. `P4-T05` 实现 calibration run executor
6. `P4-T06` 暴露 calibration APIs 与 summary read model
7. `P4-T07` 透出 report / stats 侧 calibration 指标
8. `P4-T08` 前端类型与 API 封装
9. `P4-T09` Calibration Summary 页面
10. `P4-T10` 全链路验证与阶段审查

原因：

- judge snapshot 不先定，后面的 sample 和 run 会漂
- sample schema 不先定，人工 gold 与生产抽样会出现两套不兼容契约
- summary 指标必须建立在稳定 run 结果之上，不能让前端自己拼

## 6. 任务清单

## 6.1 Judge 数据契约与持久化

### `P4-T01` 统一 case 级 judge snapshot 与判定投影

任务目标：

- 给当前 case 结果增加稳定、可采样的自动 judge 投影
- 避免 calibration 逻辑依赖 scattered legacy 字段反推

影响文件：

- `backend/app/models/attack_case.py`
- `backend/app/schemas/case.py`
- `backend/app/services/case_serializer.py`
- `backend/app/services/report_generator.py`
- `backend/app/api/reports.py`

建议新增字段：

- `AttackCase.judge_snapshot`
- `AttackCase.review_required`
- `AttackCase.reportable`

建议 `judge_snapshot` 结构：

```json
{
  "verdict_status": "manual_review_needed",
  "verdict_reason": "...",
  "execution_mode": "EXECUTING_ATTACK",
  "blackbox_outcome": "PARTIAL_INJECTION_SUCCESS",
  "control_assessment": "attack_delta_supported",
  "attack_goal_score": 0.82,
  "utility_score": 0.41,
  "business_verification_status": "text_claim_only",
  "review_required": true,
  "reportable": false
}
```

关键设计要求：

- `review_required` 固定由自动 judge 语义推导，不依赖人工 review 覆盖
- `reportable` 固定表示“自动 judge 认为这个 case 当前是否应进入正式 finding 集合”
- 现有 results/report 兼容层继续返回 legacy 字段，不被替换

验收标准：

- 新 case 可以稳定落下 `judge_snapshot / review_required / reportable`
- 老 case 在没有新字段时仍可通过 read-path fallback 读出一致结果

### `P4-T02` 新增 calibration tables 与 schema

任务目标：

- 为 gold label、抽样、run 历史建立持久化基础

影响文件：

- 新增：`backend/app/models/judge_calibration_sample.py`
- 新增：`backend/app/models/judge_calibration_run.py`
- `backend/app/models/__init__.py`
- `backend/app/database.py`
- 新增：`backend/app/schemas/judge_calibration.py`
- `backend/app/schemas/__init__.py`

建议新表：

1. `judge_calibration_samples`

- `id`
- `source_type`
- `attack_case_id`
- `judge_input_snapshot`
- `judge_output`
- `gold_label`
- `gold_rationale`
- `labeler`
- `label_version`
- `sampling_reason`
- `is_drift_sample`
- `created_at`
- `updated_at`

2. `judge_calibration_runs`

- `id`
- `name`
- `run_mode`
- `filters_json`
- `sample_count`
- `summary_json`
- `status`
- `started_at`
- `completed_at`
- `created_at`

关键设计要求：

- `judge_calibration_runs` 虽未在总方案正文单独列出，但为了支持 `run_id` 查询和 run 历史，Phase 4 MVP 需要它
- `judge_input_snapshot` 必须足够支撑离线重放，不得要求重新访问目标系统
- `gold_label` 与 `judge_output` 必须是结构化 JSON，不用自由文本拼接

验收标准：

- 数据库可创建 `judge_calibration_samples` 与 `judge_calibration_runs`
- schema 可稳定表达 sample 与 run 的 CRUD / 查询输出

## 6.2 Gold label 与 sample 采集

### `P4-T03` 定义 gold label 契约与来源规则

任务目标：

- 统一 gold label 的形状与含义，避免不同标注来源不可比较

影响文件：

- `backend/app/schemas/judge_calibration.py`
- 如有必要：`backend/app/services/case_serializer.py`

建议 `gold_label` 最小结构：

```json
{
  "reportable": true,
  "verdict_status": "manual_verified",
  "execution_mode": "EXECUTING_ATTACK",
  "blackbox_outcome": "FULL_INJECTION_SUCCESS"
}
```

建议 `source_type` 固定枚举：

- `curated_gold_seed`
- `manual_review_promoted`
- `production_random`
- `production_targeted`

关键设计要求：

- gold label 必须明确区分“人工确认的最终结论”和“自动 judge 输出”
- Phase 4 MVP 不要求完整标注工作台，但后端契约必须允许人工输入 gold label
- `label_version` 必须显式存在，避免标注规范变更后不可比较

验收标准：

- 任意 calibration sample 都能被明确标记来源、label 版本和 gold 责任人

### `P4-T04` 实现 production sampling 与 sample ingest

任务目标：

- 从生产 case 中自动抽样沉淀 calibration samples
- 支持把已 review 的 case 提升为 gold sample

影响文件：

- 新增：`backend/app/services/judge_sampling.py`
- 新增：`backend/app/api/judge_calibration.py`
- `backend/app/api/__init__.py`

建议生产抽样规则：

- 随机分层抽样：
  - 按 `category`
  - 按 `target_type`
  - 按 `business_verification_status`
- 定向抽样：
  - `verdict_status in {manual_review_needed, ai_suspected}`
  - `business_verification_status in {text_claim_only, probe_failed}`
  - 高风险但低置信
  - `control_assessment = controls_inconclusive`

建议最小 ingest API：

- `POST /api/v1/judge/calibration/samples`
- `GET /api/v1/judge/calibration/samples`
- `PATCH /api/v1/judge/calibration/samples/{sample_id}`

关键设计要求：

- sample 创建时应冻结：
  - `judge_input_snapshot`
  - `judge_output`
  - 当时的 case 核心 summary
- 同一个 `attack_case_id + label_version + source_type` 应避免无界重复
- 从 review 提升为 gold sample 时，gold label 应来自人工 review 结果，而不是重新推断

验收标准：

- 能从 case 手动创建 sample
- 能按规则批量抽取 production sample
- 能给 sample 录入或更新 gold label

## 6.3 Calibration run 执行与 summary

### `P4-T05` 实现 calibration run executor

任务目标：

- 基于冻结 sample 执行 calibration run
- 输出稳定 summary，而不是只返回原始样本列表

影响文件：

- 新增：`backend/app/services/judge_calibration_runner.py`
- 新增：`backend/app/services/judge_metrics.py`

建议 `run_mode`：

- `snapshot_eval`

本期固定行为：

- 只评估 sample 中冻结的 `judge_output` 相对 `gold_label` 的表现
- 不重新访问真实目标
- 不重新执行 probe
- 不重新跑 adapter invoke

建议 summary 输出：

- `sample_count`
- `judge_precision_at_gold`
- `judge_recall_at_gold`
- `judge_false_positive_rate`
- `manual_review_overturn_rate`
- `by_category`
- `by_target_type`
- `by_business_verification_status`
- `misclassified_samples`

关键设计要求：

- `misclassified_samples` 需要可 drill-down 到 sample id 和 case id
- summary 必须区分：
  - judge 误报
  - judge 漏报
  - review 推翻
- 本期不做“在线 rejudge 当前模型版本”模式，避免把 scope 拉到模型重跑与成本控制

验收标准：

- 能对至少一套 gold-labeled dataset 运行 calibration
- run 结果可持久化并可通过 `run_id` 查询

### `P4-T06` 暴露 calibration APIs 与 summary read model

任务目标：

- 提供可消费的 calibration run 和 summary API

影响文件：

- `backend/app/api/judge_calibration.py`
- `backend/app/schemas/judge_calibration.py`

建议 API：

- `POST /api/v1/judge/calibration/runs`
- `GET /api/v1/judge/calibration/runs/{run_id}`
- `GET /api/v1/judge/calibration/summary`

建议 `summary` 支持参数：

- `label_version`
- `source_type`
- `category`
- `target_type`
- `business_verification_status`
- `date_from`
- `date_to`

关键设计要求：

- `summary` 是聚合视图，不替代 run 明细
- run 查询必须返回：
  - run metadata
  - filters
  - summary
  - 少量 misclassified preview
- API 不返回大段冗余 case/raw evidence，细节 drill-down 通过 `sample_id` 或 `case_id`

验收标准：

- 能触发 calibration run
- 能查询 run 结果
- 能拿到全局 summary 和分层 breakdown

## 6.4 后端指标与兼容透出

### `P4-T07` 透出 calibration 指标到 stats/report 兼容层

任务目标：

- 让系统在不重构报告首页的前提下，能开始展示 judge 质量指标

影响文件：

- `backend/app/services/report_generator.py`
- `backend/app/api/stats.py`
- 如有必要：`backend/app/schemas/scan.py`

建议新增指标：

- `judge_precision_at_gold`
- `judge_false_positive_rate`
- `manual_review_overturn_rate`
- `latest_calibration_sample_count`

关键设计要求：

- report 不直接内联 calibration run 全量明细
- 首页或 summary 只暴露最新可用指标摘要
- 若当前环境还没有 calibration data，应明确返回 `null` 或 `not available`

验收标准：

- stats/report 侧可读取 calibration 摘要
- 老扫描、老报告不会因缺少 calibration 数据报错

## 6.5 前端 summary 与运维视图

### `P4-T08` 新增前端 calibration 类型与 API 封装

任务目标：

- 给前端页面和运维视图提供稳定类型层

影响文件：

- `frontend/src/types/index.ts`
- 新增：`frontend/src/api/judgeCalibration.ts`

建议新增类型：

- `JudgeCalibrationSample`
- `JudgeCalibrationRun`
- `JudgeCalibrationSummary`
- `JudgeGoldLabel`
- `JudgeMisclassificationPreview`

建议新增 API wrapper：

- `createCalibrationRun`
- `getCalibrationRun`
- `getCalibrationSummary`
- `listCalibrationSamples`
- `createCalibrationSample`
- `updateCalibrationSample`

验收标准：

- 前端无需手写 `any` 处理 calibration 数据
- `npm run build` 零类型错误

### `P4-T09` 新增 Calibration Summary 页面

任务目标：

- 提供最小可用的 judge calibration 运营视图

影响文件：

- 新增：`frontend/src/pages/JudgeCalibration.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/layout/Sidebar.tsx`

页面最小能力：

- 查看 latest summary
- 手动触发 calibration run
- 查看按类别 / 目标类型 / 业务验证状态的 breakdown
- 查看误判样本 preview，并跳转到 case 或 report

关键设计要求：

- 本期只做 summary 与 preview，不做完整标注工作台
- 页面需明确区分：
  - 当前自动 judge 指标
  - 业务验证指标
  - 人工 review 推翻率

验收标准：

- 用户能在 UI 中看到最新 calibration 概况
- 用户能触发 run 并查看 run summary

## 6.6 验证与阶段审查

### `P4-T10` 全链路验证与阶段审查

任务目标：

- 为 Phase 4 建立最小但可信的回归验证集
- 对 `P4-T01 ~ P4-T09` 做 findings-first 阶段审查

后端验证：

- calibration tables 可创建
- sample ingest 可用
- run 可执行并持久化
- summary API 可返回全局指标与 breakdown
- report/stats 兼容读取不报错

建议测试覆盖：

- gold label schema 校验
- sample dedupe / source_type 校验
- production sampling 规则命中
- calibration run summary 计算
- misclassification preview 输出
- 历史无 calibration 数据时的 read-path fallback

前端验证：

- `npm run build` 通过
- Calibration Summary 页面可加载 summary
- run 触发与 run detail 展示可用

阶段审查固定关注：

- judge snapshot 是否真的稳定，不依赖散落 legacy 字段反推
- gold label 与 judge output 是否语义清晰，不混淆
- summary 指标是否可解释，尤其是 precision / false positive / overturn
- calibration 是否没有破坏 results/report/review 现有链路

## 7. 里程碑建议

### `M1` 数据契约与 sample 采集

完成项：

- `P4-T01`
- `P4-T02`
- `P4-T03`
- `P4-T04`

验收：

- 可创建 calibration sample
- 可录入 gold label
- 可从生产 case 抽样

### `M2` calibration run 与 summary API

完成项：

- `P4-T05`
- `P4-T06`
- `P4-T07`

验收：

- 可触发 run
- 可读取 summary
- report/stats 可拿到 calibration 摘要

### `M3` 前端 summary 与阶段审查

完成项：

- `P4-T08`
- `P4-T09`
- `P4-T10`

验收：

- UI 可查看 calibration summary
- UI 可查看误判 preview
- Phase 4 回归与阶段审查通过

## 8. 明确不做

Phase 4 明确不做：

- `review_events` 事件链重构
- 完整人工标注工作台
- 在线重跑真实目标或 probe 的 calibration 模式
- judge 自动调参、模型自动切换、prompt 自动搜索
- 把 calibration 结果直接回写覆盖现有 report finding

## 9. 完成定义

Phase 4 完成时，应满足：

- 平台存在稳定的 `judge_calibration_samples`
- 平台存在可查询的 calibration run 与 summary
- 用户能看到 judge 的基础质量指标，而不只是单个 finding
- summary 至少能回答三个问题：
  1. 自动 judge 对 gold label 的误报率有多高
  2. 哪些类别 / 目标类型 / 业务验证状态最容易误判
  3. 当前人工 review 最常推翻哪类自动结论

如果系统还不能回答这三个问题，就不应宣称 judge calibration loop 已经落地。
