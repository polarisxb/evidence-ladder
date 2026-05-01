# Phase 1 开发任务清单

天鉴 · 衡 Phase 1（Quartet Case Layer）开发任务拆解  
版本：`v0.1-draft`  
日期：`2026-03-28`

## 1. 文档目的

本文档将 [Phase 1 实施方案](./phase1_quartet_case_layer_plan.zh-CN.md) 进一步拆成可以直接排期、分配、开发和验收的任务清单。

本清单只覆盖 Phase 1：

- `Quartet Case Layer`
- `legacy compatibility`
- `case-level read path`

本清单不覆盖后续阶段：

- `adapter`
- `probe`
- `judge calibration`
- `review event log`

## 2. Phase 1 总目标

Phase 1 完成后，系统应满足：

- 默认每个逻辑攻击 case 都会生成 quartet 结果
- 数据库中存在独立的 `attack_cases` 与 `attack_case_variants`
- 旧的 `attack_results` 接口仍然可用
- 前端至少有一个主入口能直接查看 quartet 证据
- 不引入迁移框架的前提下，服务启动即可自动建表并跑通链路

## 3. 任务分组

本期任务分成 6 组：

1. 数据模型
2. 扫描执行
3. 查询 API
4. 前端基础层
5. 前端页面层
6. 验证与回归

## 4. 开发顺序建议

建议按下面顺序推进：

1. `P1-T01` 数据模型落地
2. `P1-T02` case schema 与序列化
3. `P1-T03` quartet 执行辅助函数
4. `P1-T04` 基础模板扫描接入 case layer
5. `P1-T05` 高级攻击引擎接入 case layer
6. `P1-T06` case 查询 API
7. `P1-T07` report / legacy 兼容字段
8. `P1-T08` 前端类型与 API 封装
9. `P1-T09` ScanResults case 视图
10. `P1-T10` Report quartet 详情
11. `P1-T11` ScanProgress case 语义修正
12. `P1-T12` 全链路验证

原因：

- 数据层和扫描层是关键路径
- 前端必须建立在稳定的只读 API 之上
- report 页需要后端先暴露 case 标识和 quartet 明细

## 5. 任务清单

## 5.1 数据模型

### `P1-T01` 新增 `AttackCase` 与 `AttackCaseVariant` model

任务目标：

- 新增 `attack_cases` 表
- 新增 `attack_case_variants` 表
- 保持现有 `attack_results` 不删除、不破坏

影响文件：

- `backend/app/models/attack_case.py`
- `backend/app/models/attack_case_variant.py`
- `backend/app/models/__init__.py`
- 可能需要更新模型关联文件

关键设计要求：

- `AttackCase` 关联 `scan_task_id`
- `AttackCaseVariant` 关联 `attack_case_id`
- `AttackCase` 中保存 `legacy_attack_result_id`
- 不要求给 `attack_results` 新增必填字段

验收标准：

- 启动后数据库自动建出两张新表
- 现有服务启动不报模型导入错误
- 旧扫描与旧查询接口仍可启动

### `P1-T02` 新增 case schema 与序列化层

任务目标：

- 为 case list/detail API 准备 schema
- 为 report 和前端使用准备稳定序列化结构

影响文件：

- `backend/app/schemas/case.py`
- `backend/app/schemas/__init__.py`（如存在）
- 可能更新 `backend/app/schemas/scan.py`

建议产出：

- `AttackCaseListItem`
- `AttackCaseVariantResponse`
- `AttackCaseDetailResponse`

验收标准：

- schema 能表达 case 列表与详情
- 不污染现有 `AttackResultResponse` 兼容结构

## 5.2 扫描执行层

### `P1-T03` 抽出 quartet case 执行辅助函数

任务目标：

- 把 quartet 相关逻辑从“附加分析信息”升级为“独立执行单元”

影响文件：

- `backend/app/services/scan_runner.py`
- 如有必要，可新增：
  - `backend/app/services/case_runner.py`
  - `backend/app/services/case_serializer.py`

建议新增函数：

- `_build_case_variants(...)`
- `_execute_case_variant(...)`
- `_analyze_case_variants(...)`
- `_persist_case_with_legacy_result(...)`

