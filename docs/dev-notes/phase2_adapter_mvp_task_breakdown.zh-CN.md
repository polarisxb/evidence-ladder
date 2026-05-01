# Phase 2 开发任务清单

天鉴 · 衡 Phase 2（Adapter MVP）开发任务拆解  
版本：`v0.1-draft`  
日期：`2026-03-28`

## 1. 文档目的

本文档将 [真实业务接入实施方案](./business_integration_implementation_plan.zh-CN.md) 中的 `Phase 2：Adapter MVP` 拆成可以直接排期、分配、开发和验收的任务清单。

本清单只覆盖 Phase 2：

- `adapter resource`
- `adapter-backed scan path`
- `direct HTTP adapter`
- `response extraction`
- `frontend adapter selection and test flow`

本清单不覆盖后续阶段：

- `probe verification`
- `judge calibration`
- `review event log`
- `bridge adapter`
- `adapter` 内任意脚本执行

## 2. Phase 2 总目标

Phase 2 完成后，系统应满足：

- 平台中存在可管理的 `adapter` 资源
- 扫描创建支持 `target_type=adapter`
- 扫描请求支持 `adapter_id + runtime_vars`
- 后端可通过 `direct_http_adapter` 访问真实业务 HTTP API
- 至少支持 `http_json` 与 `openai_chat` 两种 transport 形态
- response extraction 可从结构化响应中稳定提取文本和错误信息
- quartet case layer 与 legacy `attack_results` 兼容链路继续可用
- 现有 `openai_compatible / builtin_vulnerable / custom` 目标类型不被破坏

## 3. 当前基线与工程约束

在开始 Phase 2 前，需要明确几个硬约束。

### 3.1 Phase 1 已完成并且必须保持兼容

当前仓库已经具备：

- `attack_cases`
- `attack_case_variants`
- quartet 默认执行
- case list / detail API
- report 与 results 页的 case 级读取能力

结论：

- Phase 2 不允许破坏现有 case layer
- `attack_results` 兼容层必须继续保留
- adapter 接入后的扫描结果仍必须落到现有 case / legacy 双写结构

### 3.2 当前没有迁移框架

当前数据库仍通过 `Base.metadata.create_all()` 自动建表。

结论：

- Phase 2 应优先采用新增表和新增字段
- 不应依赖复杂的既有表结构重写
- 任何新增持久化概念都应保持 additive

### 3.3 Adapter MVP 不是通用编排平台

本期必须压住 scope，不允许把 adapter 膨胀成通用 DSL。

本期固定约束：

- 不支持任意脚本执行
- 不支持任意表达式
- 只支持固定模板变量
- 只支持有限 transport 类型

### 3.4 Session 隔离仍是默认原则

quartet 四个 variants 仍必须默认使用独立会话。

结论：

- adapter 层必须显式支持 session create / close
- `attack / clean / quoted_attack / benign_distractor` 默认不能共享状态

## 4. 任务分组

本期任务分成 5 组：

1. Adapter 资源模型
2. Adapter 执行与扫描接入
3. Adapter 管理 API
4. 前端 Adapter 接入
5. 验证与回归

## 5. 开发顺序建议

建议按下面顺序推进：

1. `P2-T01` Adapter model 落地
2. `P2-T02` Adapter schema 与固定变量校验
3. `P2-T03` Adapter 模板渲染与 response extraction
4. `P2-T04` Adapter 执行器与 session 生命周期
5. `P2-T05` Adapter CRUD / test API
6. `P2-T06` Scan contract 升级为 `adapter_id + runtime_vars`
7. `P2-T07` `scan_runner` 接入 adapter 与 `custom` 最小映射
8. `P2-T08` 前端类型与 API 封装
9. `P2-T09` Adapter 管理入口
10. `P2-T10` `NewScan` 与扫描页面接入 adapter
11. `P2-T11` 全链路验证

原因：

