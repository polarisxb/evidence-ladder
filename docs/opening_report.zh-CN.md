# 开题报告初稿：基于多源证据分层的大模型应用安全评测与闭环补测方法研究

## 一、课题名称

基于多源证据分层的大模型应用安全评测与闭环补测方法研究

可选题名：

- 面向大模型应用的证据分层安全评测方法与可信攻击成功率度量研究
- 面向 LLM 应用的多源证据分层与冲突驱动闭环补测方法研究
- 基于 E-level × Kill-chain 矩阵的大模型应用安全评测方法研究

当前建议采用第一个题名作为大创/开题主标题，第二个题名作为论文英文投稿方向的延展。

英文工作题名建议：

- *Multi-Source Evidence-Stratified Evaluation for LLM Applications with Conflict-Driven Retesting*
- *Trustworthy Attack Success Measurement for LLM Application Security via Evidence Stratification*

注：本研究不再以"评测平台"为题名核心。平台是支撑系统，核心创新在于**多源证据分层协议**、**Evidence-Stratified ASR 度量**、**Quartet 四元对照**、**冲突驱动闭环补测**与 **E-level × Kill-chain 二维评测框架**。

## 二、研究背景与意义

大模型正在被快速集成到客服、办公助手、知识库问答、检索增强生成系统和工具调用型 Agent 中。与传统只评测基础模型安全性的工作不同，真实业务风险往往发生在应用层：用户输入、系统提示词、历史消息、检索内容、插件输出和后端工具调用被组合到同一上下文中，导致模型可能出现提示注入、系统提示词泄露、敏感信息泄露、越权工具调用和不可信输出传递等问题。

现有大模型安全评测常以攻击成功率作为核心指标，但在应用层场景中，简单的成功/失败判定容易混淆多种情况。例如，模型可能只是复述了攻击文本，可能只是声称执行了某个操作，也可能被 LLM-as-a-Judge 误判为攻击成功；在 Agent 场景下，模型声称“已删除邮件”并不等于真实工具调用或业务状态发生变化。若不区分这些证据强度，评测结果会高估或低估真实风险，难以支撑企业安全治理和学术研究。

因此，本课题拟面向大模型应用层安全评测，研究一种基于**多源证据分层**的黑盒评测方法。课题重点不在于单纯堆叠攻击算法，也不在于对单一裁判结果做事后统计校正，而在于建立可复现、可比较、可审计的评测流程：将文本声称、模型裁判、规则命中、工具调用和业务探针验证等异质证据沿强度维度分层，并通过 Quartet 控制变量与冲突驱动的闭环补测机制提升攻击成功率指标的可信度。

## 三、国内外研究现状

### 3.1 大模型应用安全风险

OWASP LLM Top 10 将提示注入、敏感信息泄露、过度代理行为、系统提示词泄露等列为大模型应用的主要风险。NIST AI RMF Generative AI Profile 强调生成式 AI 系统需要可测量、可审计和可管理的风险治理流程。MITRE ATLAS / SAFE-AI 从攻击技术和威胁建模角度总结了提示注入、工具滥用和数据泄露等风险路径。

这些框架为本课题提供了风险分类依据，但它们更多是风险框架和治理指南，并未直接给出面向具体 LLM 应用接口的自动化评测协议。

### 3.2 Jailbreak 与 Prompt Injection 评测

HarmBench、JailbreakBench 等工作推动了越狱攻击和安全拒答能力的标准化评测，常用攻击成功率、拒答率和模型裁判等指标评估模型安全性。这类工作为基础模型安全评测提供了重要参考，但在真实 LLM 应用场景中，最终响应可能经过应用层模板、后处理、拦截器、检索上下文或工具调用链路影响，单纯依据最终文本计算 ASR 容易产生偏差。

### 3.3 Agent 与工具调用安全评测

AgentDojo、ToolEmu、AgentHarm、tau-bench 等研究开始关注工具调用型 Agent 的安全性、可靠性和任务完成情况。其中，tau-bench 强调通过最终数据库状态判断 Agent 是否完成任务，AgentDojo 关注动态环境中的间接提示注入攻击与防御。这些工作表明，Agent 安全评测不能只看最终自然语言回复，还需要关注工具调用和环境状态。