关键要求：

- `attack` variant 仍是主攻击执行入口
- `clean / quoted_attack / benign_distractor` 必须可统一生成
- quartet 默认开启

验收标准：

- `scan_runner` 内部出现清晰的 case 执行边界
- quartet 不再只是 `analysis_raw` 的附加字段来源

### `P1-T04` 基础模板扫描接入 case layer

任务目标：

- 让普通单轮模板和多轮模板都先产出 `attack_case`
- 同时继续产出一条 legacy `attack_result`

影响文件：

- `backend/app/services/scan_runner.py`

关键要求：

- 每个逻辑 payload 只统计为 1 个 case
- `scan_tasks.total_attacks` / `completed_attacks` 口径按 case 计算
- `attack_case`、`attack_case_variants`、`attack_result` 尽量在一个事务内完成

验收标准：

- 基础模板扫描完成后，每个 case 都有：
  - 1 条 `attack_case`
  - 4 条 `attack_case_variants`
  - 1 条 legacy `attack_result`

### `P1-T05` 高级攻击引擎接入 case layer

任务目标：

- `PAIR / TAP / Crescendo / IRIS` 最终结果也写入 case 层

影响文件：

- `backend/app/services/scan_runner.py`
- 如有必要，少量改动：
  - `backend/app/services/pair_engine.py`
  - `backend/app/services/tap_engine.py`
  - `backend/app/services/crescendo_engine.py`
  - `backend/app/services/iris_engine.py`

关键要求：

- 高级引擎先跑出最佳 prompt 或最终 transcript
- 再基于最终攻击文本生成 quartet controls
- 结果仍归并成一个 `attack_case`

验收标准：

- 每种高级引擎至少有一个样本能完成：
  - case 持久化
  - quartet 持久化
  - legacy result 双写

## 5.3 查询 API

### `P1-T06` 新增 case 级查询接口

任务目标：

- 提供 case list 与 case detail 的只读接口

影响文件：

- `backend/app/api/scans.py`
- 新增：
  - `backend/app/api/cases.py`
- `backend/app/api/__init__.py` 或 router 聚合文件

建议接口：

- `GET /api/scans/{scan_id}/cases`
- `GET /api/cases/{case_id}`

关键要求：

- 不替换现有 `GET /reports/{scan_id}/results`
- case detail 必须包含 quartet variants

验收标准：

- 前端可独立读取 case list/detail
- 老结果接口保持兼容

### `P1-T07` 报告与 legacy 兼容字段补齐

任务目标：

- 让 report 或 result 能定位到 case
- 让 quartet 证据能在报告页读取

影响文件：

- `backend/app/api/reports.py`
- `backend/app/services/report_generator.py`
- 如有需要，更新相关 schema

建议补充字段：

- `case_id`
- `case_final_outcome`
- `quartet_present`
- `control_assessment`
- `control_summary`

验收标准：

- report finding 能关联到 case
- 报告页可用 case detail 渲染 quartet 证据

## 5.4 前端基础层

### `P1-T08` 新增前端 case 类型与 API 封装

任务目标：

- 为前端页面接入 case 级数据提供稳定类型层

影响文件：

- `frontend/src/types/index.ts`
- 新增或更新：
  - `frontend/src/api/cases.ts`
  - 如有必要更新 `frontend/src/api/reports.ts`

建议新增类型：

- `AttackCase`
- `AttackCaseVariant`
- `AttackCaseDetail`

验收标准：

- TypeScript 类型完整
- `npm run build` 不因类型冲突失败

## 5.5 前端页面层

### `P1-T09` ScanResults 增加 case 视图

任务目标：

- 让用户在结果页直接查看 case 级结果，而不是只能看 legacy result

影响文件：

- `frontend/src/pages/ScanResults.tsx`

建议做法：

- 增加 `Cases / Legacy Results` 双视图
- 默认优先显示 `Cases`

case 列表建议展示：

- `attack_name`
- `category`
- `case_final_outcome`
- `verdict_status`
- `control_assessment`

验收标准：

- 用户能直接看到 case 级列表
- 旧 legacy results 视图仍可访问

### `P1-T10` Report 页面接入 quartet 详情