- 资源定义和执行器是关键路径
- API 设计必须建立在稳定的 adapter schema 之上
- 前端必须建立在后端 CRUD 与 test API 已稳定的前提下

## 6. 任务清单

## 6.1 Adapter 资源模型

### `P2-T01` 新增 `Adapter` model 与基础持久化

任务目标：

- 新增 `adapters` 表
- 定义 Adapter 资源的最小持久化结构
- 为扫描引用 `adapter_id` 提供稳定目标

影响文件：

- 新增：`backend/app/models/adapter.py`
- `backend/app/models/__init__.py`
- 如有必要，更新 `ScanTask` 关联字段

建议字段：

- `id`
- `name`
- `description`
- `mode`
- `transport`
- `base_url`
- `auth_config`
- `session_config`
- `invoke_config`
- `response_extract`
- `enabled`
- `created_at`
- `updated_at`

关键设计要求：

- `mode` 本期只允许 `direct_http_adapter`
- `transport` 本期支持 `http_json | openai_chat`
- 敏感信息不直接写死在文档型字段里，应通过 `secret_ref` 或配置引用表达

验收标准：

- 服务启动后数据库自动建出 `adapters` 表
- 现有服务启动不报模型导入错误
- 旧扫描链路不受影响

### `P2-T02` 新增 Adapter schema 与固定变量校验

任务目标：

- 为 adapter CRUD / test API 准备稳定 schema
- 定义 MVP 范围内的固定模板变量和校验规则

影响文件：

- 新增：`backend/app/schemas/adapter.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/scan.py`

建议产出：

- `AdapterCreate`
- `AdapterUpdate`
- `AdapterResponse`
- `AdapterTestRequest`
- `AdapterTestResponse`

固定变量范围：

- `{{runtime.*}}`
- `{{session.id}}`
- `{{input.prompt}}`
- `{{input.history}}`
- `{{scan.id}}`
- `{{case.id}}`
- `{{variant.type}}`

关键设计要求：

- 不支持任意表达式
- 不支持模板函数
- 不支持脚本
- schema 层必须拒绝未知 transport、未知 auth 类型、未知变量占位

验收标准：

- adapter schema 可表达 CRUD 与 test 请求
- 无法通过 schema 绕过 MVP 边界

## 6.2 Adapter 执行与扫描接入

### `P2-T03` 新增模板渲染器与 response extraction

任务目标：

- 实现固定变量渲染器
- 实现结构化响应提取

影响文件：

- 新增：`backend/app/services/adapter_renderer.py`
- 新增：`backend/app/services/adapter_extractors.py`

关键设计要求：

- 渲染器只做简单占位替换，不做求值
- response extraction 至少支持：
  - `text_path`
  - `error_path`
  - `tool_calls_path`
- 对提取失败、空路径、不匹配路径要有可解释错误

验收标准：

- 给定 adapter 定义与 runtime payload，能稳定渲染请求
- 给定 HTTP 响应 JSON，能提取 `response_text` 或结构化错误

### `P2-T04` 新增 Adapter 执行器与 session 生命周期

任务目标：

- 实现 adapter 调用执行层
- 管理 quartet variant 的独立会话

影响文件：

- 新增：`backend/app/services/adapter_executor.py`
- 如有必要，新建小型辅助模块处理 auth / session

关键设计要求：

- `session.create` / `session.close` 可选，但 schema 和执行器都要支持
- quartet variants 默认 `per_variant_isolated`
- 执行器输出必须包含：
  - `response_text`
  - `response_status`
  - `response_error`
  - `latency_ms`
  - 最小 transport metadata

验收标准：

- 给定 adapter 定义，可独立执行一次 invoke
- 若配置 session create / close，四个 variants 能分别建立独立会话

### `P2-T05` Scan contract 升级为 `adapter_id + runtime_vars`

任务目标：

- 扩展扫描创建契约
- 让扫描任务能引用 adapter 资源

影响文件：

