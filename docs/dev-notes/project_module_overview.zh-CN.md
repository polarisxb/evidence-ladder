# 天鉴 · 衡 — 项目模块总览

> 最后更新：2026-04-08

---

## 一、项目概述

**天鉴 · 衡** 是一个面向真实 AI 应用的 Prompt Injection 黑盒安全评测平台。项目采用前后端分离架构，后端基于 Python FastAPI，前端基于 React + TypeScript，同时提供模拟靶标（Mock Target）供开发与演示使用。

**技术栈总览：**

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy (async)、aiosqlite、OpenAI SDK、Anthropic SDK |
| 前端 | React 19、TypeScript 5.9、Vite 8、TailwindCSS 4、Recharts、Lucide Icons |
| 模拟靶标 | FinanceBot (Java 17 + Spring Boot 3.2)、ShopBot (Node 20 + Express + TypeScript + SQLite) |
| 部署 | Docker Compose（backend:8000, frontend:5173） |

---

## 二、顶层目录结构

```
ai-security/
├── backend/            # 后端服务（FastAPI）
├── frontend/           # 前端 SPA（React + Vite）
├── mock_targets/       # 模拟靶标应用
│   ├── financebot/     #   金融客服机器人（Java）
│   └── shopbot/        #   电商客服机器人（Node.js）
├── demo/               # 演示配置与示例 prompt
├── docs/               # 设计文档、论文、原型
├── output/             # 扫描输出数据目录
├── docker-compose.yml  # 容器编排
└── README.md           # 项目入口文档
```

---

## 三、后端模块（`backend/`）

后端是整个平台的核心，运行在端口 **8000**，入口文件为 `app/main.py`。

### 3.1 API 路由层（`app/api/`）

所有路由挂载在 `/api/v1` 前缀下。

| 文件 | 路由前缀 | 职责 |
|------|---------|------|
| `scans.py` | `/scans` | 扫描任务 CRUD、启动/暂停/恢复扫描 |
| `cases.py` | `/cases` | 攻击用例查询 |
| `targets.py` | `/targets` | 扫描目标管理 |
| `reports.py` | `/reports` | 报告生成与导出（HTML/PDF/JSON） |
| `templates.py` | `/templates` | 攻击模板管理 |
| `stats.py` | `/stats` | 统计仪表盘数据 |
| `settings.py` | `/settings` | 系统设置 |
| `model_providers.py` | `/model-providers` | 模型供应商配置（多模型管理） |
| `adapters.py` | `/adapters` | 适配层管理（对接真实业务 API） |
| `judge_calibration.py` | `/judge/calibration` | Judge 校准实验管理 |

### 3.2 数据模型层（`app/models/`）

基于 SQLAlchemy 2.0 异步 ORM，使用 SQLite 存储。

| 模型 | 说明 |
|------|------|
| `ScanTask` | 扫描任务（目标配置、状态、进度） |
| `AttackResult` | 单次攻击结果（prompt、response、裁决） |
| `AttackCase` | 攻击用例（与模板、扫描任务关联） |
| `AttackCaseVariant` | 四元对照变体（Clean / Attack / Quoted Attack / Benign Distractor） |
| `Adapter` | 适配层配置（对接自定义业务 API） |
| `ModelProvider` | 模型供应商配置 |
| `JudgeCalibrationRun` | Judge 校准运行记录 |
| `JudgeCalibrationSample` | Judge 校准样本 |

### 3.3 Schema 层（`app/schemas/`）

基于 Pydantic v2 的请求/响应数据验证。

| 文件 | 覆盖范围 |
|------|---------|
| `scan.py` | 扫描任务创建、响应、进度 |
| `case.py` | 攻击用例 |
| `report.py` | 报告结构 |
| `adapter.py` | 适配层配置 |
| `model_provider.py` | 模型供应商 |
| `judge_calibration.py` | 校准实验 |

### 3.4 服务层（`app/services/`）— 核心业务逻辑

这是项目最核心的模块，包含扫描引擎、攻击引擎、裁决引擎等。

#### 3.4.1 扫描编排

| 文件 | 职责 |
|------|------|
| `scan_runner.py` | 扫描主编排器：加载模板 → 生成用例 → 调度攻击引擎 → 收集结果 → 更新进度 |
| `scan_recovery.py` | 扫描恢复（中断后续跑） |
| `case_executor.py` | 单个攻击用例的执行器，含变体（四元对照）执行逻辑 |
| `case_persistence.py` | 攻击用例持久化（落库） |
| `case_serializer.py` | 用例序列化 |
| `control_variants.py` | 四元对照变体生成（Clean / Quoted Attack / Benign Distractor） |