任务目标：

- 在报告页为 finding 增加 quartet 证据展示

影响文件：

- `frontend/src/pages/Report.tsx`

建议做法：

- 维持当前 report 顶层结构
- 对每个 finding 增加“查看 quartet 详情”入口
- 展示四个 variants 的：
  - prompt
  - response
  - control summary

验收标准：

- 报告页可展开查看 quartet 证据
- 不需要第一期就全面重写 report 首页统计布局

### `P1-T11` ScanProgress 调整为 case 语义

任务目标：

- 让进度页的统计口径与 case 层一致

影响文件：

- `frontend/src/pages/ScanProgress.tsx`
- 如 websocket 事件调整，可能还会涉及 hook 或 API 层

建议做法：

- 保留当前页面结构
- 把文案从 `attacks` 调整为 `cases`
- 如后端支持，可增加当前 variant 状态展示

验收标准：

- 进度页统计口径与后端 case 数一致
- 页面主链路不退化

## 5.6 验证与回归

### `P1-T12` 后端与前端全链路验证

任务目标：

- 在不引入迁移框架的前提下确认新增表、case 执行、API、前端展示都工作

验证项：

- 服务启动后自动建表
- 基础模板扫描能完成 quartet 持久化
- 至少抽样验证一个高级引擎
- `GET /api/scans/{scan_id}/cases` 正常
- `GET /api/cases/{case_id}` 正常
- `npm run build` 通过
- 结果页可看 case 视图
- 报告页可看 quartet 明细
- legacy result 与旧 review 接口仍可工作

验收标准：

- 新链路可用
- 旧链路未坏

## 6. 推荐分配方式

如果多人并行开发，建议按写入边界拆分：

### 后端 A

负责：

- `P1-T01`
- `P1-T02`
- `P1-T06`

主要写入文件：

- `backend/app/models/*`
- `backend/app/schemas/*`
- `backend/app/api/cases.py`
- `backend/app/api/scans.py`

### 后端 B

负责：

- `P1-T03`
- `P1-T04`
- `P1-T05`
- `P1-T07`

主要写入文件：

- `backend/app/services/scan_runner.py`
- `backend/app/services/report_generator.py`
- `backend/app/api/reports.py`

### 前端

负责：

- `P1-T08`
- `P1-T09`
- `P1-T10`
- `P1-T11`

主要写入文件：

- `frontend/src/types/index.ts`
- `frontend/src/api/*`
- `frontend/src/pages/ScanResults.tsx`
- `frontend/src/pages/Report.tsx`
- `frontend/src/pages/ScanProgress.tsx`

## 7. 里程碑建议

### 里程碑 M1：后端可产出 case 数据

完成任务：

- `P1-T01`
- `P1-T02`
- `P1-T03`
- `P1-T04`

完成标志：

- 一次基础扫描能落出 case 与 quartet variant

### 里程碑 M2：所有扫描路径可双写

完成任务：

- `P1-T05`
- `P1-T06`
- `P1-T07`

完成标志：

- case 读链路打通
- legacy result 兼容仍正常

### 里程碑 M3：前端主入口可查看 quartet

完成任务：

- `P1-T08`
- `P1-T09`
- `P1-T10`
- `P1-T11`
- `P1-T12`

完成标志：

- 用户可通过主 UI 查看 quartet case 结果

## 8. 风险提示

Phase 1 最容易出问题的点有三个：

- quartet 默认化后扫描时长上升
- case 与 legacy result 双写导致一致性问题
- report 页和结果页短期同时存在两套口径，容易让用户混淆

因此实施时必须坚持三条约束：

- 旧接口先保留
- 新页面先增量接入
- case 和 legacy result 尽量在同一事务内完成持久化

## 9. 完成定义

只有当下面条件同时满足时，Phase 1 才算真正完成：

- 默认扫描会生成 quartet case
- 数据库中存在可查询的 case 与 variant 记录
- 旧结果与旧 review 不坏
- 前端至少一个主入口能直接查看 quartet 证据
- 构建与基础扫描验证通过

如果只完成“落库”但前端看不到，或者只完成“前端展示”但双写不稳定，都不应算完成。