- `backend/app/schemas/scan.py`
- `backend/app/models/scan_task.py`
- `backend/app/api/scans.py`

建议新增字段：

- `target_type = adapter`
- `adapter_id`
- `runtime_vars`

关键设计要求：

- 继续保留 `openai_compatible`
- 继续保留 `builtin_vulnerable`
- 继续保留 `custom`
- `adapter` 型扫描必须显式传 `adapter_id`

验收标准：

- 可创建 `target_type=adapter` 的扫描
- 旧 target type 的扫描创建接口保持兼容

### `P2-T06` `scan_runner` 接入 adapter 与 `custom` 最小映射

任务目标：

- 让扫描主流程可以走 adapter 执行器
- 给现有 `custom` 目标提供最小 adapter 映射

影响文件：

- `backend/app/services/scan_runner.py`
- 如有必要，新增：`backend/app/services/adapter_mapping.py`

关键设计要求：

- `target_type=adapter` 走 adapter 执行器
- `target_type=custom` 继续可用，但内部可映射为最小 adapter：
  - `method = POST`
  - `body_template = { "message": "{{input.prompt}}", "history": "{{input.history}}" }`
  - `response_extract = raw_text`
- adapter 扫描结果仍写入：
  - `attack_cases`
  - `attack_case_variants`
  - `attack_results`

验收标准：

- adapter 型扫描能完成 quartet 执行和双写落库
- `custom` 兼容模式不被破坏

## 6.3 Adapter 管理 API

### `P2-T07` 新增 Adapter CRUD 与 test API

任务目标：

- 提供 adapter 资源管理接口
- 提供独立于扫描的 test 能力

影响文件：

- 新增：`backend/app/api/adapters.py`
- `backend/app/api/__init__.py`

建议接口：

- `POST /api/v1/adapters`
- `GET /api/v1/adapters`
- `GET /api/v1/adapters/{adapter_id}`
- `PATCH /api/v1/adapters/{adapter_id}`
- `POST /api/v1/adapters/test`
- `POST /api/v1/adapters/probe/test`

关键设计要求：

- `adapters/test` 至少验证：
  - auth 是否可用
  - session create 是否成功
  - invoke 是否可达
  - response extract 是否可提取文本
- `probe/test` 本期只保留接口壳和请求校验
- 不在 Phase 2 执行真实 probe 逻辑

验收标准：

- 用户可在不创建扫描的前提下测试 adapter
- CRUD 与 test API 都能独立使用

## 6.4 前端 Adapter 接入

### `P2-T08` 新增前端 Adapter 类型与 API 封装

任务目标：

- 为 adapter CRUD / test / scan 接入提供稳定类型层

影响文件：

- `frontend/src/types/index.ts`
- 新增：`frontend/src/api/adapters.ts`
- `frontend/src/api/scans.ts`

建议新增类型：

- `Adapter`
- `AdapterConfig`
- `AdapterTestRequest`
- `AdapterTestResult`
- `AdapterScanConfig`

验收标准：

- TypeScript 类型完整
- `npm run build` 不因类型冲突失败

### `P2-T09` 新增 Adapter 管理入口

任务目标：

- 让用户可以创建、编辑、测试和查看 adapter

影响文件：

- 新增：`frontend/src/pages/Adapters.tsx`
- 如有必要，新增管理组件或表单组件
- 路由聚合文件

建议能力：

- adapter 列表
- adapter 创建 / 编辑
- adapter test
- 启用 / 禁用状态展示

关键设计要求：

- 管理页与 `NewScan` 解耦
- 不把完整 CRUD 表单塞进扫描创建页

验收标准：

- 用户可以先保存 adapter，再在扫描页选择它

### `P2-T10` `NewScan` 与扫描页面接入 adapter

任务目标：

- 让扫描创建和扫描页面认知 `adapter` 目标类型

影响文件：

- `frontend/src/pages/NewScan.tsx`
- 如有必要，少量改动：
  - `frontend/src/pages/ScanProgress.tsx`
  - `frontend/src/pages/ScanResults.tsx`
  - 扫描列表页

