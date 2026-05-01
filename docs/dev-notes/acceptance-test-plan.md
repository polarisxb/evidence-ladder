# 天鉴 · 衡 — 项目验收审查计划

> 审查日期: 2026-04-13
> 范围: 全模块业务逻辑、安全性、数据一致性、前后端集成
> 已有缺陷修复文档: `defect-fix-plan.md` (2026-03-26)

---

## 〇、已知缺陷修复状态核查

> `defect-fix-plan.md` 中记录了 4 个致命级 + 9 个高危级缺陷，需逐项确认是否已落地。

| ID | 缺陷 | 涉及文件 | 状态 |
|----|------|---------|------|
| C1 | AI 分析器 prompt injection 漏洞 | `ai_analyzer.py:271-278` | ✅ 已修复 — 已改用 XML 标签包裹 |
| C2 | IRIS 引擎泄露攻击目标给目标模型 | `iris_engine.py:142-147` | ✅ 已修复 — explanation_prompt 已移除 Attack Objective |
| C3 | 平台 API Key 泄露给用户指定 URL | `target_client.py` (原 scan_runner) | ✅ 已修复 — 已拆分到 target_client 并增加 `is_platform_openai_target()` 校验 |
| C4 | API Key 通过错误信息泄露到数据库 | `target_client.py` | ✅ 已修复 — `sanitize_error()` 已实现 |
| H1 | 四引擎成功阈值虚高导致误报 | tap/pair/iris/crescendo | ✅ 已修复 — 回退阈值已对齐主阈值 (8.0/70) |
| H2 | `except Exception` 吞错误返回"安全" | `ai_analyzer.py:349` | ⚠️ 待验证 — 需确认 except 是否已拆分 |
| H3 | 速率限制耗尽静默返回"安全" | `ai_analyzer.py:365-377` | ✅ 已修复 — 改为 raise RuntimeError |
| H4 | PAIR/Crescendo/IRIS 无 LLM 超时 | 三个引擎文件 | ⚠️ 待验证 — Crescendo 已有 asyncio.wait_for，需检查 PAIR/IRIS |
| H5 | 多轮攻击模板当单轮执行 | `scan_runner.py` | ✅ 已修复 — `_run_multiturn_base_case()` 已实现 |
| H6 | TAP 查询预算过低 (8→30) | `tap_engine.py:31` | ✅ 已修复 — `TAP_MAX_TOTAL_QUERIES = 30` |
| H7 | CVSS × confidence 非标准评分 | `risk_scorer.py:76-78` | ✅ 已修复 — 不再乘以 confidence |
| H8 | 严重性比率被失败攻击稀释 | `risk_scorer.py:107-108` | ✅ 已修复 — 分母改为 `max(successful_attacks, 1)` |
| H9 | 空响应被错误分类为"拒绝" | `ai_analyzer.py:155-156` | ✅ 已修复 — 空响应返回 False |

### 验证操作

```
# H2: 检查 ai_analyzer.py 中 except 是否正确拆分
搜索 "except (json.JSONDecodeError, Exception)" 确认已消除

# H4: 检查 PAIR 和 IRIS 是否有 asyncio.wait_for
grep -n "wait_for" pair_engine.py iris_engine.py
```

---

## 一、攻击引擎模块

### 1.1 攻击模板完整性

**文件**: `backend/app/attack_templates/*.json` (7 个)

| 检查项 | 验证方法 | 严重度 |
|--------|---------|--------|
| 每个 JSON 模板格式合法 | `python -c "import json,glob; [json.load(open(f)) for f in glob.glob('*.json')]"` | 高 |
| 每个模板有 id / name / category / technique / payloads 字段 | 脚本遍历检查 | 高 |
| 多轮模板标记 `multi_turn: true` 且 payloads 有序 | 手动检查 `jailbreak.json` 中 JB-003 | 中 |
| 模板 id 全局唯一 | 脚本检查 | 高 |
| payloads 内容非空且无占位符遗留 | grep "TODO\|FIXME\|PLACEHOLDER" | 低 |