本课题拟在此基础上聚焦"应用层黑盒评测"和"多源证据强度分层"，将文本回复、工具调用、状态变化和业务探针验证纳入统一的证据分层协议，并将其与 Quartet 对照、冲突驱动复测与 Kill-chain 阶段建模组合，服务于可信、可复现的应用层安全评测。

### 3.4 LLM-as-a-Judge 可靠性问题

安全评测中常使用 LLM-as-a-Judge 判断攻击是否成功，但已有研究表明，LLM 裁判会受到提示词、样本分布、攻击文本和评价标准影响，可能产生误判。本课题不否定模型裁判的辅助价值，而是将其作为证据链中的一层，并结合规则证据、人工标注和业务探针进行校准。

### 3.5 现有工作局限与本文定位

近一年内，国内外已有若干工作直接指出 LLM 安全评测中"攻击成功率不可靠"的问题，并各自给出了不同的解决路径。为了避免本文与这些工作正面重合，需要明确各自的对象、方法与边界。

**(1) Corrected ASR：基于裁判精度的统计后校正。** *A Coin Flip for Safety: LLM Judges Fail to Reliably Measure Adversarial Robustness* (2026) 通过 6642 条人工标注证明，主流 LLM-as-a-Judge 在对抗性分布偏移下接近随机，并提出 **Corrected ASR**——以裁判 precision 对 judge-positive 结果进行倍乘校正。该工作面向**基础模型 adversarial robustness 评测**，校正方式为**事后统计调整**，未涉及应用层 RAG、工具调用、业务状态等多源证据。

**(2) Verification-Layer ASR：评测器替换与二阶段验证。** *When Scanners Lie: Evaluator Instability in LLM Red-Teaming* (2026) 在 garak 25 个攻击类别上发现 22 个评测器不稳定（最大 ±33%），并提出**两阶段可靠性框架**：先量化评测器分歧，再加入独立 verifier 模型把扫描器准确率从 72% 提升至 89%。该工作面向**通用扫描器**，verification 层仍是单一 verifier，不涉及证据来源分层、Quartet 控制变量或 probe 状态验证。

**(3) Kill-Chain Canary：按攻击传播阶段分解。** *Pipeline-stage Canary Kill-Chain in Multi-Agent Systems* (2026) 用 cryptographic canary 跟踪 Exposed → Persisted → Relayed → Executed 四个阶段，主张 agentic 安全评测必须做 stage decomposition。该工作给出了"攻击传播到哪里"的维度，但未给出"凭什么确认"的证据强度维度。

**(4) Noisy but Valid：基于 TPR/FPR 的统计有效性框架。** *Noisy but Valid* (2026) 用人工标注校准集估计 judge 的 TPR/FPR，给出 finite-sample Type-I error 控制的统计推理框架。该工作偏向**统计方法论**，可作为本文证据分层后再做显著性检验的统计基础，与本研究互补而非重叠。

**本文定位与上述工作的差异：**

上述工作主要解决基础模型层面或扫描器层面的裁判可靠性问题。本文关注 **LLM 应用层黑盒评测**，特别是 RAG、工具调用、业务状态变化和 Agent 越权行为。本文不将 LLM 裁判作为最终事实来源，也不依赖单一 verifier 进行二阶段校验，而是：

- 构建**多源证据分层协议**，将 text claim、judge、rule、tool log、probe 等异质证据沿 E0–E5 强度维度分层；
- 提出 **Evidence-Stratified ASR**，将攻击结果按证据来源与证据强度分层报告，与 Corrected ASR 的"事后统计校正"是正交策略；
- 引入 **Quartet 四元对照**与**冲突驱动闭环补测**，使弱证据 finding 自动进入复测而非单纯被裁判精度倍乘掉；
- 进一步将证据强度（E-level）与攻击传播阶段（Kill-chain stage）正交组合为**二维评测矩阵**，弥补单维度评测的不足。

简言之，本文与现有工作不是同一类问题的同一类解法，而是把"评测可靠性"从基础模型/扫描器层面延伸到**应用层多源证据**层面，并把"事后校正"延伸到"运行中闭环补测"。

## 四、研究目标

本课题目标是设计并实现一个面向大模型应用的黑盒安全评测平台，重点解决以下问题：

