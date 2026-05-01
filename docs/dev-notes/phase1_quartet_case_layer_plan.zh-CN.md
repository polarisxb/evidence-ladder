# Phase 1 实施方案：Quartet Case Layer

天鉴 · 衡 Phase 1 工程实施方案  
版本：`v0.1-draft`  
日期：`2026-03-28`  
编码：`UTF-8 with BOM`

## 1. Phase 1 的定位

Phase 1 只做一件核心事情：

把当前“以 `attack_results` 为中心的扁平攻击结果流”升级成“以逻辑 case 为中心的 quartet 评测流”，并且保持现有扫描、结果、报告、人工复核链路继续可用。

Phase 1 的目标不是一次性完成整个真实业务接入路线图，而是先把“攻击是否真的成立”这件事做成默认协议。

这一期的关键词只有三个：

- `case layer`
- `quartet by default`
- `legacy compatibility`

## 2. 当前基线与工程约束

在开始 Phase 1 前，需要先明确当前代码的几个硬约束。

### 2.1 当前数据库初始化方式

当前项目没有迁移框架，数据库初始化方式是启动时执行：

- [backend/app/database.py](../backend/app/database.py)
- [backend/app/main.py](../backend/app/main.py)

关键点：

- 使用 `Base.metadata.create_all()` 自动建表
- 这适合“新增表”
- 这不适合“自动修改已有表结构”

这意味着：

- Phase 1 应优先采用“新增表 + 兼容层双写”
- 尽量不要依赖对既有 `attack_results` / `scan_tasks` 表做大量结构变更
- 如果后续必须改旧表，应单独引入迁移方案，而不是把风险混在 Phase 1 中

### 2.2 当前核心数据模型

当前只有两张核心业务表：

- [backend/app/models/scan_task.py](../backend/app/models/scan_task.py)
- [backend/app/models/attack_result.py](../backend/app/models/attack_result.py)

当前特点：

- `scan_tasks` 负责扫描级聚合
- `attack_results` 是结果级主存储
- 前端结果页、进度页、报告页主要围绕 `attack_results` 工作

### 2.3 当前 quartet 能力的位置

当前 quartet 相关能力已经有雏形，但仍是附加能力：

- [backend/app/services/control_variants.py](../backend/app/services/control_variants.py)
- [backend/app/services/scan_runner.py](../backend/app/services/scan_runner.py)

当前特点：

- `Attack / Clean / Quoted Attack / Benign Distractor` 已能生成
- `enable_control_variants` 仍是高级开关
- 结果主要塞在 `analysis_raw` 中
- 还没有独立的 case / variant 持久化模型

### 2.4 当前 API 与前端耦合点

当前主要耦合点：

- 扫描创建与列表：[backend/app/api/scans.py](../backend/app/api/scans.py)
- 报告与结果：[backend/app/api/reports.py](../backend/app/api/reports.py)
- 结果页类型：[frontend/src/types/index.ts](../frontend/src/types/index.ts)
- 结果页：[frontend/src/pages/ScanResults.tsx](../frontend/src/pages/ScanResults.tsx)
- 报告页：[frontend/src/pages/Report.tsx](../frontend/src/pages/Report.tsx)
- 进度页：[frontend/src/pages/ScanProgress.tsx](../frontend/src/pages/ScanProgress.tsx)

结论：

- Phase 1 不能粗暴替换 `attack_results`
- 必须新增 case 视图，同时保留旧结果接口与旧页面语义
- 先把 case layer 接入，再逐步把前端切换到 case 级展示

## 3. Phase 1 范围

### 3.1 本期要交付的内容

Phase 1 必须交付：

1. `attack_cases` 新表
2. `attack_case_variants` 新表
3. quartet 默认化执行逻辑
4. case 级只读查询 API
5. 结果页与报告页可读取 case 级数据
6. 保留 `attack_results` 兼容层与现有 review 接口

### 3.2 本期明确不做的内容

Phase 1 不做：