### 1.2 高级攻击引擎正确性

**TAP** (`tap_engine.py`)
- [ ] `TAP_MAX_TOTAL_QUERIES = 30` 已确认
- [ ] 所有 LLM 调用有 `asyncio.wait_for` 超时
- [ ] 回退阈值 ≥ 8.0
- [ ] branching/pruning 逻辑：off-topic 剪枝正确（score < 3 的分支被裁剪）
- [ ] `result.stop_reason` 在各退出路径都被正确设置

**PAIR** (`pair_engine.py`)
- [ ] 回退阈值 ≥ 8.0 — ✅ line 144
- [ ] LLM 调用是否有超时保护
- [ ] `_refine_prompt` 的 conversation history 不会无限增长（检查是否截断）
- [ ] judge score 为 1-10 范围，解析出非数字时的降级处理

**Crescendo** (`crescendo_engine.py`)
- [ ] 回退阈值 ≥ 70 — ✅ line 280
- [ ] `attacker_history` 长度限制 — ✅ `_MAX_HISTORY = 13`
- [ ] LLM 调用有超时保护 — ✅ `asyncio.wait_for`
- [ ] `conversation_history` 传递给 `send_fn` 时累积正确

**IRIS** (`iris_engine.py`)
- [ ] 回退阈值 ≥ 8.0 — ✅ line 161
- [ ] `explanation_prompt` 不含 Attack Objective — ✅ line 137-140
- [ ] `_rewrite_with_explanation` 有超时保护 — ✅ `asyncio.wait_for` line 175
- [ ] self-explanation 响应截断合理 (`[:1200]`)

**FITD** (`fitd_engine.py`)
- [ ] 引擎完整性——是否有超时、停止检查、回退阈值
- [ ] 多级升级逻辑是否正确递进

**MSJ** (`msj_engine.py`)
- [ ] few-shot 消息拼装正确性——不能超出 LLM 上下文窗口
- [ ] 停止检查是否存在

**ICE** (`ice_engine.py`)
- [ ] 引擎基本流程是否完整

**Mutation** (`mutation_engine.py`)
- [ ] 变体生成策略（重写/替换/编码等）是否产出有效 payload
- [ ] 变体数量限制（scan_runner 中 `[:3]`）是否合理

### 1.3 对照变体模块

**文件**: `control_variants.py`

- [ ] `build_control_variant_prompts()` 对所有 7 个 category 都有 clean/quoted_attack/benign_distractor 模板
- [ ] Jaccard similarity 阈值 `_CONTROL_SIMILARITY_THRESHOLD = 0.72` 是否经过校准
- [ ] `_REFUSAL_MARKERS` 多语言覆盖是否充分
- [ ] `summarize_control_comparison()` 返回结构与 case_serializer 期望一致

---

## 二、扫描与执行模块

### 2.1 扫描主循环 (`scan_runner.py`, ~1117 行)

| 检查项 | 位置 | 严重度 |
|--------|------|--------|
| `total_attacks` 计算是否包含 base + advanced + mutations | L371-392 | 高 |
| advanced_attack_total 用 `min(5, templates_with_payload)` 合理性——如果模板无 payload 会怎样 | L373-391 | 中 |
| `_persist_and_count` 使用独立 session + 原子计数器 | L117-157 | 高 |
| 全局扫描超时 `MAX_SCAN_DURATION_S = 3600` 是否在所有路径生效 | L44 + L400 | 高 |
| `_check_should_stop_isolated` 的 DB 轮询间隔 5s 是否合理 | L160-183 | 低 |
| base_sem / chain_sem 并发控制——确保不会饿死任一类型 | L417-418 | 中 |
| 所有 `asyncio.gather(..., return_exceptions=True)` 后都检查了异常 | L489-492 | 中 |
| 扫描完成时 refresh task 再更新状态——避免覆盖并发写入 | L502-508 | 高 |

### 2.2 目标通信 (`target_client.py`)

