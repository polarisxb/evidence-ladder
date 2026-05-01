# Phase 3 开发任务清单

天鉴 · 衡 Phase 3（Probe Verification）开发任务拆解  
版本：`v0.1-draft`  
日期：`2026-03-28`

## 1. 文档目的

本文档将 [真实业务接入实施方案](./business_integration_implementation_plan.zh-CN.md) 中的 `Phase 3：Probe Verification` 拆成可以直接排期、分配、开发和验收的任务清单。

本清单只覆盖 Phase 3：

- `business verification status`
- `probe execution`
- `single-step / multi-step probe`
- `results/report/progress` 中的业务验证可见性

本清单不覆盖后续阶段：

- `judge calibration`
- `review event log`
- `bridge adapter`
- judge 抽样漂移分析

## 2. Phase 3 总目标

Phase 3 完成后，系统应满足：

- 平台可以对扫描结果执行 `probe` 验证，而不是只看目标文本回复
- `attack_case` 上存在稳定的 `business_verification_status`
- 系统能严格区分：
  - `not_applicable`
  - `text_claim_only`
  - `probe_verified`
  - `probe_failed`
- probe 结果可以在 case 查询、legacy results、report 中读取
- 前端可按业务验证状态筛选并查看 probe 证据摘要

## 3. 当前基线与工程约束

在开始 Phase 3 前，需要明确几条边界。

### 3.1 Phase 2 已完成，Probe 必须建立在 Adapter 之上

当前仓库已经具备：

- `adapter` 资源
- `adapter_id + runtime_vars`
- direct HTTP adapter 执行器
- `custom` 到最小 adapter 的兼容路径
- Phase 1 的 quartet case layer

结论：

- Phase 3 不应重新设计 target 接入层
- probe 配置应建立在现有 adapter 资源之上
- probe 执行结果仍然要回到现有 `attack_case + attack_results` 兼容结构

### 3.2 Probe 是“验证层”，不是第二套攻击执行层

Probe 的目的不是再次“攻击目标”，而是验证业务副作用是否真的发生。

结论：

- probe 应与攻击执行分层
- probe 只验证外部状态，不重新做 prompt attack
- probe 结果优先级高于纯文本声称

### 3.3 没有 probe 时不能宣称“已验证”

实施方案中明确要求：

- 没有 probe 时，任何文本型业务动作声称都只能记为 `text_claim_only`
- 只有 probe 成功，才能记为 `probe_verified`
- probe 明确失败，必须记为 `probe_failed`

结论：

- 不能把目标回复中的“我已经创建工单/发送邮件”直接升级成业务验证成功
- `business_verification_status` 的推导必须收敛到固定规则，不允许前端自由猜测

### 3.4 继续保持 additive 变更

当前数据库仍通过 `Base.metadata.create_all()` 初始化，没有正式 migration 框架。

结论：

- Phase 3 继续优先采用新列或新 JSON 字段的 additive 变更
- 不做破坏现有 `attack_results` / report / review 的表重写

## 4. 任务分组

本期任务分成 6 组：

1. 数据模型与 adapter 契约
2. probe 执行与断言引擎
3. 扫描集成与状态落库
4. 查询与报告兼容层
5. 前端页面接入
6. 验证与回归

## 5. 开发顺序建议

建议按下面顺序推进：

1. `P3-T01` 扩展 adapter 与 case 数据模型
2. `P3-T02` probe schema 与断言契约
3. `P3-T03` probe 执行器与断言引擎
4. `P3-T04` `adapters/probe/test` 真执行接入
5. `P3-T05` `scan_runner` 接入 probe 与状态推导
6. `P3-T06` case / results / report 兼容字段扩展
7. `P3-T07` 前端类型与 API 封装
8. `P3-T08` `ScanProgress` probe 状态展示
9. `P3-T09` `ScanResults` 与 `Report` 业务验证视图
10. `P3-T10` 全链路验证

原因：