- `adapter` 资源化
- `bridge adapter`
- `probe` 业务副作用验证
- `judge calibration samples`
- review 事件流重构
- 浏览器/页面级 agent 自动化

这些内容都放到后续 Phase。

## 4. Phase 1 关键设计决策

### 4.1 一个逻辑攻击 case 只算一次攻击

无论一个 case 内部跑几个 variants，扫描统计口径都按“逻辑 case 数”计算。

结论：

- `scan_tasks.total_attacks` 表示逻辑 case 数
- `scan_tasks.completed_attacks` 表示已完成 case 数
- 不按 4 倍 variant 数去放大扫描统计

这样可以保持当前 Dashboard、进度页、报告页对“攻击数”的理解基本稳定。

### 4.2 `attack_results` 继续保留，作为兼容镜像

Phase 1 不废弃 `attack_results`。

设计上：

- `attack_cases` 才是新的逻辑主记录
- `attack_case_variants` 保存 quartet 细节
- `attack_results` 继续保存与 `attack` variant 对应的一条兼容结果，供现有 API 和页面使用

这意味着：

- 老接口还能工作
- 现有人工复核还能工作
- 前端不需要一次性重写全部页面

### 4.3 quartet 改为默认开启，但保留回退开关

当前 `AdvancedConfig.enable_control_variants` 默认值是 `false`：

- [backend/app/schemas/scan.py](../backend/app/schemas/scan.py)

Phase 1 的处理方式：

- 后端运行时默认按 `True` 执行
- 配置项保留，但降级为“回退开关”
- 前端不再把它当主选项暴露

推荐实现：

- `adv.get("enable_control_variants", True)`

这样做的原因：

- 新扫描默认进入 quartet 协议
- 老任务如果没写这个字段，也能自动使用 quartet
- 如果上线后发现性能或稳定性问题，还可以临时关掉

### 4.4 Phase 1 尽量不改旧表结构

因为当前没有迁移框架，所以本期优先：

- 新增 `attack_cases`
- 新增 `attack_case_variants`
- 不给 `attack_results` 强加新的必需列
- 旧表与新表通过新表中的外键或引用关系连接

推荐做法：

- 在 `attack_cases` 中保存 `legacy_attack_result_id`
- 不反向给 `attack_results` 增列

这是为了避免在现有 `create_all()` 模式下出现表结构漂移问题。

## 5. 数据模型设计

## 5.1 新表：`attack_cases`

用途：表示一个逻辑攻击评测单元。

建议字段：

- `id`
- `scan_task_id`
- `template_id`
- `category`
- `technique`
- `attack_name`
- `protocol_version`
- `case_status`
- `case_final_outcome`
- `attack_variant_response`
- `control_assessment`
- `control_summary`
- `verdict_status`
- `verdict_reason`
- `legacy_attack_result_id`
- `summary_json`
- `created_at`
- `updated_at`

说明：

- `case_final_outcome` 建议先与当前 control assessment 对齐
- `legacy_attack_result_id` 指向现有兼容 `attack_results.id`
- `summary_json` 用于存放当前阶段不稳定但前端有价值的聚合字段

建议取值：

- `case_status`: `pending | running | completed | failed`
- `case_final_outcome`: `attack_delta_supported | discussion_supported | controls_inconclusive | controls_missing | passed`

其中：

- `passed` 是 case 层最终结果
- `controls_missing` 仅用于兼容回退场景

## 5.2 新表：`attack_case_variants`

用途：保存 quartet 变体明细。

建议字段：

- `id`
- `attack_case_id`
- `variant_type`
- `position`
- `request_text`
- `response_text`
- `response_error`
- `response_status`
- `latency_ms`
- `analysis_raw`
- `is_primary`
- `started_at`
- `completed_at`
- `created_at`

建议取值：

- `variant_type`: `attack | clean | quoted_attack | benign_distractor`

说明：