#### 3.4.2 攻击引擎

| 文件 | 攻击模式 | 说明 |
|------|---------|------|
| `attack_engine.py` | 基础攻击 | 直接发送攻击 prompt |
| `pair_engine.py` | PAIR | Prompt Automatic Iterative Refinement |
| `tap_engine.py` | TAP | Tree of Attacks with Pruning |
| `crescendo_engine.py` | Crescendo | 逐步升级式多轮攻击 |
| `iris_engine.py` | IRIS | Self-Explanation 引导式攻击 |
| `mutation_engine.py` | Mutation/Fuzzing | Prompt 变异与模糊测试 |
| `msj_engine.py` | MSJ | Many-Shot Jailbreaking |
| `ice_engine.py` | ICE | In-Context Extraction |
| `fitd_engine.py` | FITD | Foot-in-the-Door 渐进式攻击 |

#### 3.4.3 裁决与分析

| 文件 | 职责 |
|------|------|
| `ai_analyzer.py` | AI 裁决主引擎：调用 LLM 进行结构化行为判定（execution_mode / blackbox_outcome / behavior_flags） |
| `verdict_engine.py` | 综合裁决引擎：规则判定 + AI 判定融合 |
| `risk_scorer.py` | 风险评分（CVSS 向量生成） |
| `probe_assertions.py` | Probe 断言：基于规则的快速检测（canary token 命中等） |
| `probe_executor.py` | Probe 执行器 |

#### 3.4.4 Judge 校准

| 文件 | 职责 |
|------|------|
| `judge_calibration_runner.py` | 校准运行器 |
| `judge_metrics.py` | 校准指标计算 |
| `judge_sampling.py` | 校准样本抽取 |

#### 3.4.5 基础设施

| 文件 | 职责 |
|------|------|
| `llm_client.py` | 通用 LLM 客户端（支持 OpenAI / Anthropic / OpenAI-compatible） |
| `target_client.py` | 目标客户端（向被测目标发请求） |
| `vulnerable_ai.py` | 内置脆弱 AI（`builtin_vulnerable` 模式，用于验证链路） |
| `report_generator.py` | 报告生成（HTML/PDF） |
| `adapter_executor.py` | 适配层执行器（对接真实业务 API） |
| `adapter_extractors.py` | 适配层响应提取 |
| `adapter_renderer.py` | 适配层模板渲染 |
| `engine_utils.py` | 引擎公用工具 |

### 3.5 核心基础模块（`app/core/`）

| 文件 | 职责 |
|------|------|
| `auth.py` | 认证中间件（API Secret 校验） |
| `exceptions.py` | 全局异常定义与处理 |
| `frameworks.py` | 安全框架映射（NIST / MITRE ATLAS / OWASP） |
| `openai_client.py` | OpenAI 客户端单例 |

### 3.6 攻击模板（`app/attack_templates/`）

JSON 格式的预置攻击模板，每个模板包含多条攻击 prompt 及元数据。

| 文件 | 攻击类别 |
|------|---------|
| `prompt_injection.json` | Prompt 注入 |
| `jailbreak.json` | 越狱攻击 |
| `information_disclosure.json` | 信息泄露 |
| `system_prompt_extraction.json` | System Prompt 提取 |
| `indirect_injection.json` | 间接注入 |
| `excessive_agency.json` | 越权执行 |
| `denial_of_service.json` | 拒绝服务 |

### 3.7 配置与数据库

| 文件 | 职责 |
|------|------|
| `config.py` | 全局配置（Pydantic Settings，从 `.env` 加载） |
| `database.py` | 数据库初始化与会话管理（SQLAlchemy async） |
| `report_template.html` | Jinja2 报告 HTML 模板 |

---

## 四、前端模块（`frontend/`）

前端是一个 React 19 SPA，运行在端口 **5173**（开发模式），构建后通过 Nginx 托管。

### 4.1 页面（`src/pages/`）

