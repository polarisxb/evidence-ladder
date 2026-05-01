# Provenance 协议设计文档

> **天鉴 · 衡 / TianJian Libra — 响应来源 Provenance 确定化方案**
>
> 状态：设计定稿 · 待实现
> 创建时间：2026-04-21

---

## 1. 问题定义

### 1.1 现状

当前 `response_screening.py` 的 `ResponseEvaluation` 只有一个 `response_origin` 字段，取值为：

| response_origin  | 含义                                 |
|------------------|--------------------------------------|
| `model`          | 响应由 LLM 直接生成                 |
| `app_fallback`   | 响应来自已知非模型回退模板           |
| `transport_error`| 传输层错误                           |
| `adapter_error`  | 适配器层错误                         |
| `gateway_error`  | 网关/HTML 错误页                     |
| **`unknown`**    | **无法判断来源**                     |

对 `custom` / `adapter` 类 target（FinanceBot、ShopBot 等应用层 HTTP 端点），只要响应是
HTTP 200 + 非空 + 不命中已知 fallback，就会落入 `unknown`。实际上这些响应绝大多数是模型
真实输出，但当前系统无法确认。

### 1.2 核心矛盾

**纯黑盒下无法 100% 区分**：

- 🛡 应用层守卫前置拦截（模型根本没被调用）
- 🧠 模型自主拒答（模型被调用了，但主动拒绝）
- ✏ 模型响应被应用层后处理改写

三者表层 HTTP 特征可以完全一致（均为 HTTP 200 + 合理文本）。

### 1.3 目标

报告页面从单一的 `Unknown` 变为明确的两问两答：

> **问 1：攻击请求打到模型了没？** → ✅ 是 / ❌ 否 / ❓ 不确定
> **问 2：模型响应被应用层改过没？** → ✅ 原样 / ✏ 改过 / ❓ 不确定

---

## 2. 两维数据模型

### 2.1 新增字段（`ResponseEvaluation` schema 扩展）

在 `response_screening.py::ResponseEvaluation` 和前端 `types/index.ts::ResponseEvaluation`
中新增以下字段：

```python
# 后端 Pydantic schema
class ResponseEvaluation(BaseModel):
    # ---- 现有字段（保留，向后兼容）----
    response_origin: ResponseOrigin = "unknown"         # 旧枚举，由新字段派生
    origin_confidence: OriginConfidence = "low"
    evaluation_validity: EvaluationValidity = "evaluable"
    invalid_reason: str | None = None
    matched_signature: str | None = None
    transport_ok: bool = True
    http_status: int | None = None
    content_type: str | None = None
    evidence_codes: list[str] = Field(default_factory=list)
    baseline_probe: dict | None = None

    # ---- 新增字段（两维 Provenance）----
    model_invoked: bool | None = None          # True=模型被调用 / False=未调用 / None=不确定
    post_processed: bool | None = None         # True=被改写 / False=原样 / None=不确定
    block_reason: str | None = None            # model_invoked=False 时的阻断原因
    post_reason: str | None = None             # post_processed=True 时的改写原因
    provenance_source: str | None = None       # 判定依据来源
```

### 2.2 `block_reason` 枚举值

当 `model_invoked=False` 时由 target 声明或由规则推断：

| block_reason         | 含义                                        |
|----------------------|---------------------------------------------|
| `pre_guardrail`      | 前置安全网关 / WAF 拦截                     |
| `input_validation`   | 输入参数校验不通过（Bean Validation 等）     |
| `auth_denied`        | 认证/鉴权失败                               |
| `rate_limit`         | 限流 / 配额耗尽                             |
| `tool_only_route`    | 纯规则/FAQ 路由，不走 LLM                   |

### 2.3 `post_reason` 枚举值

当 `post_processed=True` 时由 target 声明：

| post_reason          | 含义                                        |
|----------------------|---------------------------------------------|
| `pii_redaction`      | PII 脱敏（如卡号打码）                      |
| `policy_filter`      | 内容策略过滤（删/替换违规词）               |
| `format_enforcement` | 模型输出格式不符被强制修正                  |
| `tool_rewrite`       | 工具调用结果覆盖了模型原文                  |