- `is_primary = true` 只给 `attack` variant
- `response_error` 负责保留调用失败信息，不把错误全丢进文本字段里
- `analysis_raw` 保存该 variant 的结构化分析结果

## 5.3 与 legacy 表的关系

关系如下：

- `scan_tasks 1 - N attack_cases`
- `attack_cases 1 - N attack_case_variants`
- `attack_cases 1 - 1 attack_results(legacy mirror)`

兼容策略：

- `attack_results` 仍然由扫描主流程创建
- 但其语义退化为“attack variant 的兼容投影”
- 新页面和新报告优先读取 case 层

## 6. 扫描执行设计

## 6.1 执行单元从 payload result 升级为 logical case

当前 `_execute_payload_attempt()` 返回的是一条 attack 结果：

- [backend/app/services/scan_runner.py](../backend/app/services/scan_runner.py)

Phase 1 改造方向：

新增三个核心步骤：

1. 构造 quartet variants
2. 执行并分析所有 variants
3. 聚合成 case + legacy result

建议新增内部函数：

- `_build_case_variants(template, payload_text)`
- `_execute_case_variant(task, variant)`
- `_analyze_case_variants(...)`
- `_persist_case_with_legacy_result(...)`

## 6.2 基础模板攻击流程

对普通单轮模板：

1. 用 payload 生成一个 `attack_case`
2. 先执行 `attack` variant
3. 基于 attack payload 生成 `clean / quoted_attack / benign_distractor`
4. 并发执行控制组
5. 对 quartet 结果做聚合
6. 生成 case-level outcome
7. 生成一条 legacy `attack_result`
8. 一次提交事务

说明：

- attack 先执行，是因为控制组构造依赖 attack payload
- 控制组可继续并发执行，减少额外耗时

## 6.3 多轮模板攻击流程

对多轮模板：

- `attack` variant 仍按当前多轮逻辑执行
- `payload_text` 使用合并后的 transcript
- `target_response` 使用最终一轮的目标回复
- 控制组继续围绕“合并后的攻击 transcript”构造

Phase 1 不尝试为多轮模板生成真正的多轮 control conversation。

原因：

- 这会显著扩大本期复杂度
- 当前阶段先保证“有 quartet 证据链”比“所有变体都完整多轮复现”更重要

## 6.4 高级攻击引擎流程

对 `PAIR / TAP / Crescendo / IRIS`：

- 高级引擎继续先跑出最佳 prompt 或最终 transcript
- 然后基于最终攻击 prompt / transcript 生成 quartet controls
- 结果仍归并成一个 `attack_case`
- 同时生成一条 legacy `attack_result`

这样可以保持当前高级引擎实现大体不动，只在“最终结果落盘”前插入 case layer。

## 6.5 事务策略

Phase 1 推荐一个逻辑 case 使用一次数据库事务提交：

- `attack_case`
- `attack_case_variants`
- `attack_result(legacy)`

必须保证这三者要么一起成功，要么一起失败。

原因：

- 避免 case 层和 legacy 层出现部分写入
- 避免报告与结果页读取到互相矛盾的数据

如果提交失败：

- 当前 case 标记失败
- 记录日志
- 继续由 scan-level 错误处理决定是否终止整个扫描

## 7. Case 聚合逻辑

Phase 1 不引入新的大模型 judge，只复用现有：

- `analyze_response()`
- `classify_verdict()`
- `summarize_control_comparison()`

case 聚合输出至少应包括：

- `case_final_outcome`
- `control_assessment`
- `control_summary`
- `verdict_status`
- `verdict_reason`
- `primary_attack_successful`
- `quartet_present`

推荐聚合规则：

1. `attack` variant 仍是主要风险判断来源
2. quartet controls 负责判断“这个风险是否具有 attack-only delta”
3. `case_final_outcome` 优先使用 quartet 对照结果，而不是只看 attack variant
4. legacy `attack_result.attack_successful` 继续沿用 attack variant 的兼容语义

换句话说：