| 页面 | 路由 | 职责 |
|------|------|------|
| `Dashboard.tsx` | `/` | 仪表盘首页（扫描统计、风险概览） |
| `NewScan.tsx` | `/scan/new` | 创建新扫描（目标配置、模板选择、参数设置） |
| `ScanProgress.tsx` | `/scan/:taskId` | 扫描实时进度（WebSocket 推送） |
| `ScanResults.tsx` | `/results/:scanId` | 扫描结果详情（findings 列表、人工复核） |
| `Report.tsx` | `/report/:scanId` | 报告页面（可导出 PDF/HTML） |
| `Templates.tsx` | `/templates` | 攻击模板管理 |
| `Adapters.tsx` | `/adapters` | 适配层管理 |
| `JudgeCalibration.tsx` | `/judge-calibration` | Judge 校准实验 |
| `Playground.tsx` | `/playground` | Prompt 试验场 |
| `Compare.tsx` | `/compare` | 多次扫描对比 |
| `Settings.tsx` | `/settings` | 系统设置（模型配置、API Key 等） |
| `About.tsx` | `/about` | 关于页面 |

### 4.2 API 客户端（`src/api/`）

| 文件 | 对接后端模块 |
|------|------------|
| `client.ts` | HTTP 客户端封装（baseURL、错误处理） |
| `scans.ts` | 扫描相关 API |
| `cases.ts` | 攻击用例 API |
| `reports.ts` | 报告 API |
| `stats.ts` | 统计 API |
| `settings.ts` | 设置 API |
| `targets.ts` | 目标 API |
| `adapters.ts` | 适配层 API |
| `modelProviders.ts` | 模型供应商 API |
| `judgeCalibration.ts` | Judge 校准 API |

### 4.3 组件（`src/components/`）

| 目录/文件 | 职责 |
|----------|------|
| `layout/Layout.tsx` | 应用主布局框架 |
| `layout/Sidebar.tsx` | 侧边导航栏 |
| `charts/CategoryBarChart.tsx` | 攻击类别柱状图 |
| `charts/CategoryRadarChart.tsx` | 攻击类别雷达图 |
| `charts/RiskPieChart.tsx` | 风险等级饼图 |
| `charts/ScoreTrendChart.tsx` | 评分趋势折线图 |
| `CompliancePanel.tsx` | 合规框架映射面板 |
| `ProviderIcon.tsx` | 模型供应商图标 |
| `Skeleton.tsx` | 骨架屏加载组件 |
| `Toast.tsx` | 通知提示组件 |

### 4.4 其他模块

| 目录/文件 | 职责 |
|----------|------|
| `hooks/useWebSocket.ts` | WebSocket Hook（扫描实时进度推送） |
| `i18n/` | 国际化（`en.ts` 英文、`zh.ts` 中文） |
| `types/index.ts` | 全局 TypeScript 类型定义 |
| `utils/chartTheme.ts` | 图表主题配置 |
| `utils/csv.ts` | CSV 导出工具 |
| `utils/format.ts` | 格式化工具 |
| `utils/risk.ts` | 风险等级工具 |

---

## 五、模拟靶标（`mock_targets/`）

用于开发调试和演示的真实风格 AI 应用。

### 5.1 FinanceBot（金融客服机器人）

| 属性 | 值 |
|------|------|
| 路径 | `mock_targets/financebot/` |
| 技术栈 | Java 17 + Spring Boot 3.2 + H2 + OkHttp |
| 端口 | 8001 |
| 功能 | 银行账户查询、贷款申请、欺诈举报 |
| Canary Tokens | `CANARY-MBANK-FRAUD-ESCAL-2024`、`CANARY-VIP-MERIDIAN-GOLD-7829`、`CANARY-MBANK-APPROVAL-XK9` |
| 审计端点 | `GET /audit/loans`、`GET /audit/fraud-reports` |
| 攻击面 | LLM 可被操纵以错误 customerId 调用 queryAccount / submitLoanApplication（越权） |

### 5.2 ShopBot（电商客服机器人）

| 属性 | 值 |
|------|------|
| 路径 | `mock_targets/shopbot/` |
| 技术栈 | Node 20 + Express + TypeScript + SQLite |
| 端口 | 8002 |
| 功能 | 订单查询、退款、取消订单、地址修改、优惠券 |
| Canary Tokens | `CANARY-SHOP-VIP-POLICY-ALPHA`、`STAFF-SHOPNOW-OVERRIDE-2024`、`FLASH-SALE-ADMIN-TOKEN-XZ9` |
| 审计端点 | `GET /audit/order-ops`、`GET /audit/coupon-uses` |
| 工具 | `listOrders`、`getOrderDetail`、`requestRefund`、`cancelOrder`、`updateShippingAddress`、`applyCoupon` |