- [ ] `builtin_vulnerable`: conversation_history 正确透传
- [ ] `openai_compatible`: API key 安全策略已验证（C3 修复）
- [ ] `claude`: 单独的 ProviderClientInfo 构建是否正确
- [ ] `adapter/custom`: `__resolved_adapter` 注入到 config 的时机
- [ ] 兜底 `httpx.AsyncClient`: timeout 30s、MAX_RESPONSE_BYTES 1MB 限制
- [ ] `sanitize_error()` 覆盖所有错误返回路径
- [ ] `send_to_target_with_result()` 对 adapter 和非 adapter 路径都返回 `(text, session_id)`

### 2.3 Case 执行 (`case_executor.py`)

- [ ] `_prepare_case_attempt` 流程: 攻击→分析→评分→裁决→对照变体→probe
- [ ] `_ADAPTIVE_CONTROL_SKIP_CONFIDENCE = 0.85` — adaptive quartet_mode 跳过条件
- [ ] `OBJECTIVE_BY_CATEGORY` 覆盖全部 7 个攻击类别
- [ ] 当 probe 返回 inconclusive 时 business_verification_status 设置是否正确
- [ ] case_attempt dict 结构是否与 case_persistence 期望一致

### 2.4 Case 持久化 (`case_persistence.py` + `case_serializer.py`)

- [ ] `persist_case_with_legacy_result` 同时写入 AttackCase + AttackResult
- [ ] 序列化器正确映射 AnalysisResult → AttackResult 所有字段
- [ ] JSON 字段 (`analysis_raw`, `probe_summary`, `judge_snapshot`) 存储完整且可反序列化

---

## 三、裁决与评估模块

### 3.1 AI 分析器 (`ai_analyzer.py`)

| 检查项 | 位置 | 严重度 |
|--------|------|--------|
| XML 标签隔离（C1 修复）是否对所有调用路径生效 | L271-278 | 致命 |
| `_looks_like_clear_refusal` 快速路径准确性 | L145-151 | 高 |
| `SUSPICIOUS_SUCCESS_MARKERS` 是否把可疑响应排除出快速拒绝路径 | 检查列表 | 中 |
| 二次评估触发条件合理性 | L289-296 | 中 |
| `_merge_evaluations` 合并逻辑——两次结果冲突时如何处理 | 查找函数 | 高 |
| `_single_llm_evaluation` JSON 解析失败时的降级处理 | L346+ | 高 |
| `_normalize_score` / `_normalize_bool` 边界值处理 | 查找函数 | 中 |
| `ANALYSIS_SYSTEM_PROMPT` 中的 Anti-Manipulation Rule 是否存在 | 检查行 ~54 | 致命 |

### 3.2 裁决引擎 (`verdict_engine.py`)

- [ ] canary token 匹配 → `rule_verified` — ✅ 逻辑正确
- [ ] system prompt overlap 检测——`_find_prompt_overlap` window=10 词的滑动窗口
- [ ] `_is_distinctive_phrase` 排除了通用词——但有些 7 字母以上的通用词可能遗漏
- [ ] FULL_INJECTION_SUCCESS + confidence < 0.80 → manual_review 而非 ai_suspected
- [ ] 所有路径返回的 dict 结构一致 (verdict_status, verdict_reason, rule_hits)

### 3.3 Canary 检测 (`canary_utils.py`)

- [ ] `collect_canary_tokens` 从 target_config 正确提取
- [ ] `find_canary_matches` 大小写不敏感匹配
- [ ] 部分匹配 vs 完全匹配的策略

### 3.4 风险评分 (`risk_scorer.py`)

- [ ] `compute_risk_score`: 成功攻击返回 CVSS 原始分，失败返回 0 — ✅
- [ ] `compute_posture_metrics`: severity_ratio 分母正确 — ✅
- [ ] `security_posture_score` 公式: `100 * (1 - 0.5*ASR - 0.5*severity_ratio)` 合理性
- [ ] `compute_overall_score` 和 `classify_overall_risk` 的输入输出一致性