### 2.4 `provenance_source` 枚举值

标记本次判定的信息来源：

| provenance_source         | 含义                                  | 可信度  |
|---------------------------|---------------------------------------|---------|
| `target_header`           | 目标系统返回了 X-Provenance-* header  | high    |
| `target_body`             | 目标系统响应体里有 `_provenance` 字段 | high    |
| `origin_rule`             | 命中了用户配置的 origin_rules         | high    |
| `known_fallback`          | 命中了内置已知回退签名库              | high    |
| `heuristic`               | 启发式推断（错误标记/空响应/HTML 等） | medium  |
| `target_type_default`     | 根据 target_type 默认值              | low     |
| `none`                    | 无任何信号，两维均为 None             | none    |

### 2.5 向后兼容：旧字段派生规则

旧 `response_origin` 由新字段自动映射，确保所有已有测试 / API / 报告模板不受影响：

```python
def _derive_response_origin(
    model_invoked: bool | None,
    post_processed: bool | None,
    block_reason: str | None,
    current_origin: ResponseOrigin,  # 来自启发式/传输层的判定
) -> ResponseOrigin:
    """从两维 Provenance 派生旧 response_origin 枚举。"""
    # 传输层/网关层错误优先（这些不受 Provenance 协议控制）
    if current_origin in ("transport_error", "adapter_error", "gateway_error"):
        return current_origin
    # 明确未调用模型 → app_fallback
    if model_invoked is False:
        return "app_fallback"
    # 明确调用了模型 + 未被改写 → model
    if model_invoked is True and not post_processed:
        return "model"
    # 明确调用了模型 + 被改写 → app_fallback（应用层后处理）
    if model_invoked is True and post_processed is True:
        return "app_fallback"
    # 两个都不确定 → 保持原值（通常是 unknown）
    return current_origin
```

---

## 3. 信号采集：四级渐进兑现

优先级从高到低，命中即止：

```
Level 1 ── 目标系统 Provenance 协议（Header 或 Body）
       │     → 100% 确定性
       │     → provenance_source = target_header | target_body
       ▼
Level 2 ── 用户配置的 origin_rules（含新增 JSON path 结构化规则）
       │     → 按规则命中程度确定
       │     → provenance_source = origin_rule
       ▼
Level 3 ── 内置启发式推断（known_fallback / transport / HTML / empty）
       │     → medium 确定性
       │     → provenance_source = known_fallback | heuristic
       ▼
Level 4 ── 默认值（target_type_default 或 none）
             → 对 builtin_vulnerable/claude/openai_compatible → model_invoked=True
             → 对 custom/adapter → model_invoked=None（不确定）
             → provenance_source = target_type_default | none
```

---

## 4. Level 1 实现：Provenance 协议

### 4.1 传输方式

**推荐使用 HTTP Response Header**。原因：

1. 不改变响应 Body 结构，AI 裁判读到的 `response_text` 保持干净
2. 兼容 `text/plain` 和 `application/json` 任意 Content-Type
3. Header 采集在 adapter_executor 已有先例（`content-type` / `status_code`）

**Header 名称定义**：

| Header                        | 类型   | 示例值            |
|-------------------------------|--------|--------------------|
| `X-Provenance-Model-Invoked`  | bool   | `true` / `false`   |
| `X-Provenance-Post-Processed` | bool   | `true` / `false`   |
| `X-Provenance-Block-Reason`   | string | `input_validation`  |
| `X-Provenance-Post-Reason`    | string | `pii_redaction`     |

**备选方式**（Body 字段，适用于 JSON 响应）：

```json
{
  "response": "...",
  "_provenance": {
    "model_invoked": true,
    "post_processed": false,
    "block_reason": null,
    "post_reason": null
  }
}
```

screening 同时支持两种采集方式，Header 优先于 Body。

### 4.2 后端采集：adapter_executor / target_client 改动

#### 4.2.1 adapter_executor.py