1. 如何对 LLM 应用而非单一基础模型进行可复现安全测试。
2. 如何区分“讨论攻击文本”“执行攻击目标”“越权声称”和“真实业务副作用”。
3. 如何建立证据分级协议，提升攻击成功率指标的可信度。
4. 如何在工具调用型 Agent 场景中验证越权行为是否真实发生。
5. 如何通过人工标注和 Judge 校准评估自动裁判结果的可靠性。

最终希望形成一套工程上可运行、实验上可量化、论文上可解释的 LLM 应用安全评测方法。

## 五、研究内容

### 5.1 大模型应用安全评测中的证据失真问题

LLM 应用层评测的根本困难在于：最终响应、模型裁判、规则命中、工具调用和业务状态变化属于**异质证据来源**，强度与可验证性差异巨大，但既有评测往往把它们折叠为单一"攻击是否成功"的布尔判定。该折叠会引入三类典型证据失真：

- **复述—执行混淆**：模型复述或讨论攻击文本被误判为执行攻击。
- **声称—副作用混淆**：模型在文本中声称"已删除邮件"被等同于真实工具调用与状态变化。
- **裁判—事实混淆**：LLM-as-a-Judge 在分布偏移下接近随机，但其结论被直接当作 ground truth。

本研究的总体技术取向是不再将单一证据视为成功判定的事实来源，而是通过**多源证据分层**、**Quartet 控制变量**、**冲突驱动闭环补测**和**业务状态探针验证**共同构造判定面，把"是否成功"问题转化为"在何种证据强度下、在攻击传播链的哪个阶段被确认"问题。

### 5.2 Quartet 四元对照实验设计

为隔离误判与过度防御，本课题为每个逻辑攻击用例设计四类变体：

- **Clean**：正常任务输入，用于评估原任务是否可完成（衡量 Utility）。
- **Attack**：包含攻击目标的输入（衡量 Attack Success）。
- **Quoted Attack**：将攻击内容作为引用或待分析文本，检验系统是否把"讨论"误判为"执行"（隔离 quoted-attack false positive）。
- **Benign Distractor**：无害但与攻击在词汇/格式上相似的长文本，检验系统是否过度防御（衡量 Over-Defense）。

四元对照用于支撑更严格的攻击成功判定。理想情况下，安全可用的应用应满足：Clean 可完成、Attack 不成功、Quoted Attack 不成功、Benign Distractor 不被误拒；若仅基于 Attack 单变体计算 ASR，则上述四种失真无法被识别。

Quartet 同时提供四类**冲突类型**，用于触发后续闭环补测：

- `judge_without_rule_evidence`：Judge 判成功但规则/probe 均无强证据。
- `quoted_attack_success`：Attack 与 Quoted Attack 都"成功"，疑似 judge 误判。
- `benign_distractor_refused`：Benign Distractor 被拒答，疑似过度防御。
- `clean_failed`：Clean 任务失败，应判 not_evaluable 或 utility failure。

### 5.3 Evidence-Stratified ASR 证据分层指标

本课题提出 **Evidence-Stratified ASR（证据分层攻击成功率）**，将攻击结果按证据来源与证据强度分层报告。证据等级初步定义为：

| 等级 | 名称 | 判定依据 |
|---|---|---|
| E0 | Not Evaluable | 基础设施失败、协议配置错误或目标不可用 |
| E1 | Text Claim | 模型仅在文本中声称执行了操作 |
| E2 | Judge-Suspected | LLM 裁判认为攻击疑似成功 |
| E3 | Rule-Verified | Canary token、隐藏字符串或强规则命中 |
| E4 | Tool-Observed | 工具调用日志显示越权调用发生 |
| E5 | Probe-Verified | 业务状态变化被探针或状态差异验证 |

报告中同时给出多种指标，避免汇报数字中混入弱证据：

- **Evaluability Rate**：可评价运行比例（剔除 E0）。
- **Raw ASR**：传统文本扫描结果。
- **Judge ASR**：模型裁判判断的攻击成功率。
- **Text-Claim ASR**：仅文本声称层面的越权成功率（E1）。
- **Rule-Verified ASR**：规则强证据确认的攻击成功率（E3）。
- **Tool-Observed ASR**：工具调用层面的越权成功率（E4）。
- **Probe-Verified ASR**：业务探针确认的攻击成功率（E5）。
- **Evidence-Stratified ASR**：在 E≥E3 上聚合的强证据攻击成功率。
- **Quartet-Validated ASR**：通过四元对照后保留的攻击成功率。
- **Utility Rate**：正常任务完成率。
- **Over-Defense Rate**：正常输入被错误拒绝的比例。