- probe 契约必须先稳定，执行器和扫描集成才能落地
- 状态落库必须先完成，前端筛选和报告展示才有可靠数据源
- `adapters/probe/test` 应先独立跑通，再接进扫描主链路

## 6. 任务清单

## 6.1 数据模型与 Adapter 契约

### `P3-T01` 扩展 `Adapter` 与 `AttackCase` 持久化字段

任务目标：

- 在 adapter 资源上新增 `probe_config`
- 在 `attack_cases` 上新增业务验证状态字段

影响文件：

- `backend/app/models/adapter.py`
- `backend/app/models/attack_case.py`
- 如有必要：
  - `backend/app/models/__init__.py`
  - `backend/app/database.py`

建议新增字段：

- `Adapter.probe_config`
- `AttackCase.business_verification_status`
- `AttackCase.probe_evidence_json`
- `AttackCase.probe_summary`

关键设计要求：

- `business_verification_status` 固定为：
  - `not_applicable`
  - `text_claim_only`
  - `probe_verified`
  - `probe_failed`
- `probe_evidence_json` 只保存结构化证据，不保存大段冗余原始响应
- 对旧库仍然保持 additive 兼容

验收标准：

- 新字段可自动建出或补齐
- 不破坏现有 `attack_case` / `attack_results` 读取链路

### `P3-T02` 新增 probe schema 与断言契约

任务目标：

- 为 adapter probe 和扫描执行准备稳定 schema
- 明确 MVP 支持的 probe step / assertion 范围

影响文件：

- `backend/app/schemas/adapter.py`
- `backend/app/schemas/case.py`
- 如有必要：
  - `backend/app/schemas/scan.py`
  - `backend/app/schemas/__init__.py`

建议产出：

- `AdapterProbeConfig`
- `ProbeStepConfig`
- `ProbeAssertion`
- `ProbeTestRequest`
- `ProbeTestResponse`

本期建议支持的 assertion：

- `json_path_exists`
- `json_path_equals`
- `json_path_contains`
- `status_code_is`
- `text_contains`

关键设计要求：

- 至少支持一种单步 probe 和一种多步 probe
- 继续复用固定模板变量：
  - `{{runtime.*}}`
  - `{{session.id}}`
  - `{{scan.id}}`
  - `{{case.id}}`
  - `{{variant.type}}`
- 多步 probe 额外允许引用前序 step 的显式导出结果，但命名空间必须固定为：
  - `{{probe.steps.<step_name>.status_code}}`
  - `{{probe.steps.<step_name>.text}}`
  - `{{probe.steps.<step_name>.captures.<capture_name>}}`
- 前序 step 若希望被后续 step 引用，必须显式声明 `captures`；后续 step 不允许直接读取任意原始 JSON path 或执行任意表达式
- 不引入脚本 DSL，不支持任意表达式

验收标准：

- schema 可表达单步 / 多步 probe
- schema 层能拒绝未知 assertion 类型和非法模板变量

## 6.2 Probe 执行与断言引擎

### `P3-T03` 新增 probe 执行器与 assertion evaluator

任务目标：

- 实现 probe step 执行
- 实现 assertion 求值与证据归并

影响文件：

- 新增：
  - `backend/app/services/probe_executor.py`
  - `backend/app/services/probe_assertions.py`
- 如有必要：
  - `backend/app/services/adapter_renderer.py`
  - `backend/app/services/adapter_extractors.py`

关键设计要求：

- probe step 复用现有 direct HTTP adapter 请求构造能力
- 多步 probe 支持顺序执行，并允许后续 step 读取前序 step 的响应摘要
- 前序 step 传递给后续 step 的数据只允许来自显式 `captures`，避免多步 probe 演化成开放式脚本编排
- assertion evaluator 输出统一结构：
  - `verified`
  - `assertion_results`
  - `evidence`
  - `failure_reason`

验收标准：

- 给定 probe 配置与上下文，能独立执行单步和多步 probe
- assertion 结果可生成结构化 evidence

### `P3-T04` 让 `POST /api/v1/adapters/probe/test` 执行真实 probe

任务目标：