建议改造：

- `NewScan` 新增 `target_type=adapter`
- 增加 adapter 选择器
- 增加 `runtime_vars` 编辑区
- 将 `custom` 标为兼容模式
- 扫描列表 / 进度页 / 结果页至少能显示当前目标来自 adapter

验收标准：

- 用户可以通过 UI 创建 adapter 型扫描
- adapter 型扫描在主要页面上可被识别

## 6.5 验证与回归

### `P2-T11` Adapter MVP 全链路验证

任务目标：

- 在不引入迁移框架的前提下确认 adapter CRUD、adapter test、adapter scan 和前端创建流程都工作

验证项：

- 服务启动后自动建出 `adapters` 表
- `POST /api/v1/adapters` 正常
- `POST /api/v1/adapters/test` 正常
- `target_type=adapter` 的扫描能完成 quartet 落库
- `custom` 兼容模式仍可扫描
- `npm run build` 通过
- 至少接通两个真实业务 API

验收标准：

- 至少两个真实 API 样例可用
- 不要求客户重构原始业务 API

## 7. 推荐分配方式

如果多人并行开发，建议按写入边界拆分：

### 后端 A

负责：

- `P2-T01`
- `P2-T02`
- `P2-T05`
- `P2-T07`

主要写入文件：

- `backend/app/models/*`
- `backend/app/schemas/*`
- `backend/app/api/adapters.py`
- `backend/app/api/scans.py`

### 后端 B

负责：

- `P2-T03`
- `P2-T04`
- `P2-T06`
- `P2-T11`

主要写入文件：

- `backend/app/services/adapter_*`
- `backend/app/services/scan_runner.py`
- adapter test 样例与验证脚本

### 前端

负责：

- `P2-T08`
- `P2-T09`
- `P2-T10`

主要写入文件：

- `frontend/src/types/*`
- `frontend/src/api/*`
- `frontend/src/pages/Adapters.tsx`
- `frontend/src/pages/NewScan.tsx`

## 8. 里程碑建议

### 里程碑 M1：Adapter 资源与 test API 可用

完成任务：

- `P2-T01`
- `P2-T02`
- `P2-T03`
- `P2-T04`
- `P2-T07`

完成标志：

- adapter 可创建、读取、测试

### 里程碑 M2：Adapter 扫描链路可用

完成任务：

- `P2-T05`
- `P2-T06`

完成标志：

- adapter 型扫描能完成 quartet case 双写
- `custom` 兼容模式不退化

### 里程碑 M3：前端可创建并使用 Adapter

完成任务：

- `P2-T08`
- `P2-T09`
- `P2-T10`
- `P2-T11`

完成标志：

- 用户可通过主 UI 配置 adapter、测试 adapter、发起 adapter 扫描

## 9. 风险提示

Phase 2 最容易出问题的点有四个：

- adapter 范围过早膨胀成通用编排平台
- session 生命周期设计不清，导致 quartet 对照失真
- response extraction 设计太弱，导致“调用成功但文本抽取失败”
- `custom` 兼容迁移做坏，破坏现有扫描入口

因此实施时必须坚持四条约束：

- 本期不支持任意脚本执行
- 本期只支持固定变量模板
- quartet variants 默认独立 session
- `custom` 只做兼容迁移，不做硬切退役

## 10. 完成定义

只有当下面条件同时满足时，Phase 2 才算真正完成：

- 平台中存在可管理的 adapter 资源
- 扫描支持 `target_type=adapter`
- adapter 扫描能稳定落出 quartet case 与 legacy result
- adapter test API 可独立验证真实业务入口
- 前端可配置并使用 adapter
- 至少两个真实业务 API 已接通
- 旧 target type 与旧扫描链路未坏

如果只完成“保存 adapter”但不能发起扫描，或者只完成“能扫描”但 UI 无法接入，都不应算完成。