**与 Corrected ASR 的区别（关键差异声明）：**

不同于 *A Coin Flip for Safety* (2026) 提出的 Corrected ASR 通过裁判 precision 对 judge-positive 结果进行**统计后校正**，本文提出的 Evidence-Stratified ASR 将攻击成功结果按文本声称、模型裁判、规则命中、工具观测、业务探针验证等**证据来源分层统计**，从而避免将弱证据、误判证据和真实业务副作用混为同一类成功。两类方法在数学上是正交的：Corrected ASR 是事后校正的标量调整，Evidence-Stratified ASR 是按来源切分的多元报告，二者可在同一实验中并列报告以便对比。

### 5.4 弱证据冲突识别与闭环补测机制

本课题提出**弱证据冲突驱动的闭环补测机制**，使初测中产生的弱证据 finding 能够被自动复测、确认或推翻，而非依赖单一裁判精度倍乘抹平。

**冲突类型识别：**

| conflict_type | 含义 | 触发处理 |
|---|---|---|
| `judge_without_rule_evidence` | Judge 判成功但 rule/probe 无强证据 | 触发 Quartet 复测 |
| `quoted_attack_success` | Quoted Attack 也成功 | 标记 judge false positive 候选 |
| `text_claim_probe_failed` | 文本声称成功但 probe 失败 | 保持 E1，不升级至 E5 |
| `rule_judge_disagree` | 规则命中但 judge 未判成功 | 升级证据，记录 judge miss |
| `secret_disclosure_suspected` | 疑似泄露但无 canary 命中 | 触发 canary 重测 |
| `unauthorized_action_claim` | 文本声称越权动作 | 触发 probe 验证 |

**复测策略：**

- 初测 → 冲突识别 → 选择补测策略（Quartet / Canary 重测 / Probe / 多次重复）→ 复测执行 → 与初测结果关联 → 标记为 `confirmed` / `overturned` / `manual_review_needed`。
- 受 *When Scanners Lie* (2026) verification-layer 框架启发，但本文将"verifier"扩展为**多类异质证据源**而非单一 verifier 模型，并以 conflict-type → retest-action 状态机规范化触发条件。
- 设置 `max_retest_rounds` 上限，避免补测无限循环；记录每个 finding 的补测历史（initial → retest_1 → ... → final），保留可审计追踪。

### 5.5 Agent 工具调用与业务状态验证

为支撑 E4（Tool-Observed）与 E5（Probe-Verified），本课题构建最小业务 Agent 沙箱。初步选择两个场景：

- **邮件 Agent**：读取邮件、总结邮件、发送邮件、删除邮件。
- **电商 Agent**：查询订单、修改地址、申请退款、导出订单。

每个场景均记录**操作前状态快照、工具调用日志、操作后状态快照与 Probe 查询结果**：

- 若模型回复"我已发送邮件"，但 outbox 未发生变化 → 判为 E1 Text Claim。
- 若 `send_email` 工具被调用 → 升级至 E4 Tool-Observed。
- 若 Probe 查询到攻击邮件已实际写入 outbox 且包含攻击 payload → 升级至 E5 Probe-Verified。

该设计借鉴 *tau-bench* (2024) 用最终数据库状态评估任务完成的思想，但将其扩展到**安全评测语境下的状态差异验证**，并与证据分层协议绑定。

### 5.6 E-level × Kill-chain 二维评测矩阵

本文进一步将证据强度维度（E0–E5）与攻击传播阶段（Exposed / Persisted / Relayed / Executed）正交组合，形成**二维评测矩阵**。该矩阵既区分"攻击传播到哪里"，也区分"我们凭什么确认它发生"，从而避免仅依据最终文本或单一 canary 事件判断应用层安全风险。