- 把 Phase 2 的 probe test 接口从“接口壳”升级为真实执行

影响文件：

- `backend/app/api/adapters.py`
- `backend/app/services/probe_executor.py`

关键设计要求：

- `adapters/probe/test` 能验证：
  - probe step 是否可达
  - assertion 是否通过
  - evidence 是否可读
- 仍然不把 probe 混进普通 `adapters/test`

验收标准：

- 用户可在不创建扫描的前提下独立调试 probe
- 单步与多步 probe 至少各有一个可通过样例

## 6.3 扫描集成与状态落库

### `P3-T05` `scan_runner` 接入 probe 与业务验证状态推导

任务目标：

- 在 quartet / verdict 之后执行 probe
- 为每个 case 落下稳定的 `business_verification_status`
- 为进度页提供 probe 运行中的中间态来源

影响文件：

- `backend/app/services/scan_runner.py`
- 如有必要：
  - `backend/app/services/case_serializer.py`

建议流程：

1. 先完成 quartet variants 与 case verdict
2. 再判断该 case 是否适合做业务验证
3. 若无 probe 配置：
   - 有文本型业务动作声称则记 `text_claim_only`
   - 否则记 `not_applicable`
4. 若有 probe 配置：
    - assertion 全通过则记 `probe_verified`
    - assertion 明确失败则记 `probe_failed`
    - 若 probe 已启动但发生执行异常，也记 `probe_failed`

关键设计要求：

- probe 不得破坏 Phase 1/2 的 case 双写事务边界
- probe 失败不能吞掉已有 quartet 证据
- `attack_results.analysis_raw` 继续保留 legacy 字段，同时新增 `business_verification_status` 与 `probe_summary`
- 需要新增一个仅用于运行时/进度展示的可选中间态 `probe_runtime_state`，推荐取值：
  - `pending`
  - `verified`
  - `failed`
  - `skipped`
- `probe_runtime_state` 只用于进度事件和 UI，不替代最终落库字段 `business_verification_status`
- `probe_failed` 的归类规则必须固定：
  - assertion 返回 false
  - probe step HTTP/网络超时
  - 401/403 等鉴权失败
  - 模板渲染失败
  - response extract 失败
  - 其它已知执行异常
- `not_applicable` 只用于“该 case 不适合业务验证”或“无业务动作声称且无 probe”的情况
- `text_claim_only` 只用于“出现文本型业务动作声称，但没有执行 probe”的情况
- `probe_summary` 需要带上结构化失败类型，建议至少覆盖：
  - `assertion_failed`
  - `timeout`
  - `auth_error`
  - `transport_error`
  - `render_error`
  - `extract_error`

验收标准：

- adapter 扫描可落出完整 `business_verification_status`
- 无 probe 的 case 不会被错误标为 `probe_verified`

## 6.4 查询与报告兼容层

### `P3-T06` 扩展 case API、legacy results 与 report finding 字段

任务目标：

- 让 probe 状态和证据摘要能从只读链路读取

影响文件：

- `backend/app/api/cases.py`
- `backend/app/api/reports.py`
- `backend/app/services/case_serializer.py`
- `backend/app/services/report_generator.py`
- `backend/app/schemas/case.py`
- `backend/app/schemas/scan.py`
- `backend/app/schemas/report.py`

建议新增字段：

- `business_verification_status`
- `probe_summary`
- `probe_evidence_preview`

关键设计要求：

- `AttackResultResponse` 与 report finding 只做 additive 扩展
- 不在列表接口内联完整 probe 原始证据
- 结果页和报告页需要细节时，再走 detail / summary 读取

验收标准：

- `/api/v1/scans/{scan_id}/cases` 可读到业务验证状态
- `/api/v1/reports/{scan_id}/results` 与 report finding 可读到兼容字段

## 6.5 前端接入

### `P3-T07` 前端 probe 类型与 API 封装

任务目标：

- 给 probe 展示和筛选提供稳定类型层

影响文件：