- case 层代表“可信解释后的最终结论”
- legacy result 代表“兼容当前页面和 API 的主攻击结果”

## 8. API 设计

## 8.1 保持现有 API 不破坏

Phase 1 保持这些接口兼容：

- `POST /api/scans`
- `GET /api/scans`
- `GET /api/reports/{scan_id}/results`
- `GET /api/reports/{scan_id}`
- `POST /api/reports/results/{result_id}/review`

目的：

- 现有前端和已有使用者不被一次性打断

## 8.2 新增 case 级只读接口

Phase 1 新增：

- `GET /api/scans/{scan_id}/cases`
- `GET /api/cases/{case_id}`

建议返回结构：

### `GET /api/scans/{scan_id}/cases`

返回：

- case 列表
- 分页信息
- case 级筛选字段

每条 case 至少包含：

- `id`
- `attack_name`
- `category`
- `technique`
- `case_status`
- `case_final_outcome`
- `verdict_status`
- `control_assessment`
- `legacy_attack_result_id`
- `created_at`

### `GET /api/cases/{case_id}`

返回：

- case 基本信息
- quartet variants
- case summary
- legacy result 摘要

Phase 1 不新增 case 级 review 写接口。

理由：

- 当前 review 已经能落在 legacy result 上
- 先把 case 级读链路跑顺，再做 review 事件流改造

## 9. 前端实施方案

## 9.1 类型层

在 [frontend/src/types/index.ts](../frontend/src/types/index.ts) 新增：

- `AttackCase`
- `AttackCaseVariant`
- `AttackCaseDetail`

旧的 `AttackResult` 不删除。

## 9.2 API 层

新增前端 API：

- `getAttackCases(scanId)`
- `getAttackCase(caseId)`

旧的：

- `getAttackResults(scanId)`
- `getReport(scanId)`

继续保留。

## 9.3 Scan Results 页面

目标文件：

- [frontend/src/pages/ScanResults.tsx](../frontend/src/pages/ScanResults.tsx)

Phase 1 改造建议：

- 页面默认切到 case 级列表
- 保留切换到 legacy result 视图的兼容入口，或保留当前行为但增加 case tab
- case 列表展示：
  - `attack_name`
  - `category`
  - `case_final_outcome`
  - `verdict_status`
  - `control_assessment`

推荐策略：

- 第一步先做双 tab：`Cases / Legacy Results`
- 稳定后再考虑把 legacy result 降为次级视图

## 9.4 Report 页面

目标文件：

- [frontend/src/pages/Report.tsx](../frontend/src/pages/Report.tsx)

Phase 1 改造建议：

- 报告主统计暂时仍沿用当前 scan/report 结构
- finding detail 增加 quartet 证据块
- 当用户展开 finding 时，可拉取 `case detail`
- 展示四个 variants 的 prompt / response / analysis 摘要

这样做的好处：

- 不需要第一期就推翻整个 `SecurityReport` 结构
- 但用户已经能看到 quartet 证据链

## 9.5 Scan Progress 页面

目标文件：

- [frontend/src/pages/ScanProgress.tsx](../frontend/src/pages/ScanProgress.tsx)

Phase 1 改造建议：

- 进度统计仍复用 `completed_attacks / total_attacks`
- 文案逐步改成 “cases” 而不是 “attacks”
- 如果新增 websocket 事件，可显示当前 case 正在执行哪个 variant

这一页不要求第一期就做成完整的 quartet 可视化，只要统计口径正确即可。

## 10. WebSocket 与进度事件

当前 websocket 事件以 `attack_started / attack_completed` 为主。

Phase 1 建议：

- 保留现有事件名称，语义改为“逻辑 case”开始与完成
- 新增可选事件：
  - `variant_started`
  - `variant_completed`

这样可以保证：

- 老前端不会直接坏掉
- 新前端可以逐步消费更细的 quartet 进度

## 11. 报告与统计口径

Phase 1 不全面重写报告生成器，但要做两件事：