| | Exposed | Persisted | Relayed | Executed |
|---|---|---|---|---|
| **E1 Text Claim** | 模型在文本中复述输入注入 | — | 注入文本被原样转发 | 模型声称已执行 |
| **E2 Judge-Suspected** | Judge 认为输入暴露成功 | — | Judge 认为传递成功 | Judge 认为最终执行 |
| **E3 Rule-Verified** | Canary 出现于上下文输入 | Canary 写入 memory/RAG | Canary 经下游 agent 转发 | Canary 出现于工具入参 |
| **E4 Tool-Observed** | — | 工具日志显示写入 | 工具日志显示读取并传递 | 工具日志显示越权调用 |
| **E5 Probe-Verified** | — | 状态快照显示持久化 | 跨 agent 状态差异确认 | 业务后端状态变化 |

阶段定义参考 *Pipeline-stage Canary Kill-Chain in Multi-Agent Systems* (2026)：

- **Exposed**：攻击 payload 进入目标上下文。
- **Persisted**：payload 被写入 memory、RAG 或长期上下文。
- **Relayed**：payload 被下游 agent / 工具读取并继续传递。
- **Executed**：payload 触发实际工具调用或业务副作用。

该矩阵的研究价值在于：

- 单一维度评测（仅证据强度或仅传播阶段）会漏判组合情形，例如 E5 Persisted（持久化但未执行）与 E1 Executed（声称执行但无证据）的风险性质不同；
- 矩阵化报告能直接支撑应用方的修复决策——E≥E3 + Stage=Executed 的格子最具优先级，E≤E2 + Stage=Exposed 主要服务于早期发现；
- 与现有工作的差异：*Coin Flip* 与 *Scanners Lie* 不涉及阶段维度，*Kill-Chain Canary* 不涉及证据强度维度，本矩阵是两者的正交融合。

### 5.7 平台实现（系统支撑）

为支撑上述协议、指标、对照与矩阵，本课题实现一套面向 LLM 应用的安全评测原型平台。平台面向 OpenAI-compatible API、自定义 HTTP 接口和内置脆弱目标，支持提示注入、系统提示词泄露、越狱攻击、敏感信息泄露、间接提示注入和过度代理行为等测试类型，提供扫描任务创建、攻击模板执行、结构化结果分析、Quartet 变体生成、补测调度、人工复核与报告生成能力。

平台不作为本研究的核心创新点，而是作为**可复现实验的系统支撑**与**开源参考实现**，便于后续工作复现本文实验、扩展新攻击类别或接入新业务沙箱。

## 六、拟解决的关键问题

1. 应用层评测对象复杂，最终响应并不等同于基础模型原始输出。
2. 攻击成功率容易混淆复述、讨论、声称、工具调用和真实副作用。
3. Agent 场景下越权行为需要通过工具日志和状态变化验证。
4. LLM-as-a-Judge 存在误判，需要通过人工标注和规则证据校准。
5. 安全评测平台自身需要具备可审计、可复现和较高的安全性。

## 七、创新点

1. **提出面向 LLM 应用层的多源证据分层协议**：将攻击结果按 E0 not_evaluable、E1 text_claim_only、E2 judge_suspected、E3 rule_verified、E4 tool_observed、E5 probe_verified 区分，避免把弱证据、误判证据和真实业务副作用混为同一类成功。
2. **提出 Evidence-Stratified ASR 证据分层指标**：将 Raw / Judge / Text-Claim / Rule-Verified / Tool-Observed / Probe-Verified / Quartet-Validated ASR 按证据来源与证据强度分层报告。该方法在数学上正交于 *A Coin Flip for Safety* (2026) 提出的 Corrected ASR：后者通过裁判 precision 做事后统计校正，本文按异质证据来源做分层切分。
3. **提出 Quartet 四元对照机制**：以 Clean / Attack / Quoted Attack / Benign Distractor 四类变体共同构造判定面，识别 judge 把"讨论"当"执行"的误判、quoted-attack false positive 与 over-defense，并提供 `judge_without_rule_evidence`、`quoted_attack_success` 等结构化冲突类型作为后续补测触发条件。
4. **提出弱证据冲突驱动的闭环补测机制**：以 conflict-type → retest-action 状态机驱动 Quartet 复测、Canary 重测、Probe 验证或多次重复执行；将初测 weak finding 与复测结果关联，区分 confirmed / overturned / manual_review，避免将不可靠 finding 直接计入 ASR 数字。
5. **提出 E-level × Kill-chain 二维评测框架**：将证据强度（E0–E5）与攻击传播阶段（Exposed / Persisted / Relayed / Executed）正交组合，区分"攻击传播到哪里"与"凭什么确认它发生"，弥补 *A Coin Flip*、*When Scanners Lie*、*Kill-Chain Canary* 等单维度工作的覆盖空缺。
6. **实现原型平台作为系统贡献**：支撑扫描、Quartet 变体生成、证据归档、补测调度与报告生成的开源参考实现，为后续工作提供可复现的实验基础。该项作为 system contribution 而非核心 novelty。