在 `execute_adapter_request` 中，已有读取 `invoke_response.headers.get("content-type")`
的先例。新增采集 `X-Provenance-*` 系列 header，写入返回字典的 `transport_meta`：

```python
# adapter_executor.py — invoke 成功后
provenance_headers = {
    "model_invoked": _parse_bool_header(invoke_response.headers.get("x-provenance-model-invoked")),
    "post_processed": _parse_bool_header(invoke_response.headers.get("x-provenance-post-processed")),
    "block_reason": invoke_response.headers.get("x-provenance-block-reason"),
    "post_reason": invoke_response.headers.get("x-provenance-post-reason"),
}
# 只保留非 None 的键
provenance_headers = {k: v for k, v in provenance_headers.items() if v is not None}

transport_meta["provenance_headers"] = provenance_headers if provenance_headers else None
```

#### 4.2.2 target_client.py — invoke_target_with_envelope

`invoke_target_with_envelope` 负责为 `custom`/`adapter` 类 target 构建
`TargetResponseEnvelope`。目前它把 `transport_meta` 直接从 adapter result 传入。
无需额外改动——只要 adapter_executor 把 `provenance_headers` 放进 `transport_meta`，
envelope 就自然携带了。

### 4.3 response_screening.py — 读取 Provenance 信号

`screen_response_origin` 函数在现有启发式检查**之前**，优先从 envelope 读取
Provenance 信号：

```python
def screen_response_origin(
    envelope: TargetResponseEnvelope,
    *,
    origin_rules: Mapping[str, Any] | None = None,
) -> ResponseEvaluation:
    # ---- Level 1: Provenance Header / Body ----
    provenance = _extract_provenance(envelope)
    if provenance is not None:
        return _build_from_provenance(envelope, provenance)

    # ---- Level 2: origin_rules ----
    # （现有逻辑 + JSON path 扩展，见下文）

    # ---- Level 3: 启发式（现有逻辑不变）----
    # known_fallback → transport_error → http_error → ...

    # ---- Level 4: 默认值（现有 _default_origin）----
```

`_extract_provenance` 同时尝试：

1. `envelope.transport_meta.get("provenance_headers")` — 来自 response header
2. 响应体 JSON 解析后的 `_provenance` 字段 — 来自 response body

---

## 5. Level 2 扩展：结构化 origin_rules

### 5.1 现有 origin_rules 结构

```json
{
  "origin_rules": {
    "exact": ["..."],
    "contains": ["..."],
    "regex": ["..."]
  }
}
```

现有规则只做**响应文本**匹配，且命中一律标记为 `app_fallback` + `not_evaluable`。

### 5.2 扩展结构：新增 `structured` 规则

在 `TargetOriginRules` schema 中新增 `structured` 字段：

```python
class StructuredOriginRule(BaseModel):
    """基于响应结构字段的来源规则。"""
    field: str                      # JSON path 或 header 名，如 "$.filtered" / "header:x-blocked"
    op: str = "eq"                  # 操作符：eq / ne / exists / not_exists / contains
    value: Any = True               # 比较值
    mark: str = "blocked"           # 命中后标记：blocked / model / post_processed
    reason: str | None = None       # block_reason 或 post_reason
    label: str | None = None        # 人类可读描述

class TargetOriginRules(BaseModel):
    exact: list[str] = Field(default_factory=list)
    contains: list[str] = Field(default_factory=list)
    regex: list[str] = Field(default_factory=list)
    structured: list[StructuredOriginRule] = Field(default_factory=list)
```

示例配置：

```json
{
  "origin_rules": {
    "structured": [
      {
        "field": "$.guardrail.action",
        "op": "eq",
        "value": "INTERVENED",
        "mark": "blocked",
        "reason": "pre_guardrail",
        "label": "AWS Bedrock Guardrail 拦截"
      },
      {
        "field": "$.moderation.filtered",
        "op": "eq",
        "value": true,
        "mark": "post_processed",
        "reason": "policy_filter",
        "label": "内容策略过滤"
      },
      {
        "field": "$.meta.llm_model",
        "op": "exists",
        "mark": "model",
        "label": "LLM 模型字段存在 → 确认为模型响应"
      }
    ]
  }
}
```