1. 让 report finding 能定位到 case
2. 增加最基础的 quartet 统计

建议新增的轻量级统计字段：

- `quartet_cases_total`
- `quartet_supported_findings`
- `controls_inconclusive_count`
- `controls_missing_count`

这些字段可以先放在 report JSON 中，不要求第一期首页全部展示。

## 12. 开发任务拆解

### 12.1 后端数据层

任务：

- 新增 `AttackCase` model
- 新增 `AttackCaseVariant` model
- 更新 [backend/app/models/__init__.py](../backend/app/models/__init__.py)
- 新增 schema 定义

验收：

- 服务启动后能自动建出新表
- 不影响旧表加载与旧扫描启动

### 12.2 后端扫描层

任务：

- 改造 `scan_runner`，引入 case 执行与持久化逻辑
- 默认开启 quartet
- 抽出 case 级聚合函数
- 对基础模板与高级引擎统一接入 case 持久化

验收：

- 每个逻辑攻击 case 都产生 1 条 `attack_case`
- 每个 case 默认产生 4 条 `attack_case_variants`
- 同时仍产生 1 条 legacy `attack_result`

### 12.3 后端 API 层

任务：

- 新增 case list/detail 接口
- 为 report finding 暴露 `case_id` 或 case summary

验收：

- 前端可拉到 case 列表
- 报告页可按 finding 读取 quartet 明细

### 12.4 前端类型与 API

任务：

- 新增 case 类型
- 新增 case API 封装

验收：

- TypeScript 编译通过
- 不破坏旧报告和旧结果页调用

### 12.5 前端页面

任务：

- ScanResults 增加 case 视图
- Report finding detail 增加 quartet 视图
- ScanProgress 文案切换为 case 语义

验收：

- 用户可在 UI 中直接看到 quartet 证据
- 旧页面主链路仍可正常使用

## 13. 测试与验证方案

当前项目自动化业务测试较少，因此 Phase 1 至少需要以下验证。

### 13.1 后端验证

- 服务启动后自动创建新表
- 基础模板扫描能正常完成
- `PAIR / TAP / Crescendo / IRIS` 至少各抽一个样本跑通
- `GET /api/scans/{scan_id}/cases` 返回正常
- `GET /api/cases/{case_id}` 返回 quartet 详情

### 13.2 前端验证

- `npm run build` 通过
- case 列表正常加载
- report finding 能展开 quartet 详情
- 旧结果页和旧报告页没有被破坏

### 13.3 兼容性验证

- 老扫描记录仍能查看 legacy report
- 新扫描记录既能看 legacy result，也能看 case result
- review 旧接口仍可操作，并能反映在报告中

## 14. 风险与回退策略

### 14.1 主要风险

- quartet 默认化导致扫描时长上升
- case 与 legacy result 双写导致一致性复杂度上升
- 老页面与新 case 视图的口径短期并存，用户可能混淆

### 14.2 回退策略

- 保留 `enable_control_variants` 作为后端回退开关
- 保留 legacy `attack_results` 与旧结果接口
- 新页面优先做“增量展示”，不一次性删除旧视图

## 15. Phase 1 验收标准

Phase 1 完成后，必须满足：

1. 默认新扫描会生成 quartet 结果，而不是只有 attack payload 结果
2. 每个逻辑攻击 case 在数据库中都有独立记录
3. `attack_results` 兼容接口仍然可用
4. 前端结果页或报告页至少有一个入口可直接查看 quartet 证据
5. 不引入迁移框架的前提下，服务启动即可创建新表并跑通链路

## 16. Phase 1 完成后的结果

如果本期按上述方案完成，项目会从：

- “附带一些 control 信息的攻击结果平台”

升级为：

- “默认以 quartet case 为基本评测单元的黑盒评测平台”

这会为后续的：

- `adapter`
- `probe`
- `judge calibration`
- `review event log`

提供稳定的协议基础，而不会把所有复杂度同时压在一个版本里。