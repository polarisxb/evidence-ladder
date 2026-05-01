# 攻击模板库技术说明

| 项目 | 内容 |
|------|------|
| **文档类型** | 技术参考 / 数据字典 |
| **版本** | 1.1 |
| **文档状态** | 正式发布 |
| **读者对象** | 后端开发、安全研究、模板维护人员 |
| **关联文档** | [用户操作手册](./user-guide.md) · [安装配置说明](./installation-guide.md) |

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.1 | 2026-04 | 版式专业化；校正 OWASP 汇总表；补充合规声明 |
| 1.0 | 2026-04 | 初版 |

---

## 摘要

攻击模板库是 天鉴 · 衡 的 **结构化载荷数据源**，以 JSON 形式存放七类攻击类别下的模板、载荷变体与成功判定线索。引擎在运行时读取这些文件并可选地与高级攻击策略（PAIR、TAP、Crescendo 等）组合。**`owasp_id` 等字段以各 JSON 文件为准**；不同 OWASP LLM Top 10 版本间编号可能演进，汇总表仅作交叉引用。

**合规声明**：模板仅用于 **已获授权** 的安全测试、研发自测或封闭靶场；禁止用于未授权系统。使用者须遵守适用法律与组织政策。

---

## 目录

1. [存储与加载](#1-存储与加载)
2. [模板 JSON Schema](#2-模板-json-schema)
3. [攻击类别详解](#3-攻击类别详解)
4. [安全框架映射](#4-安全框架映射)
5. [扩展与维护](#5-扩展与维护)
6. [与高级攻击引擎的协同](#6-与高级攻击引擎的协同)

---

## 1. 存储与加载

| 项目 | 说明 |
|------|------|
| **目录** | `backend/app/attack_templates/` |
| **格式** | 每文件对应一个 `category`，内含若干 `templates` |
| **加载** | 后端启动时扫描并载入；修改后需 **重启后端** 生效 |

---

## 2. 模板 JSON Schema

每个攻击模板文件描述同一类别下的模板列表，结构示例如下：

```json
{
  "category": "prompt_injection",
  "category_name": "Prompt Injection",
  "owasp_id": "LLM01",
  "atlas_ids": ["AML.T0051", "AML.T0043"],
  "description": "类别描述",
  "templates": [
    {
      "id": "PI-001",
      "name": "Direct Instruction Override",
      "technique": "instruction_override",
      "severity": "high",
      "atlas_id": "AML.T0051",
      "description": "攻击技术描述（可选）",
      "multi_turn": false,
      "payloads": [
        {
          "text": "实际发送给目标 AI 的攻击文本",
          "language": "en",
          "variant": "base"
        }
      ],
      "success_indicators": ["判定攻击成功的依据"]
    }
  ]
}
```

### 2.1 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `category` | string | 是 | 类别标识（英文蛇形命名） |
| `category_name` | string | 是 | 界面与报告用显示名 |
| `owasp_id` | string | 是 | 与 OWASP LLM Top 10 对齐的引用 ID（以本仓库约定为准） |
| `atlas_ids` | string[] | 否 | MITRE ATLAS 技术 ID 列表 |
| `description` | string | 是 | 类别级描述 |
| `templates[].id` | string | 是 | 模板唯一 ID |
| `templates[].name` | string | 是 | 模板显示名称 |
| `templates[].technique` | string | 是 | 攻击技术子类标识 |
| `templates[].severity` | string | 是 | `critical` / `high` / `medium` / `low` |
| `templates[].multi_turn` | boolean | 否 | 是否多轮模板，默认 `false` |
| `templates[].payloads` | array | 是 | 至少 1 条载荷 |
| `templates[].payloads[].text` | string | 是 | 发送文本 |
| `templates[].payloads[].language` | string | 是 | 语言标签，如 `en`、`zh` |
| `templates[].payloads[].variant` | string | 是 | 变体标签，如 `base`、`admin`、`encoded` |
| `templates[].success_indicators` | string[] | 是 | 成功判定的文本线索（供分析与裁判参考） |

### 2.2 模板 ID 前缀约定

| 类别 | ID 前缀 | 示例 |
|------|---------|------|
| Prompt Injection | `PI-` | PI-001 |
| System Prompt Extraction | `SP-` | SP-001 |
| Jailbreak | `JB-` | JB-001 |
| Information Disclosure | `ID-` | ID-001 |
| Indirect Injection | `II-` | II-001 |
| Excessive Agency | `EA-` | EA-001 |
| Denial of Service | `DoS-` | DoS-001 |

---

## 3. 攻击类别详解

下列 `owasp_id` 与各 JSON 文件 **保持一致**。

### 3.1 Prompt Injection（提示注入）

| 属性 | 值 |
|------|-----|
| **文件** | `prompt_injection.json` |
| **OWASP** | LLM01 |
| **ATLAS** | AML.T0051, AML.T0043, AML.T0048 |
| **风险摘要** | 通过用户侧输入覆盖或弱化系统指令，使模型行为偏离业务预期 |

**常见 technique 示例**：`instruction_override`（直接覆盖指令）、`authority_impersonation`（冒充高权限身份）、`role_switching`（角色切换）、`context_manipulation`（上下文操控）。

---

### 3.2 System Prompt Extraction（系统提示词提取）

| 属性 | 值 |
|------|-----|
| **文件** | `system_prompt_extraction.json` |
| **OWASP** | LLM07 |
| **ATLAS** | AML.T0056 |
| **风险摘要** | 诱导模型输出隐藏 system prompt、业务规则或内部策略文本 |

**常见 technique 示例**：`direct_request`、`indirect_elicitation`、`encoding_bypass`、`output_format_manipulation`。

**Canary Token**：在 system prompt 中预埋唯一串；若响应中出现该串，可作为 **高置信度** 泄露信号（需在目标配置中启用）。

---

### 3.3 Jailbreak（越狱）

| 属性 | 值 |
|------|-----|
| **文件** | `jailbreak.json` |
| **OWASP** | LLM01 |
| **ATLAS** | AML.T0054 |
| **风险摘要** | 削弱安全对齐，使模型输出策略禁止的内容 |

**常见 technique 示例**：`roleplay_jailbreak`、`hypothetical_scenario`、`character_injection`（Unicode / 零宽字符绕过）、`skeleton_key`、`gcg_suffix`（对抗后缀类）。

---

### 3.4 Information Disclosure（信息泄露）

| 属性 | 值 |
|------|-----|
| **文件** | `information_disclosure.json` |
| **OWASP** | LLM02 |
| **ATLAS** | AML.T0057 |
| **风险摘要** | 诱导输出配置、凭据、用户数据等敏感信息 |

**常见 technique 示例**：`social_engineering`、`context_exploitation`、`data_fishing`。

---

### 3.5 Indirect Injection（间接注入）

| 属性 | 值 |
|------|-----|
| **文件** | `indirect_injection.json` |
| **OWASP** | LLM01 |
| **ATLAS** | AML.T0051, AML.T0043 |
| **风险摘要** | 经由检索片段、工具输出、外部文档等 **非用户直接输入** 通道注入指令 |

**常见 technique 示例**：`rag_document_injection`、`retrieval_barrier_bypass`、`tool_result_hijacking`、`zero_click_context_injection`、`multi_hop_injection`、`agent_arena_hijacking`。

---

### 3.6 Excessive Agency（过度代理）

| 属性 | 值 |
|------|-----|
| **文件** | `excessive_agency.json` |
| **OWASP** | LLM08（本仓库 JSON 约定） |
| **ATLAS** | AML.T0048 |
| **风险摘要** | 诱导越权操作、工具滥用或夸大可用权限 |

**常见 technique 示例**：`unauthorized_action`、`tool_misuse`、`privilege_escalation`。

---

### 3.7 Denial of Service（拒绝服务）

| 属性 | 值 |
|------|-----|
| **文件** | `denial_of_service.json` |
| **OWASP** | LLM04（本仓库 JSON 约定） |
| **ATLAS** | AML.T0029 |
| **风险摘要** | 消耗算力或使服务不可用 |

**常见 technique 示例**：`resource_exhaustion`、`infinite_loop_trigger`、`output_explosion`。

---

## 4. 安全框架映射

### 4.1 OWASP LLM Top 10（与本仓库类别的对应关系）

下表汇总 **本仓库** 中各类别使用的 `owasp_id`。若与公开发布的 OWASP 年度版本在编号或命名上存在差异，以 `attack_templates/*.json` 为准。

| OWASP ID（本仓库） | 风险名称（参考） | 覆盖的平台攻击类别 |
|-------------------|------------------|---------------------|
| LLM01 | Prompt Injection（及相近表述） | Prompt Injection、Jailbreak、Indirect Injection |
| LLM02 | Sensitive Information Disclosure | Information Disclosure |
| LLM04 | 拒绝服务 / 资源耗尽类（本仓库用于 DoS 类别） | Denial of Service |
| LLM07 | System Prompt Leakage | System Prompt Extraction |
| LLM08 | Excessive Agency（本仓库约定） | Excessive Agency |

### 4.2 MITRE ATLAS（节选）

| ATLAS ID | 技术名称 | 典型用途 |
|----------|----------|----------|
| AML.T0029 | Denial of ML Service | DoS 类 |
| AML.T0043 | Craft Adversarial Data | 对抗样本构造 |
| AML.T0048 | Command and Control via AI | 越权与工具链滥用 |
| AML.T0051 | LLM Prompt Injection | 提示注入 |
| AML.T0054 | LLM Jailbreak | 越狱 |
| AML.T0056 | LLM Meta Prompt Extraction | 系统提示词提取 |
| AML.T0057 | LLM Data Leakage | 数据泄露 |

---

## 5. 扩展与维护

### 5.1 新增模板条目

1. 在对应类别的 `templates` 数组中追加对象。  
2. 保证 `id` 全局唯一且符合前缀规范。  
3. 至少包含 1 条 `payloads` 与 1 条 `success_indicators`。  
4. 重启后端服务。

### 5.2 新增类别文件

1. 在 `backend/app/attack_templates/` 新建 JSON，顶层字段符合第 2 节 Schema。  
2. 后端按文件发现机制加载新类别（具体行为以实现为准）。  

### 5.3 多语言载荷

`payloads[].language` 建议使用 `en`、`zh` 等稳定标签；同一模板可并列多条语言变体以提高覆盖率。

更细的编辑规范见仓库内 **attack-template-authoring** 技能或 `.codex` 下对应说明（若存在）。

---

## 6. 与高级攻击引擎的协同

模板作为 **种子**，由引擎进行迭代、搜索或变异；并非所有引擎对所有模板启用，以产品配置与实现为准。

| 引擎 | 与模板的关系（概要） |
|------|----------------------|
| **PAIR** | 以模板载荷为起点，迭代优化攻击文本 |
| **TAP** | 以模板为根节点做树搜索与剪枝 |
| **Crescendo** | 将目标拆解为多轮渐进对话 |
| **Mutation** | 对载荷做词汇、语义或编码变异 |
| **FITD** | 从低风险到高风险梯度递进请求 |
| **MSJ / ICE 等** | 与多轮、场景化策略组合时使用模板作为初始输入（以界面与引擎实现为准） |

---

*— 文档结束 —*