### 5.3 JSON path 求值

不引入 `jsonpath-ng` 等重量级依赖。自行实现简化版 `$.` 路径求值器，支持：

- `$.a.b.c` — 嵌套字段访问
- `header:X-Some-Header` — 读取 `transport_meta.provenance_headers` 或 `transport_meta`
- 操作符：`eq` / `ne` / `exists` / `not_exists` / `contains`

这个求值器约 40~60 行 Python。

---

## 6. Mock Target 改造

### 6.1 FinanceBot (Java / Spring Boot)

**ChatController.java** — 响应加 Header：

```java
@PostMapping(value = "/chat", produces = MediaType.TEXT_PLAIN_VALUE)
public ResponseEntity<String> chat(@Valid @RequestBody ChatRequest request) {
    String userId = (request.userId() != null && !request.userId().isBlank())
            ? request.userId() : "USR001";
    ChatResult result = chatService.chat(userId, request.message(), request.history());
    HttpHeaders headers = new HttpHeaders();
    headers.set("X-Provenance-Model-Invoked", String.valueOf(result.modelInvoked()));
    headers.set("X-Provenance-Post-Processed", String.valueOf(result.postProcessed()));
    if (result.blockReason() != null) {
        headers.set("X-Provenance-Block-Reason", result.blockReason());
    }
    if (result.postReason() != null) {
        headers.set("X-Provenance-Post-Reason", result.postReason());
    }
    return ResponseEntity.ok().headers(headers).body(result.response());
}

public record ChatResult(
    String response,
    boolean modelInvoked,
    boolean postProcessed,
    String blockReason,
    String postReason
) {}
```

**ChatService.java** — 改 `chat()` 返回 `ChatResult`：

| 情况                              | model_invoked | post_processed | block_reason        |
|-----------------------------------|:------------:|:--------------:|---------------------|
| 正常模型回答（line 134: `return content`） | `true`  | `false`         | —                   |
| 模型空响应兜底（line 132）          | `true`  | `true`          | — / post_reason=`format_enforcement` |
| 工具轮次用尽兜底（line 138）        | `true`  | `true`          | — / post_reason=`tool_rewrite`       |
| 异常兜底 "technical difficulties"（line 142）| `false` | `false` | 根据异常类型推断    |

**GlobalExceptionHandler.java** — 验证失败时也加 Header：

```java
@ExceptionHandler(MethodArgumentNotValidException.class)
public ResponseEntity<Map<String, Object>> handleValidation(...) {
    return ResponseEntity.badRequest()
        .header("X-Provenance-Model-Invoked", "false")
        .header("X-Provenance-Block-Reason", "input_validation")
        .body(Map.of("error", "Validation failed", "details", errors));
}
```

### 6.2 ShopBot (Node / Express)

**chatRoute.ts** — 响应加 Header：

```typescript
router.post('/', chatValidation, async (req, res) => {
  // ... validation ...
  const result = await chat(userId, message, history);
  res.set('X-Provenance-Model-Invoked', String(result.modelInvoked));
  res.set('X-Provenance-Post-Processed', String(result.postProcessed));
  if (result.blockReason) res.set('X-Provenance-Block-Reason', result.blockReason);
  if (result.postReason) res.set('X-Provenance-Post-Reason', result.postReason);
  res.type('text/plain').send(result.response);
});
```

**chatService.ts** — `chat()` 返回结构化对象，分支逻辑同 FinanceBot。

### 6.3 BuiltinVulnerable（内置）

target_type = `builtin_vulnerable` 直连模型，已通过 `_default_origin` 默认为
`model_invoked=True`（Level 4），无需改动。

---

## 7. 前端改造

### 7.1 TypeScript 类型扩展

`types/index.ts::ResponseEvaluation` 新增：