## 八、技术路线

```mermaid
flowchart TD
    A["攻击用例与业务任务设计"] --> B["Quartet 变体生成"]
    B --> C["目标 LLM 应用 / Agent 执行"]
    C --> D["响应与工具日志采集"]
    D --> E["规则检测与 LLM Judge 分析"]
    D --> F["业务状态快照与 Probe 验证"]
    E --> G["证据等级判定"]
    F --> G
    G --> H["指标统计：ASR / Utility / FPR"]
    H --> I["人工标注与 Judge 校准"]
    I --> J["报告生成与实验分析"]
```

平台实现上，后端采用 FastAPI，负责扫描调度、攻击执行、目标适配、证据保存、Judge 校准和报告生成；前端采用 React，提供目标配置、扫描执行、结果查看、人工复核和指标展示。实验部分基于多模型、多场景、多攻击类型进行对比分析。

## 九、实验设计

### 9.1 Pilot 实验

第一阶段先完成小规模可行性实验：

- 场景：1 个 Agent 场景，优先选择邮件 Agent 或电商 Agent。
- 逻辑用例：30 个。
- 变体数量：每个用例 4 个变体，共 120 次运行。
- 模型数量：1-2 个。
- 标注数量：至少 50-100 条结果。

目标是验证评测链路能否跑通，并初步比较 Judge ASR、Text-Claim ASR 和 Probe-Verified ASR 的差异。

### 9.2 正式实验

第二阶段扩展为论文实验：

- 场景：2-3 个应用/Agent 场景。
- 逻辑用例：100 个以上。
- 运行次数：400 次以上，必要时加入重复运行。
- 模型数量：3-5 个。
- 人工标注：100-200 条。

主要对比维度：

| 方法 | 作用 |
|---|---|
| Raw ASR | 传统文本/扫描器结果 |
| Judge ASR | LLM-as-a-Judge 直接结论 |
| Corrected ASR | 对齐 *A Coin Flip for Safety* (2026) 的统计后校正 baseline |
| Verification-layer ASR | 对齐 *When Scanners Lie* (2026) 的二阶段 verifier baseline |
| **Evidence-Stratified ASR** | **本文提出的多源证据分层方法** |
| Quartet-Validated ASR | 通过四元对照后保留的强证据子集 |
| Probe-Verified ASR | 业务副作用确认子集（E5） |

主要对比问题：

1. Evidence-Stratified ASR 与 Raw / Judge / Corrected / Verification-layer ASR 的数值差异。
2. LLM Judge 与人工标注的一致性（Cohen's κ、precision/recall）。
3. 不同模型在 Prompt Injection、System Prompt Leakage、Excessive Agency 等风险上的分层 ASR 表现。
4. Quartet 对 quoted-attack false positive 与 over-defense 的识别能力。
5. Probe 验证对 Agent 越权行为判定的影响（E1 → E5 升级率）。
6. E-level × Kill-chain 矩阵在不同模型/防御条件下的格子分布差异。

### 9.3 统计分析与人工标注一致性

针对当前 LLM 安全评测领域普遍存在的"指标可比性不足"问题，本研究在实验设计中引入以下统计严谨性要求：

**(1) 双人独立标注与一致性分析。**

- 至少 200 条结果由两名标注者独立标注，标注字段至少包括：是否成功、是否仅讨论、是否越权声称、是否触发工具调用、是否被 Probe 验证、原任务是否完成。
- 计算 **Cohen's κ** 与 percent agreement，对 κ<0.6 的字段重新定义判定准则后再次抽样标注。
- 标注分歧 case 进入 adjudication 队列，由第三方裁定后形成 gold label。

**(2) Judge 校准与 TPR/FPR 估计。**

- 使用 gold label 集估计 LLM Judge 的 precision、recall、TPR、FPR、F1。
- 在适用场景下，参考 *Noisy but Valid* (2026) 的有效性框架，给出基于 imperfect judge 的 finite-sample 假设检验。
- 该校准结果同时用于：(a) 定义 E2（Judge-Suspected）的可信阈值；(b) 复现 Corrected ASR baseline。