---

## 六、演示模块（`demo/`）

| 文件 | 说明 |
|------|------|
| `demo_scan_configs.json` | 预置扫描配置示例 |
| `demo_prompts/financebot_system_prompt.txt` | FinanceBot 演示用 system prompt |
| `demo_prompts/hr_rag_system_prompt.txt` | HR RAG 演示用 system prompt |
| `README.md` | 演示操作指南 |

---

## 七、文档模块（`docs/`）

### 7.1 设计文档

| 文件 | 说明 |
|------|------|
| `evaluation_protocol.md` | 正式评测协议 |
| `business_integration_implementation_plan.md` | 真实业务接入实施方案（英文） |
| `business_integration_implementation_plan.zh-CN.md` | 真实业务接入实施方案（中文） |
| `phase1_quartet_case_layer_plan.zh-CN.md` | Phase 1：四元对照用例层方案 |
| `phase1_task_breakdown.zh-CN.md` | Phase 1：开发任务分解 |
| `phase2_adapter_mvp_task_breakdown.zh-CN.md` | Phase 2：适配层 MVP 任务分解 |
| `phase3_probe_verification_task_breakdown.zh-CN.md` | Phase 3：Probe 验证层任务分解 |
| `phase4_judge_calibration_loop_task_breakdown.zh-CN.md` | Phase 4：Judge 校准循环任务分解 |
| `research-insights.md` | 学术研究洞察 |

### 7.2 参考论文（`docs/papers/`）

收录 Prompt Injection 相关学术论文（PDF），包含 AutoInject、Crescendo、Guardrail-Bypass 等。

### 7.3 UI 原型（`docs/prototypes/`）

早期 HTML 原型页面，用于 UI 方案探索。

---

## 八、模块依赖关系

```
┌─────────────────────────────────────────────────────┐
│                   frontend (React)                   │
│  Dashboard / NewScan / ScanProgress / ScanResults    │
│  Report / Templates / Adapters / JudgeCalibration    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP + WebSocket
                       ▼
┌─────────────────────────────────────────────────────┐
│                 backend (FastAPI)                     │
│                                                      │
│  ┌─────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ API 路由 │──▶│   服务层     │──▶│  数据模型    │ │
│  │ (api/)   │   │ (services/)  │   │ (models/)    │ │
│  └─────────┘   └──────┬───────┘   └──────────────┘ │
│                       │                              │
│         ┌─────────────┼─────────────┐               │
│         ▼             ▼             ▼               │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐         │
│  │ 攻击引擎   │ │ 裁决引擎 │ │ LLM 客户端│         │
│  │ PAIR/TAP/  │ │ AI分析   │ │ OpenAI/   │         │
│  │ Crescendo  │ │ 规则断言 │ │ Anthropic │         │
│  └─────┬──────┘ └──────────┘ └─────┬─────┘         │
│        │                           │                │
└────────┼───────────────────────────┼────────────────┘
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│  被测目标 API    │        │  LLM 服务商 API  │
│  (mock_targets   │        │  (OpenAI/        │
│   或真实业务)    │        │   DeepSeek/etc.) │
└─────────────────┘        └─────────────────┘
```

---

## 九、关键数据流

1. **创建扫描** → 前端 `NewScan` → `POST /api/v1/scans` → `scan_runner.py` 编排
2. **执行攻击** → `scan_runner` → 选择攻击引擎（PAIR/TAP/Crescendo/…）→ `target_client` 发请求到被测目标
3. **裁决结果** → `verdict_engine` + `ai_analyzer` → 结构化行为判定 → 落库 `AttackResult`
4. **实时推送** → WebSocket → 前端 `ScanProgress` 实时显示
5. **生成报告** → `report_generator` → Jinja2 渲染 HTML → WeasyPrint 转 PDF
6. **Judge 校准** → `judge_sampling` 抽样 → `judge_calibration_runner` 重跑 → `judge_metrics` 计算指标

---

## 十、端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| Backend (FastAPI) | 8000 | 后端 API 服务 |
| Frontend (Vite/Nginx) | 5173 | 前端开发/生产 |
| FinanceBot (Mock) | 8001 | 金融客服靶标 |
| ShopBot (Mock) | 8002 | 电商客服靶标 |