### 3.5 Probe 执行 (`probe_executor.py` + `probe_assertions.py`)

- [ ] probe 流程: 解析 config → 执行 HTTP 请求 → 提取响应 → 断言验证
- [ ] probe 断言类型覆盖: contains / not_contains / json_path_equals / status_code 等
- [ ] 当 adapter 未配置 probe_config 时的降级行为
- [ ] probe 超时和错误处理

### 3.6 Judge 校准 (`judge_calibration_runner.py` + `judge_metrics.py` + `judge_sampling.py`)

- [ ] 校准运行器是否正确保存 judge_snapshot
- [ ] Cohen's Kappa / accuracy 等指标计算正确性
- [ ] 采样策略是否保证了代表性

---

## 四、适配器模块

### 4.1 适配器执行器 (`adapter_executor.py`)

- [ ] HTTP 请求构建：headers / body template 渲染正确
- [ ] `_resolve_secret_ref` 从环境变量读取秘密——是否有 fallback 和错误提示
- [ ] session 管理: `per_variant_isolated` / `shared` 模式正确实现
- [ ] 响应提取: `extract_adapter_response()` 支持 raw_text / json_path / regex 模式
- [ ] MAX_ADAPTER_RESPONSE_BYTES 1MB 限制是否生效

### 4.2 适配器 API (`api/adapters.py`)

- [ ] CRUD 完整性：创建/读取/更新/删除/列表
- [ ] 适配器 enable/disable 状态切换
- [ ] 适配器 test 端点是否存在且功能正常
- [ ] adapter_id 关联到 scan_task 的外键一致性

### 4.3 适配器对接 Mock 靶标兼容性

- [ ] FinanceBot (port 8001): POST /chat 接口格式与 adapter body_template 匹配
- [ ] ShopBot (port 8002): POST /chat 接口格式匹配
- [ ] 对 canary token 的 end-to-end 检测能力

---

## 五、报告与数据模块

### 5.1 报告生成 (`report_generator.py`)

- [ ] `generate_report` 输出的 report_data 结构完整（包含 findings, posture, categories, trend）
- [ ] HTML 报告 (`render_html_report`) 渲染无异常
- [ ] 报告中的漏洞计数与数据库一致

### 5.2 报告 API (`api/reports.py`)

- [ ] 获取单个 scan 的所有 findings
- [ ] 人工复核 (manual_verified / false_positive / reset) 功能
- [ ] HTML/PDF 报告下载
- [ ] `_resolved_target_response` 正确回退到高级引擎的 turn details
- [ ] `_resolved_verdict_status` 在无 verdict_status 时的默认值

### 5.3 数据模型一致性

| 模型 | 检查项 |
|------|--------|
| `ScanTask` | status 枚举覆盖所有转换：pending→running→completed/failed/cancelled |
| `AttackResult` | risk_score 是否与 risk_scorer 输出一致 |
| `AttackCase` | variants 关联的级联删除 |
| `Adapter` | ondelete="SET NULL" — 删除适配器不删除扫描 |
| `JudgeCalibrationRun` / `JudgeCalibrationSample` | 与 judge_metrics 输入匹配 |

### 5.4 数据库迁移 (`database.py`)

- [ ] `_ensure_additive_*` 函数只做 ADD COLUMN，不会破坏已有数据
- [ ] 新列有合理默认值或允许 NULL
- [ ] 并发 init_db 是否安全（多 worker 启动）

### 5.5 统计 API (`api/stats.py`)

- [ ] overview 指标计算是否与 risk_scorer 一致
- [ ] score-trend 排序和分页
- [ ] 按 category / technique 分组的统计
- [ ] 框架映射 (OWASP / MITRE) 正确性

---

## 六、前端模块

### 6.1 API 客户端 (`frontend/src/api/client.ts`)