**(3) 置信区间与显著性检验。**

- 所有报告 ASR 数值同时给出 **bootstrap 95% CI**（≥1000 次重抽样）。
- 多模型/多攻击对比时使用 **Holm–Bonferroni** 或 BH-FDR 进行 multiple comparison correction。
- 不重复运行的单一 ASR 数值不进入论文主表。

**(4) 样本量依据与 Power Analysis。**

- Pilot 样本量 30 用例 × 4 变体 × 2 模型 = 240 次运行的设计依据：检测两组 ASR 差异 ≥15%（α=0.05、power=0.8）所需的最小样本量。
- 正式实验扩展至 100+ 用例时，重新计算 power 并在论文方法章节披露。

**(5) 复现包要求。**

- 公开发布：用例与变体集合、目标系统配置、扫描日志、人工标注 gold label（脱敏）、统计分析脚本。
- 所有 ASR 数值附运行时间戳、模型版本、随机种子（如适用）与运行成本。

## 十、预期成果

1. 一个可运行的大模型应用黑盒安全评测平台。
2. 一套基于多源证据分层的可信攻击成功率度量协议（Evidence-Stratified ASR + E-level × Kill-chain 矩阵）。
3. 一组可复现实验用例和实验结果。
4. 一个工具调用型 Agent 越权行为评测原型。
5. 一篇大创结题报告或中文论文初稿。
6. 根据实验质量，进一步尝试中文核心、IEEE Access 或相关 workshop 投稿。

## 十一、进度安排

| 阶段 | 时间 | 任务 |
|---|---|---|
| 第一阶段 | 第 1-2 周 | 修复平台关键安全问题，确定课题题名和指标体系 |
| 第二阶段 | 第 3-5 周 | 完成 Quartet 用例组织和 Pilot Agent 场景 |
| 第三阶段 | 第 6-8 周 | 实现 Evidence-Stratified ASR 与 E-level × Kill-chain 矩阵统计输出 |
| 第四阶段 | 第 9-11 周 | 完成人工标注集、Judge 校准和小规模实验 |
| 第五阶段 | 第 12-14 周 | 扩展多模型实验，形成图表和案例分析 |
| 第六阶段 | 第 15-16 周 | 完成开题/中期/结题材料与论文初稿 |

## 十二、可行性分析

本课题已有较好的工程基础。当前项目已支持扫描任务、攻击模板、结构化黑盒判定、人工复核、报告生成、Probe 配置、Judge 校准等功能。后续工作主要是将已有能力收敛为稳定的实验协议和指标体系，而不是从零开始开发平台。

技术风险主要包括：模型 API 成本较高、实验随机性较强、LLM Judge 结果不稳定、Agent 沙箱实现复杂度上升。对应措施包括：先进行小规模 Pilot 实验，控制用例数量；引入 not_evaluable 分类；保留原始响应、工具日志和状态快照；通过人工标注和重复运行降低偶然性。

伦理和安全方面，本课题仅面向授权目标、模拟业务环境和自建 Agent 沙箱开展测试，不使用真实用户隐私、真实密钥或第三方未授权系统。系统提示词泄露测试使用 canary token 代替真实敏感信息。

## 十三、当前优先任务

1. 修复平台已发现的高优先级安全问题，尤其是默认认证关闭、SSRF、凭据回传和 WebSocket 鉴权问题。
2. 固化证据等级和指标定义，避免后续实验口径变化。
3. 选择一个最小 Agent 场景，完成可验证副作用闭环。
4. 整理 30 个 Pilot 用例，并生成四元对照变体。
5. 跑通第一轮实验，输出第一张指标表。

## 十四、参考文献与资料

### 标准与框架

1. OWASP Foundation. *OWASP Top 10 for Large Language Model Applications 2025.*
2. OWASP Foundation. *OWASP Top 10 for Agentic Applications 2026.*
3. NIST. *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile.*
4. MITRE. *SAFE-AI / ATLAS: Adversarial Threat Landscape for Artificial-Intelligence Systems.*

### 基础模型与攻击/扫描 benchmark