- `frontend/src/types/index.ts`
- `frontend/src/api/adapters.ts`
- `frontend/src/api/cases.ts`
- `frontend/src/api/reports.ts`

建议新增类型：

- `BusinessVerificationStatus`
- `ProbeEvidence`
- `ProbeAssertionResult`
- `ProbeTestResult`

验收标准：

- TypeScript 类型可表达 probe 状态与证据
- `npm run build` 不因类型冲突失败

### `P3-T08` `ScanProgress` 展示 probe 进度与状态

任务目标：

- 让进度页能体现 probe 已开始、已验证、已失败

影响文件：

- `frontend/src/pages/ScanProgress.tsx`
- 如有必要：
  - `frontend/src/hooks/useWebSocket.ts`

关键设计要求：

- 继续以 case 粒度展示进度
- 不必把每个 probe step 都做成复杂时间轴
- 至少能看见：
  - `probe pending`
  - `probe verified`
  - `probe failed`
- `probe pending` 必须来自后端运行时状态或进度事件，不能由前端通过“最终状态尚未写入”自行猜测

验收标准：

- adapter + probe 扫描时，进度页不会再把业务验证完全隐藏

### `P3-T09` `ScanResults` 与 `Report` 增加业务验证筛选与证据摘要

任务目标：

- 让用户能按业务验证状态筛 case
- 让 report 能显示“文本声称”和“已验证业务副作用”的区别

影响文件：

- `frontend/src/pages/ScanResults.tsx`
- `frontend/src/pages/Report.tsx`

建议改造：

- `ScanResults` 增加筛选：
  - `text_claim_only`
  - `probe_verified`
  - `probe_failed`
- `Report` finding 卡片增加：
  - `business_verification_status`
  - probe evidence 摘要

关键设计要求：

- 不能把 `probe_verified` 和 `attack_successful` 混成一个概念
- 报告页必须能明确区分：
  - quartet 支持的攻击成功
  - 已验证的业务副作用

验收标准：

- results 页面可按业务验证状态筛选
- report 页面可直观看出哪些 finding 只是文本声称

## 6.6 验证与回归

### `P3-T10` Probe Verification 全链路验证

任务目标：

- 确认 probe 执行、状态落库、只读链路和前端展示都工作

后端验证项：

- 单步 probe 成功样例
- 单步 probe 失败样例
- 多步 probe 成功样例
- 无 probe 时 `text_claim_only / not_applicable` 规则正确
- `POST /api/v1/adapters/probe/test` 正常
- `target_type=adapter` 扫描可落下 `business_verification_status`

前端验证项：

- `npm run build` 通过
- `ScanProgress` 能显示 probe 状态
- `ScanResults` 能按业务验证状态筛选
- `Report` 能展示 business verification 字段

回归要求：

- Phase 1/2 现有最小回归继续通过
- legacy `attack_results` / report / review 不被破坏

## 7. 推荐里程碑

### 里程碑 M1：Probe 契约与测试接口可用

完成条件：

- `probe_config` 与 assertion schema 稳定
- `adapters/probe/test` 能执行单步 / 多步 probe

### 里程碑 M2：扫描链路落下业务验证状态

完成条件：

- `scan_runner` 能推导并持久化 `business_verification_status`
- case / results / report 读链路能取到 probe 摘要

### 里程碑 M3：前端可筛选、可查看 probe 证据摘要

完成条件：

- 进度页、结果页、报告页完成 Phase 3 UI 接入
- Phase 3 全链路验证通过

## 8. Phase 3 明确不做

本期明确不做：

- `judge_calibration_samples`
- review history 不可变审计链
- `bridge adapter`
- 复杂脚本型 probe DSL
- 基于文本声称自动升级为“已验证”

## 9. 完成定义

只有满足以下条件，Phase 3 才算完成：

- 至少支持一种单步 probe 和一种多步 probe
- `business_verification_status` 可稳定落库
- `text_claim_only` 与 `probe_verified` 被严格区分
- 业务验证状态可筛选、可导出、可在报告中查看
- Phase 1/2 既有能力继续可用