- [ ] `normalizeApiBase` 对各种 VITE_API_URL 格式的处理（空、有路径、无路径）
- [ ] API Key 通过 `X-API-Key` header 传递
- [ ] 401 响应时发出 `app-api-auth-required` 事件
- [ ] `download()` 的文件名解析

### 6.2 页面功能

| 页面 | 核心检查 |
|------|---------|
| `Dashboard.tsx` | 统计数据加载、图表渲染、空状态处理 |
| `NewScan.tsx` (43KB) | 所有 target_type 的表单切换、advanced config 联动、adapter 选择、验证提示 |
| `ScanProgress.tsx` | WebSocket 连接、实时进度条、暂停/取消操作 |
| `ScanResults.tsx` (42KB) | 结果列表加载、筛选/排序、人工复核交互、verdict 展示 |
| `Report.tsx` (41KB) | 报告加载、findings 展示、HTML 下载、posture score 可视化 |
| `Settings.tsx` (33KB) | Model Provider CRUD、全局设置持久化 |
| `Adapters.tsx` | 适配器 CRUD、测试、probe 配置 |
| `JudgeCalibration.tsx` | 校准运行、指标展示、版本对比 |
| `Compare.tsx` | 多 scan 对比 |
| `Playground.tsx` | 单次攻击测试 |
| `Templates.tsx` | 模板浏览 |

### 6.3 前端通用问题

- [ ] 所有 API 调用的 loading / error / empty 三态处理
- [ ] WebSocket 断线重连
- [ ] i18n 完整性（`frontend/src/i18n/`）
- [ ] URL 路由与后端 API 路径一致性
- [ ] CORS 配置：后端只允许 `http://localhost:5173`

---

## 七、安全审查

### 7.1 API 安全

- [ ] `AuthMiddleware` 对 WebSocket 路由 `/api/v1/scans/ws/*` 是否生效
  - **潜在问题**: WebSocket 走的 `websocket.accept()` 不经过 HTTP 中间件拦截
- [ ] `batch-delete` 无速率限制——可批量删除所有扫描
- [ ] query 参数 `q` 使用 `.ilike(pattern)` — SQLAlchemy 已参数化，但 `%` 注入可能导致性能问题
- [ ] `app_secret` 空时全局免认证——生产部署必须设置
- [ ] `api_key` 字段存储在 `target_config` JSON 中（数据库明文）

### 7.2 资源安全

- [ ] `MAX_SCAN_DURATION_S = 3600` — 单扫描最多 1 小时
- [ ] `_MAX_CONCURRENT_CHAINS = 8` — 并发链数上限
- [ ] `MAX_RESPONSE_BYTES = 1MB` — 响应大小限制
- [ ] `analyzer_concurrency = 12` — 分析器并发上限
- [ ] 无全局请求速率限制中间件

### 7.3 数据安全

- [ ] SQLite 文件权限
- [ ] 日志中是否可能泄露 API key（检查 `logger.debug` / `logger.info` 的参数）
- [ ] `analysis_raw` JSON 字段是否存储了完整的攻击 payload（可能很大）

---

## 八、Mock 靶标模块

### 8.1 FinanceBot (Java 17 + Spring Boot)

- [ ] 启动正常: `mvn spring-boot:run` (需要 OPENAI_API_KEY)
- [ ] POST /chat 接口响应格式
- [ ] 3 个 canary token 在 system prompt 中
- [ ] audit 端点 `/audit/loans`, `/audit/fraud-reports` 可访问

### 8.2 ShopBot (Node 20 + Express + TypeScript)

- [ ] 启动正常: `npm run dev`
- [ ] POST /chat 接口响应格式
- [ ] 3 个 canary token
- [ ] audit 端点 `/audit/order-ops`, `/audit/coupon-uses` 可访问
- [ ] SQLite 数据初始化正确（3 用户、订单数据）

---

## 九、集成测试

### 9.1 现有测试覆盖

| 测试文件 | 覆盖范围 |
|---------|---------|
| `test_phase1_regression.py` (17KB) | Phase 1 quartet case layer |
| `test_phase2_adapter_regression.py` (15KB) | Phase 2 adapter MVP |
| `test_phase3_probe_regression.py` (21KB) | Phase 3 probe verification |