5. Mazeika et al. *HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal.* 2024.
6. Chao et al. *JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models.* 2024.
7. Liu et al. *Formalizing and Benchmarking Prompt Injection Attacks and Defenses (Open-Prompt-Injection).* arXiv:2310.12815.

### Agent 与工具调用安全评测

8. Debenedetti et al. *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.* arXiv:2406.13352, 2024.
9. Yao et al. *tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.* arXiv:2406.12045, 2024.
10. Ruan et al. *ToolEmu: Identifying the Risks of LLM Agents with an Emulated Sandbox.* ICLR 2024.
11. Andriushchenko et al. *AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents.* arXiv:2410.09024, 2024.

### 自动红队与攻击搜索

12. Mehrotra et al. *Tree of Attacks: Jailbreaking Black-Box LLMs Automatically (TAP).* arXiv:2312.02119, 2023.
13. Liu et al. *AutoDAN-Turbo: A Lifelong Agent for Strategy Self-Exploration to Jailbreak LLMs.* arXiv:2410.05295, 2024.
14. Rahmanzadehgervi et al. *Auto-RT: Automatic Jailbreak Strategy Exploration for Red-Teaming.* arXiv:2501.01830, 2025.
15. Zhou et al. *AutoRedTeamer: Autonomous Red-Teaming with Lifelong Attack Integration.* arXiv:2503.15754, 2025.
16. Yuan et al. *AgenticRed: Optimizing Agentic Systems for Automated Red-Teaming.* arXiv:2601.13518, 2026.
17. Dreadnode. *AIRTBench: Measuring Autonomous AI Red Teaming Capabilities in Language Models.* arXiv:2506.14682, 2025.

### 评测可靠性与裁判校准（核心对比文献）

18. *A Coin Flip for Safety: LLM Judges Fail to Reliably Measure Adversarial Robustness.* arXiv:2603.06594, 2026.
19. *When Scanners Lie: Evaluator Instability in LLM Red-Teaming.* arXiv:2603.14633, 2026.
20. *Noisy but Valid: Robust Statistical Evaluation of LLMs with Imperfect Judges.* arXiv:2601.20913, 2026.
21. Raina et al. *Know Thy Judge: On the Robustness Meta-Evaluation of LLM Safety Judges.* arXiv:2503.04474, 2025.
22. Wang et al. *RobustJudge: Automatic Robustness Evaluation for LLM-as-a-Judge.* arXiv:2506.09443, 2025.

### 攻击传播与证据链

23. *Pipeline-stage Canary Kill-Chain in Multi-Agent Systems.* arXiv:2603.28013, 2026.
24. Zhao et al. *Distractor Injection Attacks on Large Reasoning Models: Characterization and Defense.* arXiv:2510.16259, 2025.
25. *NotInject / PIGuard: Mitigating Over-defense in Prompt Injection Detection.* (InjecGuard project, 2025).

### 工具与平台

26. Derczynski et al. *garak: A Framework for Security Probing Large Language Models.* arXiv:2406.11036, 2024.
27. Microsoft AI Red Team. *PyRIT: A Framework for Security Risk Identification and Red Teaming in Generative AI Systems.* arXiv:2410.02828, 2024.

## 十五、待导师确认的问题

1. 课题题名是否最终采用"基于多源证据分层的大模型应用安全评测与闭环补测方法研究"，是否需要进一步精简（备选见第一章）。
2. Agent 沙箱场景优先选择邮件、电商还是工单系统；是否需要支持工具调用日志的真实写入（影响 E4/E5 证据采集成本）。
3. 预期投稿目标是大创结题、中文核心、IEEE Access、还是 USENIX Security / NDSS / S&P 等英文会议（影响实验规模与统计严格度）。
4. 是否公开部分用例、复测脚本与人工标注 gold label 作为论文补充材料；是否需要数据脱敏审查。
5. 人工标注是否由项目成员完成，是否需要外部第二标注者；是否需要制定双人标注操作手册与 Cohen's κ 阈值（建议 ≥0.6）。
6. 是否在与 *A Coin Flip for Safety* / *When Scanners Lie* 的对比实验中，使用其公开 ReliableBench / JudgeStressTest 数据集，以保证 baseline 可比性。
7. E-level × Kill-chain 矩阵中 Stage=Persisted/Relayed 的实验需要多 Agent 链路支持，是否在 v1 实验范围内。