```typescript
export interface ResponseEvaluation {
  // ---- 现有字段（保留）----
  response_origin?: string | null;
  origin_confidence?: string | null;
  evaluation_validity?: string | null;
  invalid_reason?: string | null;
  matched_signature?: string | null;
  transport_ok?: boolean | null;
  http_status?: number | null;
  content_type?: string | null;
  evidence_codes?: string[];
  baseline_probe?: BaselineProbeResult | null;

  // ---- 新增字段 ----
  model_invoked?: boolean | null;
  post_processed?: boolean | null;
  block_reason?: string | null;
  post_reason?: string | null;
  provenance_source?: string | null;
}
```

### 7.2 ResponseEvaluationPanel 重构

从当前"一块平铺面板"改为**两问两答 + 折叠详情**：

```
┌────────────────────────────────────────────────────┐
│  响应来源                                           │
│                                                     │
│  🧠 攻击请求已到达模型层                            │
│     ✅ 模型响应原样返回，未经应用层改写              │
│                                                     │
│  依据：目标系统 Provenance 协议 (high confidence)    │
│                                                     │
│  [展开更多 ▾]                                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ HTTP 状态: 200                                │  │
│  │ 内容类型: text/plain; charset=UTF-8           │  │
│  │ 传输成功: ✓                                   │  │
│  │ 基线探针: —                                   │  │
│  └───────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

**四种主状态配色**：

| model_invoked | post_processed | 图标 | 颜色   | 标签                            |
|:------------:|:--------------:|:----:|--------|--------------------------------|
| `true`       | `false`        | 🧠   | emerald| 攻击请求已到达模型层            |
| `true`       | `true`         | ✏    | amber  | 模型响应被应用层改写            |
| `false`      | —              | 🛡    | blue   | 攻击请求被应用层前置拦截        |
| `null`       | `null`         | ❓    | slate  | 来源不确定（黑盒外不可判）      |

**不可评测场景的精细标签** — `notEvaluableDisplayCategory` 扩展：

| 场景                  | 标签                 | 色调     |
|-----------------------|----------------------|----------|
| model_invoked=false   | 未到达模型·守卫拦截  | blue     |
| transport_error + 探针 ok | 通信异常·目标健康  | rose     |
| transport_error + 探针 failed | 通信异常·目标离线 | rose |
| empty + 2xx          | 模型空响应·目标健康  | amber    |
| known_fallback       | 模型回退              | amber    |
| 其他                  | 无法评测              | orange   |

### 7.3 i18n 补充

**zh.ts** 新增键值：

```typescript
results: {
  // ...existing...
  provenanceModelInvokedTrue: "攻击请求已到达模型层",
  provenanceModelInvokedFalse: "攻击请求被应用层前置拦截",
  provenancePostProcessedFalse: "模型响应原样返回，未经应用层改写",
  provenancePostProcessedTrue: "模型响应被应用层改写",
  provenanceUnknown: "来源不确定（黑盒外不可判）",
  provenanceUnknownHint: "目标未提供 Provenance 协议，建议配置 origin_rules 或人工复核",
  provenanceSourceLabel: "判定依据",
  provenanceSource: {
    target_header: "目标系统 Provenance Header",
    target_body: "目标系统 Provenance Body 字段",
    origin_rule: "用户配置的 origin_rules",
    known_fallback: "内置已知回退签名库",
    heuristic: "启发式推断",
    target_type_default: "目标类型默认值",
    none: "无信号",
  },
  blockReason: {
    pre_guardrail: "前置安全网关拦截",
    input_validation: "输入参数校验不通过",
    auth_denied: "认证/鉴权失败",
    rate_limit: "限流/配额耗尽",
    tool_only_route: "纯规则路由，不走模型",
  },
  postReason: {
    pii_redaction: "敏感信息脱敏",
    policy_filter: "内容策略过滤",
    format_enforcement: "格式强制修正",
    tool_rewrite: "工具调用结果替代模型原文",
  },
}
```

**en.ts** 同步翻译。

---

## 8. 测试计划

### 8.1 后端

#### test_response_screening.py 新增用例

| 用例                                | 验证内容                                    |
|-------------------------------------|---------------------------------------------|
| `test_provenance_header_model_invoked_true` | header 声明 model_invoked=true → 正确映射  |
| `test_provenance_header_blocked`     | header model_invoked=false + block_reason → 正确映射 + app_fallback |
| `test_provenance_header_post_processed` | header post_processed=true + post_reason → 正确映射 |
| `test_provenance_body_field`         | 响应体 `_provenance` 字段被正确解析         |
| `test_provenance_header_overrides_heuristic` | Header 优先级 > 启发式                |
| `test_structured_origin_rule_eq`     | JSON path eq 规则命中 → blocked             |
| `test_structured_origin_rule_exists` | JSON path exists 规则命中 → model           |
| `test_structured_origin_rule_no_match` | 无命中 → 降级到启发式                     |
| `test_backward_compat_derive_origin` | 新字段正确派生旧 response_origin             |
| `test_no_provenance_custom_target`   | 无任何信号 → model_invoked=None              |

#### 已有测试回归

- `test_phase1_regression.py` — 确认 scan 流程无破坏
- `test_phase2_adapter_regression.py` — 确认 adapter 路径无破坏
- `test_phase3_probe_regression.py` — 确认 probe 逻辑无破坏
- `test_result_judgement_regression.py` — 确认 judge 路径无破坏
- `test_baseline_probe.py` — 确认 baseline_probe 逻辑无破坏

### 8.2 前端

- `npm run build` 通过
- 手动验证：扫 FinanceBot，报告页面显示两问两答，无 Unknown

---

## 9. 文件改动清单

### 后端

| 文件 | 改动 |
|------|------|
| `app/services/response_screening.py` | ResponseEvaluation 加 5 个字段；screen_response_origin 加 Level 1 读取；_derive_response_origin 派生逻辑；简化版 JSON path 求值器 |
| `app/services/adapter_executor.py` | invoke 成功后采集 X-Provenance-* headers 写入 transport_meta |
| `app/services/target_client.py` | invoke_target_with_envelope 从 transport_meta 透传 provenance |
| `app/schemas/scan.py` | TargetOriginRules 加 structured 字段 + StructuredOriginRule model |
| `app/schemas/response_evaluation.py` | ResponseEvaluationResponse 加新字段（如有单独 schema） |
| `app/tests/test_response_screening.py` | 新增 10+ 测试用例 |

### Mock Targets

| 文件 | 改动 |
|------|------|
| `mock_targets/financebot/src/.../ChatController.java` | 返回 ChatResult 替代 String；添加 Header |
| `mock_targets/financebot/src/.../ChatService.java` | chat() 返回 ChatResult；分支标记 provenance |
| `mock_targets/financebot/src/.../GlobalExceptionHandler.java` | 验证失败时加 provenance header |
| `mock_targets/shopbot/src/routes/chatRoute.ts` | 响应加 header |
| `mock_targets/shopbot/src/services/chatService.ts` | chat() 返回结构化对象 |

### 前端

| 文件 | 改动 |
|------|------|
| `src/types/index.ts` | ResponseEvaluation 加 5 个字段 |
| `src/utils/responseEvaluation.ts` | normalizeResponseEvaluation 读新字段；notEvaluableDisplayCategory 扩展 |
| `src/components/ResponseEvaluationPanel.tsx` | 两问两答视觉重构 + 折叠详情 |
| `src/i18n/zh.ts` | 新增 provenance 相关键值 |
| `src/i18n/en.ts` | 同步英文翻译 |

---

## 10. 执行顺序

```
Step 1  后端 schema 扩字段（ResponseEvaluation + TargetOriginRules）
Step 2  后端 adapter_executor 采集 X-Provenance-* headers
Step 3  后端 response_screening 四级兑现逻辑
Step 4  FinanceBot (Java) 改造 → ChatResult + Header
Step 5  ShopBot (Node) 改造 → 结构化返回 + Header
Step 6  前端类型 + ResponseEvaluationPanel 两问两答
Step 7  前端 notEvaluableDisplayCategory + i18n
Step 8  测试（新增 + 回归）
Step 9  手动验证：扫 FinanceBot，报告里 0 Unknown
```