- [ ] 所有测试可通过: `pytest backend/app/tests/ -v`
- [ ] 测试是否 mock 了 LLM 调用（不依赖真实 API key）
- [ ] 测试覆盖率评估

### 9.2 端到端测试场景

| 场景 | 步骤 | 期望结果 |
|------|------|---------|
| **E2E-1: builtin_vulnerable 全链路** | 创建扫描 → target_type=builtin_vulnerable → 等待完成 → 查看报告 | 扫描完成，发现若干漏洞，报告可下载 |
| **E2E-2: Mock 靶标连接** | 启动 ShopBot → 创建 adapter → 创建扫描 → target_type=adapter | 扫描执行，canary token 被检测到 |
| **E2E-3: 暂停/恢复** | 创建大扫描 → 暂停 → 检查报告是否基于已有结果生成 | 报告包含部分结果 |
| **E2E-4: 取消** | 创建扫描 → 取消 → 确认状态为 cancelled | 进行中的攻击优雅终止 |
| **E2E-5: 重试** | 完成/失败的扫描 → 重试 → 确认新扫描创建 | 新任务复制原始配置 |
| **E2E-6: 人工复核** | 对某结果标记 false_positive → 刷新确认持久化 | verdict 更新成功 |
| **E2E-7: 高级引擎** | 启用 PAIR + TAP → 确认引擎实际执行 | 结果包含 PAIR/TAP 前缀的 template_id |
| **E2E-8: 适配器 probe** | 配置 adapter + probe_config → 执行扫描 | business_verification_status 非 not_applicable |

---

## 十、执行计划

### Phase A: 静态审查 (预计 2-3 小时)

1. **缺陷修复核查** — 逐项确认 `defect-fix-plan.md` 中 C1-C4, H1-H9 的代码落地情况
2. **攻击模板合法性** — 脚本检查 7 个 JSON 文件
3. **代码审查** — 重点检查以下高风险区域:
   - `ai_analyzer.py` — ANALYSIS_SYSTEM_PROMPT 和异常处理
   - `scan_runner.py` — 并发控制和计数器原子性
   - `target_client.py` — API key 安全
   - `verdict_engine.py` — 裁决逻辑完整性
   - `auth.py` — WebSocket 认证缺口

### Phase B: 单元测试 (预计 1-2 小时)

4. **运行现有测试** — `pytest backend/app/tests/ -v`
5. **补充关键缺失测试**:
   - `ai_analyzer` XML 标签隔离
   - `sanitize_error` 脱敏有效性
   - `risk_scorer` 边界条件
   - `verdict_engine` 各判定路径

### Phase C: 集成测试 (预计 2-3 小时)

6. **后端启动** — `uvicorn app.main:app --reload --port 8000`
7. **前端启动** — `npm run dev`
8. **执行 E2E-1 到 E2E-8**
9. **Mock 靶标验证** — 分别启动 FinanceBot 和 ShopBot，确认可通过适配器连接

### Phase D: 安全审查 (预计 1 小时)

10. **WebSocket 认证** — 测试无 API key 是否可连接 WS
11. **API key 明文存储** — 评估风险
12. **批量操作** — 测试 batch-delete 边界
13. **日志脱敏** — 检查运行日志

### Phase E: 总结报告

14. 汇总所有发现
15. 按严重度分类: Critical / High / Medium / Low
16. 给出修复建议和优先级

---

## 附: 快速启动命令

```powershell
# 后端
cd c:\all_project\ai-security\backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd c:\all_project\ai-security\frontend
npm install
npm run dev

# 测试
cd c:\all_project\ai-security\backend
pytest app/tests/ -v

# Mock 靶标
cd c:\all_project\ai-security\mock_targets\shopbot
npm run dev

cd c:\all_project\ai-security\mock_targets\financebot
set OPENAI_API_KEY=your-key
mvn spring-boot:run
```
