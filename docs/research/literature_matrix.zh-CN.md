# 文献矩阵：LLM 应用安全评测、自动红队与 Agentic Testing

更新时间：2026-04-25

本文档用于判断“天鉴 · 衡”后续大创工程方向与论文方向。重点不是罗列文献，而是回答三个问题：

1. 哪些方向已经被强先例覆盖。
2. 哪些方向仍可结合现有项目形成差异化。
3. 后续工程应如何避开“重复造轮子”，转向可展示、可量化、可写论文的闭环。

## 1. 总体判断

当前领域已经从“手写 jailbreak prompt”进入三个阶段：

- 自动化攻击生成：自动搜索、改写、组合 jailbreak / red-teaming 策略。
- Agent / 工具调用安全：关注工具、状态、外部数据、MCP、RAG、搜索代理等新攻击面。
- 可信评测：开始质疑 LLM-as-a-Judge、ASR、单次成功率等指标的可靠性。

因此，本项目不宜主打“第一个自动红队 Agent”或“又一个 LLM 扫描器”。更稳的差异化方向是：

> 面向 LLM 应用的证据驱动自动安全测试 Agent：自动规划、执行、观察、补测，并用证据链而非单一 Judge 结论度量攻击成功。

## 2. 核心文献矩阵

| 类别 | 工作 | 对象 | 核心贡献 | 常用指标/证据 | 与本项目重合 | 暴露出的空位 | 对我们方向的启发 |
|---|---|---|---|---|---|---|---|
| LLM 安全扫描框架 | [garak](https://arxiv.org/abs/2406.11036) | LLM / 对话系统 | 结构化 probing，发现模型或对话系统弱点 | probe 结果、漏洞类别、模型弱点 | 与现有扫描平台高度相似 | 更偏模型/对话系统，不强调应用状态、副作用、证据仲裁 | 不要只做扫描器；要强调应用层证据链和自动补测 |
| LLM 红队框架 | [PyRIT](https://arxiv.org/abs/2410.02828) | GenAI 系统 | 模型无关、可组合、可扩展的红队工具包 | 风险识别、jailbreak、prompt flow | 与攻击编排、目标适配重合 | 更像工具框架，不直接解决结果可信度问题 | 可以参考“可组合架构”，但论文贡献不能只是框架 |
| 工程工具 | [Promptfoo Red Team](https://www.promptfoo.dev/docs/red-team/) | LLM 应用、RAG、Agent | 插件式红队测试、CI/CD、配置化测试 | 插件结果、风险类别、通过/失败 | 与平台化、报告化重合 | 商业/工程成熟；我们难靠“功能全”胜出 | 大创可参考体验；论文要避开“我也做了 Promptfoo” |
| 工程工具 | [DeepTeam](https://github.com/confident-ai/deepteam) | LLM 系统 | 开源 LLM red teaming 框架 | 攻击场景、评估器、风险输出 | 与模板攻击、评估流程重合 | 关注易用性和攻击覆盖，不突出证据层级 | 我们需突出“可信度”和“自适应补测” |
| Benchmark | [HarmBench](https://arxiv.org/abs/2402.04249) | 基础模型安全 | 标准化 red teaming 与拒答鲁棒性评测 | ASR、refusal、harmful compliance | 与 jailbreak 横评重合 | 更偏基础模型，不覆盖应用层链路 | 可作为 ASR 对比基线，不宜正面做“更强 HarmBench” |
| Benchmark | [JailbreakBench](https://openreview.net/pdf?id=urjPCYZt0I) | 基础模型 jailbreak | 开放 robustness benchmark，比较攻击与判别器 | ASR、judge / classifier、人类标签 | 与攻击成功判定重合 | 应用层“响应来源”和“后处理/工具副作用”不是重点 | 可借鉴 human label 与 judge 比较 |
| 自动攻击生成 | [TAP](https://arxiv.org/abs/2312.02119) | 黑盒 LLM | Tree-of-Attacks with Pruning，自动迭代生成 jailbreak | ASR、查询次数、攻击深度 | 本项目已支持 TAP 类高级攻击 | 自动 jailbreak 已有强先例 | 不要把 novelty 放在攻击 prompt 生成 |
| 自动攻击生成 | [AutoDAN-Turbo](https://arxiv.org/abs/2410.05295) | 黑盒 LLM | Lifelong agent 自动探索 jailbreak 策略 | ASR、策略发现能力 | 与“自动攻击 Agent”概念重合 | 它在自动策略探索上很强 | 我们应转向“测试编排与证据仲裁”，不是比攻击成功率 |
| 自动攻击生成 | [Auto-RT](https://arxiv.org/abs/2501.01830) | LLM red-teaming | 强化学习探索复杂攻击策略，提高发现效率 | ASR、检测速度、策略优化收益 | 与自适应攻击调度部分重合 | 主打策略搜索和攻击效率 | 我们可借鉴“动态探索”，但应把目标变成“可信评测闭环” |
| 自动红队系统 | [AutoRedTeamer](https://arxiv.org/abs/2503.15754) | LLM | 端到端自动红队，多 Agent + 记忆指导攻击选择 + 新攻击集成 | ASR、成本、攻击多样性 | 与“平台 Agent 化”高度相关 | 已覆盖“自动红队 Agent”大叙事 | 不能宣称自动化本身新；要强调应用层证据、补测、Judge 纠错 |
| 安全 Agent 工作流 | [Co-RedTeam](https://arxiv.org/abs/2602.02164) | 传统安全漏洞发现/利用 | 多 Agent 模拟红队流程，发现、利用、验证、记忆复用 | 漏洞检测率、利用成功率、ablation | 与计划-执行-验证循环重合 | 对象偏传统漏洞，不是 LLM 应用行为评测 | 可借鉴 plan-execute-validate-refine 架构 |
| Agent 安全评测 | [AgentDojo](https://arxiv.org/abs/2406.13352) | 工具调用型 LLM Agent | 动态环境，评测 prompt injection 攻防，97 任务、629 安全用例 | 攻击成功、任务成功、攻防效果 | 与 Agent 靶场/间接注入重合 | Benchmark 很强，直接做 Agent 靶场难出新 | Agent 靶场可做演示，不宜作为唯一创新 |
| Agent 任务可靠性 | [tau-bench](https://arxiv.org/abs/2406.12045) | 工具 Agent 与用户交互 | 用最终数据库状态评估任务完成，提出 pass^k 可靠性指标 | final DB state、pass^k | 与状态验证和 probe 思路相关 | 不主打安全攻击证据分级 | 支持我们用状态变化验证，而不是只看文本 |
| Agent 风险评估 | [ToolEmu](https://openreview.net/forum?id=GEcwtMk1uA) | LM Agent 工具使用 | 用 LM 模拟工具执行，规模化发现 Agent 高风险场景 | 风险失败率、人类验证、风险类别 | 与工具/沙盒/自动评估相关 | 使用 LM-emulated sandbox，真实副作用证据有限 | 我们可强调真实适配器/状态/probe，而非纯模拟 |
| Agent 有害任务 | [AgentHarm](https://arxiv.org/abs/2410.09024) | LLM Agent misuse | 110 个恶意 agentic tasks，评测拒绝有害多步任务能力 | harmful task success、refusal、task completion | 与 Agent 安全任务重合 | 聚焦恶意任务和模型拒绝，不是应用层证据链 | 可作为 agentic risk 背景，不做同类 benchmark |
| MCP / 工具投毒 | [AutoMalTool](https://arxiv.org/abs/2509.21011) | MCP-based Agent | 自动生成恶意 MCP 工具，对 Agent 做系统性红队 | 攻击成功、检测绕过 | 与工具生态安全相关 | 方向专门且偏 MCP 工具投毒 | 若后续接 MCP，可作为扩展；当前不宜作为主线 |
| 搜索代理红队 | [SafeSearch](https://arxiv.org/abs/2509.23694) | LLM Search Agent | 自动生成 300 个搜索代理安全用例，评测搜索结果误导 | ASR、风险类别、模型/架构对比 | 与自动红队 + 应用场景重合 | 场景限定为 search agent | 说明“垂直应用场景 + 自动红队”是可发表路线 |
| Agent 静态审计 | [Agent Audit](https://arxiv.org/abs/2603.22853) | LLM Agent 代码与部署 | 代码/配置/凭据/权限风险分析，输出 JSON/SARIF | recall、false positives、扫描时间 | 与平台安全审计不同，偏静态分析 | 不做动态黑盒行为评测 | 我们可避免做静态 SAST，保留黑盒动态定位 |
| Agent 安全 SoK | [Attack Surface of Agentic AI](https://arxiv.org/abs/2603.22928) | Agentic AI | 梳理工具、RAG、多 Agent、 autonomy 攻击面，提出 Unsafe Action Rate 等指标 | taxonomy、Unsafe Action Rate、Privilege Escalation Distance | 与风险分类和指标设计相关 | 是综述，不提供平台闭环 | 可引用其指标语言，为我们的 Evidence-Verified ASR 背书 |
| Agent 安全综述 | [Attack and Defense Landscape of Agentic AI](https://arxiv.org/abs/2603.11088) | AI Agent 系统 | 系统化综述 agent security 风险、攻击、防御，USENIX Security 2026 | taxonomy、case studies、open challenges | 与背景综述强相关 | 综述已覆盖大面，不能泛泛写“Agent 安全很重要” | 我们需缩到具体方法：证据反馈自动测试 |
| Judge 可靠性 | [Know Thy Judge](https://arxiv.org/abs/2503.04474) | LLM safety judges | 研究 judge 对 prompt、分布迁移、攻击的鲁棒性 | FNR、FPR、judge 被攻击成功率 | 与 Judge 校准高度相关 | 已证明 judge 不可靠 | 支持我们把 Judge 降级为一层证据，而非最终裁判 |
| Judge 鲁棒性 | [RobustJudge](https://arxiv.org/abs/2506.09443) | LLM-as-a-Judge 系统 | 自动评估 judge 鲁棒性，15 攻击、7 防御、12 模型 | 攻击成功、模板敏感性、部署漏洞 | 与裁判安全性相关 | 更关注攻击 judge 本身 | 我们可做轻量校准，而非完整 judge 攻防 |
| Judge SoK | [Security in LLM-as-a-Judge](https://arxiv.org/abs/2603.29403) | LLM-as-a-Judge | 2020-2026 相关工作 SoK，整理安全角色和风险 | taxonomy、open challenges | 与可信评测理论相关 | 已系统化 judge 风险 | 强化“不能只靠 Judge”的论证 |
| 标准/框架 | [OWASP LLM Top 10 2025](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) | LLM 应用风险 | Prompt Injection、Sensitive Disclosure、Excessive Agency 等风险分类 | 风险类别、缓解建议 | 与项目风险分类一致 | 是治理框架，不是实验协议 | 可作为风险分类来源 |
| 标准/框架 | [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/) | Agentic AI | 面向自治 Agent 的风险与缓解，行业共识快速形成 | 风险类别、治理建议 | 与 Agentic 方向强相关 | 不是自动测试实现 | 可作为工程测试覆盖目标 |

## 3. 方向风险分析

### 3.1 不建议作为主创新的方向

#### 自动生成更强 jailbreak

风险很高。TAP、AutoDAN-Turbo、Auto-RT、AutoRedTeamer 已经把“自动攻击生成”和“策略搜索”做得很深。本项目如果主打攻击成功率，很容易被审稿人要求和这些方法正面对比，成本高且胜算低。

可保留为工程能力：

- 调用已有攻击引擎；
- 用作 AutoTest Agent 的可选策略；
- 不把“攻击更强”作为论文主贡献。

#### 又一个 LLM 漏洞扫描器

garak、PyRIT、Promptfoo、DeepTeam 已经覆盖了开源工具和工程实践。若只说“支持多模型、多攻击模板、多报告”，创新性不足。

可保留为工程主干：

- 大创展示需要完整平台；
- 论文中作为系统实现，而非唯一贡献。

#### 大型 Agent benchmark

AgentDojo、tau-bench、ToolEmu、AgentHarm 都很强，数据规模和学术影响力高。我们短期做一个“邮件/电商 Agent 靶场”可以演示，但不宜宣称是通用 Agent benchmark。

可保留为验证场景：

- 一个最小 Agent 沙箱；
- 用于展示工具调用和状态验证；
- 服务 Evidence Chain，而不是单独成为主线。

### 3.2 仍有机会的方向

#### 证据驱动的自动测试编排

现有自动红队更多关注攻击生成、攻击多样性或漏洞利用成功率。本项目可以关注测试闭环：

```text
目标理解 -> 测试计划 -> 攻击执行 -> 结果观察 -> 证据仲裁 -> 自动补测 -> 报告生成
```

关键点不是“Agent 会自动攻击”，而是“Agent 会根据证据强度决定下一步测试是否充分”。

#### 可信 ASR 与 Evidence Chain

现有 ASR 往往依赖最终文本或 LLM Judge。Agent 场景和真实应用场景中，这会混淆：

- 模型复述攻击内容；
- 模型声称执行操作；
- Judge 误判；
- 规则强证据命中；
- 工具调用发生；
- 业务状态真实变化。

本项目已有 `blackbox_outcome`、`behavior_flags`、`business_verification_status`、`probe_summary`、`judge_snapshot` 等字段，适合把结果拆成证据等级。

#### Judge 可靠性校准作为辅助创新

Know Thy Judge、RobustJudge 和 SoK 已经说明 LLM-as-a-Judge 不稳定。我们不需要再做完整 judge 攻防研究，而是把它落到平台实践：

- Judge 只是证据链一环；
- 低置信度结果进入补测或人工复核；
- quartet control 用于发现 judge 将引用攻击文本误判为执行；
- 人工 gold label 用于校准 precision、recall、FPR。

## 4. 候选工程/论文方向评分

评分范围：1-5，分数越高越好。`风险` 分数越高代表越容易撞已有工作。

| 候选方向 | 工程可行性 | 大创展示性 | 论文潜力 | 与现有项目贴合 | 撞车风险 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| 通用 LLM 安全扫描平台 | 5 | 4 | 2 | 5 | 5 | 可做底座，不宜做主创新 |
| 自动 jailbreak 生成 Agent | 3 | 4 | 3 | 3 | 5 | 不建议主攻，已有强先例 |
| Agent 靶场 / 沙盒 benchmark | 3 | 5 | 3 | 3 | 4 | 可做演示场景，不宜做大 benchmark |
| LLM-as-a-Judge 可靠性研究 | 4 | 3 | 4 | 4 | 4 | 可做论文副线，需要人工标注 |
| Evidence-Verified ASR | 4 | 4 | 4 | 5 | 2 | 推荐作为论文核心指标 |
| 证据驱动自动测试 Agent | 4 | 5 | 4 | 5 | 3 | 推荐作为大创工程主线 |
| MCP 工具投毒自动红队 | 2 | 4 | 4 | 2 | 4 | 有前沿性，但偏离当前项目 |
| 搜索 Agent / RAG 垂直红队 | 3 | 4 | 4 | 3 | 3 | 可作为后续垂直场景 |
| Agent 应用静态审计 | 3 | 3 | 3 | 2 | 3 | 与当前黑盒平台方向不一致 |

当前推荐组合：

> 工程主线：证据驱动自动测试 Agent  
> 论文主线：Evidence-Verified ASR / 可信证据链  
> 展示场景：一个最小 Agent 或 RAG/客服应用靶场  
> 辅助章节：Judge 校准与 quartet 误判分析

## 5. 推荐项目定位

### 不建议这样表述

- “提出一种新的自动 jailbreak 算法”
- “提出第一个自动红队 Agent”
- “构建通用 LLM 安全扫描器”
- “构建新的 Agent benchmark”

这些表述都容易被已有工作压住。

### 建议这样表述

> 本项目面向真实 LLM 应用安全测试，提出一种证据驱动的 Agentic 黑盒评测流程。系统中的 AutoTest Agent 能根据目标特征规划测试、调用攻击引擎、观察中间结果，并在证据不足时自动触发复测、四元对照、规则验证或人工复核，最终输出分层可信的攻击成功率和可审计报告。

英文方向可暂定为：

> Evidence-Guided Agentic Security Testing for LLM Applications

或：

> Evidence-Verified Security Evaluation for LLM Applications with Agentic Test Orchestration

## 6. 可形成的研究问题

### RQ1：自动测试 Agent 是否能提升测试覆盖率？

比较：

- 静态模板扫描；
- 人工选择攻击类别；
- Agentic planning + adaptive retest。

可用指标：

- 覆盖的风险类别数量；
- 触发有效结果的 case 数；
- 单位 token / 单位查询下发现的 reportable findings；
- not_evaluable 占比。

### RQ2：证据驱动补测是否能降低误判？

比较：

- Judge-only ASR；
- Rule-Verified ASR；
- Evidence-Verified ASR；
- Human-Verified ASR。

可用指标：

- false positive rate；
- manual overturn rate；
- judge precision / recall；
- quartet false positive count。

### RQ3：Evidence-Verified ASR 与传统 ASR 差多少？

假设：

> 传统 ASR 会高估真实应用风险，因为它把文本声称、攻击讨论和真实副作用混在一起。

可用指标：

- Raw ASR；
- Judge ASR；
- Text-Claim ASR；
- Tool-Observed ASR；
- Probe-Verified ASR。

### RQ4：自动测试 Agent 的补测决策是否有收益？

比较：

- 不补测；
- 低置信度复测；
- quartet 对照；
- canary / probe 验证。

可用指标：

- 误判下降；
- 强证据发现数提升；
- 额外查询成本；
- 每个 finding 的平均证据等级。

## 7. 对现有项目的映射

| 研究/工程需要 | 当前已有基础 | 还缺什么 |
|---|---|---|
| 目标适配 | `adapter_executor`、custom/openai-compatible target | 目标画像与自动风险推荐 |
| 攻击执行 | attack templates、PAIR、TAP、Crescendo、Mutation、ICE | Agentic strategy selector |
| 结构化判定 | `blackbox_outcome`、`behavior_flags` | 统一 Evidence Level |
| 证据验证 | canary、probe、business verification | 状态 diff / probe 结果统一入报告 |
| 四元对照 | quartet schema、control variants | 与 AutoTest 补测策略绑定 |
| Judge 校准 | judge calibration API / metrics | gold label 流程和抽样策略 |
| 报告 | report generator、frontend report page | 自动结论、指标矩阵、证据时间线 |
| 大创展示 | 前后端平台已有 | 一条完整 AutoTest Agent 演示流 |

## 8. 后续阅读优先级

### 必读

1. AutoRedTeamer：确认“自动红队 Agent”已有多强，避免重复。
2. AgentDojo：理解 Agent 安全评测和间接注入环境。
3. tau-bench：学习最终状态 / 数据库状态评估思想。
4. Know Thy Judge：支撑 Judge 不应作为唯一裁判。
5. garak / PyRIT：了解开源扫描框架边界。

### 次读

1. Co-RedTeam：学习 plan-execute-validate-refine 和记忆复用。
2. ToolEmu：学习工具风险场景与自动安全评估。
3. SafeSearch：学习垂直应用自动红队写法。
4. Agent Audit：了解 agent 应用静态审计，不作为当前主线。
5. OWASP Agentic Top 10：作为 agentic 风险分类来源。

## 9. 暂定结论

本项目的最佳落点不是“更强攻击算法”，也不是“更大 benchmark”，而是：

> 将现有 LLM 安全扫描平台升级为证据驱动的 AutoTest Agent，使安全评测从静态模板执行变成可规划、可观察、可补测、可审计的闭环。

后续工程先做一个小闭环：

```text
输入目标配置
-> 自动生成测试计划
-> 选择攻击与对照用例
-> 执行扫描
-> 观察证据强度
-> 自动补测 / quartet / canary / probe
-> 输出 Evidence-Verified ASR 和报告
```

这条线既能服务大创展示，也能自然延展到中文论文或 IEEE Access 风格的系统论文。
