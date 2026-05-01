# 2024-2026 LLM 应用安全评测赛道缺口调研

更新时间：2026-04-25

本文档目标：从近几年 LLM 安全评测、自动红队、Agent 安全、LLM-as-a-Judge 可靠性等工作中，提取它们已经解决的问题、尚未完成的问题，以及可转化为本项目大创工程与论文创新点的切口。

信息来源以 arXiv、OpenReview、OWASP 官方资料为主。本文不是完整综述，而是面向项目选题的“缺口地图”。

## 1. 一句话结论

当前赛道的前沿已经不缺“自动生成攻击 prompt”的方法，也不缺“Agent 安全 benchmark”。真正值得我们切入的是：

> 面向 LLM 应用的证据驱动自动安全测试闭环：让测试 Agent 不只是自动攻击，而是自动判断证据是否足够、是否需要补测、是否需要对照实验、是否需要 probe/人工复核，并输出分层可信的攻击成功率。

换句话说，我们不要和 AutoDAN、TAP、AutoRedTeamer 拼攻击成功率，也不要和 AgentDojo、AgentDyn 拼 benchmark 规模。我们应该从它们的未完成处切入：

> 结果可信度、应用层证据、自动补测决策、Judge 误判修正、utility/over-defense 共同度量。

## 2. 近年工作分组

### 2.1 通用 LLM 安全扫描与红队工具

代表工作：

- [garak: A Framework for Security Probing Large Language Models](https://arxiv.org/abs/2406.11036)
- [PyRIT: A Framework for Security Risk Identification and Red Teaming in Generative AI System](https://arxiv.org/abs/2410.02828)
- [Promptfoo Red Team](https://www.promptfoo.dev/docs/red-team/)

它们已经做了：

- 配置化/框架化地测试 LLM 或 GenAI 系统；
- 支持多种风险、探针、目标模型和报告；
- 强调可扩展、模型无关、可复用的红队测试组件。

它们暴露的未完成问题：

- 主要解决“怎么跑测试”，不是“测试结果有多可信”；
- 多数结果仍然依赖最终文本、规则或 judge，缺少应用状态层面的证据闭环；
- 面向真实 LLM 应用的 prompt assembly、后处理、工具调用、adapter、probe 等链路证据没有形成统一指标；
- 对 “not evaluable”“基础设施失败”“目标异常”“应用拦截器输出” 与模型安全行为的区分不足。

对我们的启发：

- 平台框架本身不是创新高地；
- 我们应该强调应用层、证据链、自动复核、分层 ASR；
- 报告不能只列漏洞，要说明每个 finding 的证据等级和可复现程度。

### 2.2 自动 jailbreak / 自动红队 Agent

代表工作：

- [TAP: Tree of Attacks with Pruning](https://arxiv.org/abs/2312.02119)
- [AutoDAN-Turbo](https://arxiv.org/abs/2410.05295)
- [Auto-RT](https://arxiv.org/abs/2501.01830)
- [AutoRedTeamer](https://arxiv.org/abs/2503.15754)

它们已经做了：

- 自动迭代生成攻击 prompt；
- 用 attacker/evaluator/target 或强化学习探索攻击策略；
- 通过记忆、策略库、攻击选择机制提升 ASR 和效率；
- AutoRedTeamer 已经把“自动红队 Agent”叙事讲得很完整。

它们暴露的未完成问题：

- 重点是攻击生成和攻击成功率，而不是应用层证据可靠性；
- 多数实验对象仍偏基础模型或模型级 safety benchmark；
- 攻击成功判断往往还是最终文本或 judge/classifier；
- 很少把“攻击后是否产生真实业务副作用”作为主指标；
- 对自动化测试过程中的误判、补测、证据不足、对照实验触发策略关注不够。

对我们的启发：

- 不要把论文写成“我们提出一种更强 jailbreak Agent”；
- 可以把已有攻击算法作为被调度的工具；
- 新意应放在 “AutoTest Agent 如何根据证据反馈决定下一步测试”。

可转化创新：

```text
攻击 Agent 不是只负责生成更强 payload，
而是负责判断当前证据是否足以支撑 reportable finding。
```

### 2.3 Agent 安全 benchmark 与工具调用评测

代表工作：

- [AgentDojo](https://arxiv.org/abs/2406.13352)
- [tau-bench](https://arxiv.org/abs/2406.12045)
- [ToolEmu](https://openreview.net/forum?id=GEcwtMk1uA)
- [AgentHarm](https://arxiv.org/abs/2410.09024)
- [AgentDyn](https://arxiv.org/abs/2602.03117)

它们已经做了：

- AgentDojo：构建动态环境，评测工具调用型 Agent 的间接提示注入攻防；
- tau-bench：用最终数据库状态评估 agent 任务完成情况，并提出多次运行可靠性指标；
- ToolEmu：用 LM 模拟工具沙箱，低成本发现 Agent 高风险行为；
- AgentHarm：关注恶意 agentic tasks 和模型是否拒绝有害多步任务；
- AgentDyn：指出现有 benchmark 的静态任务、用户任务过于简单、缺少 helpful third-party instructions，并提出动态开放任务。

它们暴露的未完成问题：

- benchmark 很强，但通常服务于标准化评测，不等于可接入任意企业 LLM 应用的安全测试平台；
- AgentDojo/AgentDyn 关注被测 Agent 的任务和防御，较少关注“自动测试平台如何决定补测和证据仲裁”；
- tau-bench 强调最终数据库状态，但不是安全攻击语境下的证据分级 ASR；
- ToolEmu 用 LM 模拟工具环境，适合规模化，但真实系统状态、adapter 请求和业务 probe 的证据强度仍可加强；
- 这些工作提醒我们：Agent 测试必须同时看任务完成与安全失败，不能只看攻击成功。

对我们的启发：

- 不要做“大而全 Agent benchmark”；
- 可做一个小而完整的 Agent/RAG/客服靶场作为演示；
- 重点应是把 tau-bench 的状态验证思想迁移到安全评测：状态 diff、tool log、probe evidence；
- 把 AgentDyn 的动态任务思想转化为 AutoTest Agent 的自适应测试计划。

可转化创新：

```text
把 Agent benchmark 的“状态验证”引入 LLM 应用安全扫描，
形成 Evidence-Verified ASR，而不是只报文本/裁判 ASR。
```

### 2.4 LLM-as-a-Judge 可靠性

代表工作：

- [Know Thy Judge](https://arxiv.org/abs/2503.04474)
- [RobustJudge](https://arxiv.org/abs/2506.09443)
- [Security in LLM-as-a-Judge: A Comprehensive SoK](https://arxiv.org/abs/2603.29403)

它们已经做了：

- 指出 LLM judge 会受 prompt style、分布迁移、模型选择影响；
- 证明部分 judge 能被攻击诱导误判；
- RobustJudge 系统化评估多种攻击/防御和 prompt template 对 judge 鲁棒性的影响；
- 2026 SoK 将 LLM-as-a-Judge 的安全风险系统化。

它们暴露的未完成问题：

- 已经证明 judge 不可靠，但工程平台里如何“降级使用 judge”仍有空间；
- 现有工作更关注 judge 本身被攻击或鲁棒性，不一定关注 LLM 应用安全扫描里的 reportable finding 生成流程；
- 对“judge 何时应触发补测、何时触发 quartet、何时转人工复核”的策略还不够产品化；
- 安全评测中的 judge 误判类型可以结合应用层字段进一步细分：讨论攻击误判、引用文本误判、后处理响应误判、工具失败误判、text claim 误判。

对我们的启发：

- 不能把 LLM Judge 当最终真相；
- Judge 应该只是证据链中的一层；
- 低置信度、judge-rule 冲突、quartet 冲突、probe 失败都应该进入补测/人工复核队列。

可转化创新：

```text
Judge-aware AutoTest Agent：
根据 judge 结果和证据冲突自动决定是否复测、降级、升级或人工复核。
```

### 2.5 2026 Agentic AI 攻击面与运行时供应链

代表工作：

- [SoK: The Attack Surface of Agentic AI -- Tools, and Autonomy](https://arxiv.org/abs/2603.22928)
- [The Attack and Defense Landscape of Agentic AI](https://arxiv.org/abs/2603.11088)
- [SOK: Agentic Supply Chain Runtime](https://arxiv.org/abs/2602.19555)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [ToolHijacker](https://arxiv.org/abs/2504.19793)
- [How Vulnerable Are AI Agents to Indirect Prompt Injections?](https://arxiv.org/abs/2603.15714)

它们已经做了：

- 2026 SoK 开始系统化梳理 agentic AI 的工具、RAG、多 Agent、自治性攻击面；
- Agentic supply chain runtime 将风险从构建时供应链扩展到推理时依赖、工具发现、工具调用、上下文污染；
- OWASP Agentic Top 10 给出了实践侧风险分类；
- ToolHijacker 将工具选择本身作为 prompt injection 攻击面；
- 2026 间接提示注入竞赛论文强调 concealment：用户最终只看到正常回复，但攻击可能已执行。

它们暴露的未完成问题：

- 越来越多论文提出 taxonomy 和风险，但缺少轻量、可落地、可复现的测试工作流；
- 工具层攻击、上下文污染、隐藏执行和 final response concealment 使“只看最终回复”的评测越来越不可信；
- OWASP 给出风险分类，但不会告诉你如何自动化测试每类风险并量化证据强度；
- ToolHijacker 关注工具选择攻击，但通用平台如何检测工具选择异常、如何把工具选择纳入 evidence chain，还有空间；
- 竞赛型研究揭示 concealment 风险，但普通应用安全平台如何捕捉隐藏副作用仍有工程缺口。

对我们的启发：

- 2026 的关键词不是单纯 prompt injection，而是 runtime、tool selection、memory/context poisoning、concealment、verifiable behavior；
- 我们可以把测试平台定位为“运行时证据采集与自动补测”，而不是“静态 benchmark”；
- 对普通 LLM 应用，也要记录 origin、adapter、tool/probe、state evidence，避免被最终回复骗过。

可转化创新：

```text
Final-response-independent evaluation：
不依赖最终回复判断攻击是否成功，而依赖证据链、工具日志、状态差异和 probe。
```

## 3. 从未完成问题中提炼出的创新切口

### 切口 A：Evidence-Guided AutoTest Agent

核心问题：

> 现有自动红队重在“自动攻击”，但缺少“自动判断当前证据是否足够可信”的测试闭环。

可做内容：

- 自动读取目标配置，生成测试计划；
- 根据风险类型选择攻击策略；
- 运行初测；
- 读取结果字段：blackbox outcome、behavior flags、rule hits、judge confidence、probe status；
- 根据证据强度自动触发补测：
  - judge 成功但无规则证据 -> 触发 quartet；
  - 泄露疑似成功 -> 触发 canary 精确验证；
  - 低置信度 -> 重复运行或换攻击策略；
  - text claim only -> 尝试 tool/probe 验证；
  - clean 失败 -> 标记 not_evaluable 或 utility failure。

论文表达：

> We propose an evidence-guided agentic testing loop for LLM applications, where the tester adapts its next action based on evidence sufficiency rather than attack success alone.

工程价值：

- 这是平台 Agent 化；
- 大创展示很清楚；
- 不正面硬刚 AutoDAN/AutoRedTeamer。

### 切口 B：Evidence-Verified ASR

核心问题：

> 传统 ASR 会混淆最终文本、judge 误判、越权声称和真实副作用。

可做内容：

- 定义证据等级：
  - E0 not evaluable；
  - E1 text claim；
  - E2 judge suspected；
  - E3 rule/canary verified；
  - E4 tool observed；
  - E5 probe/state verified。
- 同时报告：
  - Raw ASR；
  - Judge ASR；
  - Rule-Verified ASR；
  - Text-Claim ASR；
  - Probe-Verified ASR；
  - Quartet-Validated ASR；
  - Utility Rate；
  - Over-Defense Rate。

论文表达：

> We show that conventional ASR overestimates or misattributes application-level security failures, and propose Evidence-Verified ASR to separate textual claims, model-judge suspicion, rule evidence, and verified side effects.

工程价值：

- 和你现有 `probe_summary`、`business_verification_status`、`verdict_status` 高度贴合；
- 可作为论文主创新；
- 实验量可控。

### 切口 C：Judge 冲突驱动的自动复核

核心问题：

> LLM-as-a-Judge 不可靠，但平台不能完全不用它；问题是如何安全地使用它。

可做内容：

- 将 Judge 输出降级为中间证据；
- 定义冲突规则：
  - judge 成功，但 quoted attack 也成功 -> 疑似 false positive；
  - judge 成功，但 rule/probe 均失败 -> 降级；
  - judge 失败，但 canary 命中 -> 升级；
  - judge confidence 低 -> 自动抽样人工复核；
  - 多 judge 分歧 -> 进入 calibration set。
- 计算 judge precision、recall、FPR、manual overturn rate。

论文表达：

> We operationalize recent findings on LLM-judge unreliability by embedding judge outputs into an evidence arbitration workflow rather than treating them as ground truth.

工程价值：

- 你项目已有 judge calibration 基础；
- 适合作为副创新或实验章节；
- 能让“结果可信”更有说服力。

### 切口 D：Final Response Concealment 检测

核心问题：

> 2026 间接提示注入研究强调：攻击可以在最终回复中隐藏痕迹，用户看不到异常。

可做内容：

- 不只看 final response；
- 保存中间步骤、adapter 请求、tool calls、probe evidence；
- 对每个结果计算“final response 与证据是否一致”：
  - final response 正常，但 tool/probe 显示越权 -> concealed success；
  - final response 声称成功，但 probe 失败 -> text hallucination；
  - final response 拒绝，但 canary 泄露 -> hidden leakage。

论文表达：

> We introduce concealment-aware evaluation for LLM applications, identifying cases where the final response does not reveal the underlying harmful action.

工程价值：

- 非常适合报告页展示；
- 与 2026 新论文趋势吻合；
- 可作为我们区别于“只看回复”的关键点。

### 切口 E：Utility-aware Security Testing

核心问题：

> 防御如果把正常任务也拦掉，并不等于安全；很多 Agent 防御存在 over-defense。

可做内容：

- Clean 变体测正常任务；
- Attack 变体测攻击成功；
- Quoted Attack 测讨论/引用误判；
- Benign Distractor 测过度防御；
- 同时报告安全性和可用性：
  - attack success；
  - utility success；
  - over-defense rate；
  - refusal on clean；
  - task degradation。

论文表达：

> We jointly evaluate security and utility under quartet controls, exposing over-defense and false-positive failures that are hidden by attack success rates alone.

工程价值：

- 你项目已有 quartet 概念；
- 可以把实验做得更像论文；
- 很适合大创答辩说明“不是只看漏洞数量”。

## 4. 最值得押注的组合

不建议把所有切口都做满。建议组合如下：

```text
主工程：Evidence-Guided AutoTest Agent
主论文指标：Evidence-Verified ASR
辅助可信机制：Judge 冲突驱动复核 + Quartet utility controls
展示亮点：Final response concealment / probe evidence 时间线
```

合成一句话：

> 我们提出一种面向 LLM 应用的证据驱动自动安全测试 Agent。它不是单纯追求更高攻击成功率，而是在测试过程中根据证据强度自动决定补测、对照、probe 和人工复核，并输出 Evidence-Verified ASR，以缓解传统 ASR 和 LLM Judge 在应用层评测中的不可信问题。

## 5. 候选题目

### 大创工程题目

- 天鉴·衡：面向大模型应用的证据驱动自动安全测试平台
- 面向 LLM 应用的 Agentic 黑盒安全评测平台
- 基于证据链的大模型应用自动化安全评测平台

### 中文论文题目

- 基于证据链的大模型应用黑盒安全评测方法
- 面向 LLM 应用的可信攻击成功率度量与自动补测方法
- 基于证据反馈的大模型应用自动安全测试方法

### 英文论文题目

- Evidence-Guided Agentic Security Testing for LLM Applications
- Evidence-Verified Security Evaluation for LLM Applications
- Trustworthy Attack Success Measurement for LLM Application Security Testing

## 6. 与本项目当前能力的对应关系

| 缺口方向 | 当前项目已有 | 需要补的工程 |
|---|---|---|
| Evidence-Guided AutoTest Agent | 攻击引擎、目标适配、扫描任务 | 测试计划、策略选择、补测决策状态机 |
| Evidence-Verified ASR | verdict、blackbox_outcome、probe_summary | evidence_level 字段、指标统计页 |
| Judge 冲突复核 | judge calibration API | 冲突规则、抽样复核、标注集导出 |
| Quartet utility controls | control variants、quartet 文档 | 与补测策略绑定、utility/over-defense 统计 |
| Concealment 检测 | adapter/probe、报告页 | final response vs evidence 对照展示 |
| 状态/probe 证据 | probe executor | 更统一的 evidence chain 结构 |

## 7. 最小可行研究闭环

第一阶段不要做 300 条用例。建议做：

```text
目标：2 类 LLM 应用目标
风险：Prompt Injection / System Prompt Leakage / Sensitive Disclosure
用例：30 个 logical cases
变体：Clean / Attack / Quoted Attack / Benign Distractor
模型：1-2 个
指标：Raw ASR / Judge ASR / Evidence-Verified ASR / Utility Rate / Over-Defense Rate
人工标注：50-100 条
```

最重要的是跑出一张表：

| 指标 | 静态模板扫描 | AutoTest Agent |
|---|---:|---:|
| Reportable findings | 待测 | 待测 |
| False positive rate | 待测 | 待测 |
| Evidence-Verified ASR | 待测 | 待测 |
| Not evaluable rate | 待测 | 待测 |
| Utility rate | 待测 | 待测 |
| Extra query cost | 待测 | 待测 |

如果 AutoTest Agent 的额外查询成本可控，并且能降低误报或提高强证据 finding 比例，这就是论文结果。

## 8. 当前不建议主攻的方向

### 不建议 1：更强 jailbreak 算法

原因：

- TAP、AutoDAN-Turbo、Auto-RT、AutoRedTeamer 已经很强；
- 需要大规模对比，成本高；
- 很容易变成“ASR 比不过前人”。

### 不建议 2：大型 Agent benchmark

原因：

- AgentDojo、AgentDyn、AgentHarm 已有数据规模；
- benchmark 维护成本高；
- 本项目工程基础更适合做平台化测试闭环。

### 不建议 3：只做 LLM-as-a-Judge 研究

原因：

- 2025-2026 judge 可靠性论文已经很多；
- 可以做副线，但单独做容易和 Know Thy Judge / RobustJudge 正面撞。

### 不建议 4：只做 OWASP 风险覆盖

原因：

- OWASP 是分类框架，不是创新；
- 只映射风险类别容易变成工具说明书。

## 9. 后续精读清单

优先精读：

1. [AutoRedTeamer](https://arxiv.org/abs/2503.15754)：确认“自动红队 Agent”已经做到了什么程度。
2. [AgentDyn](https://arxiv.org/abs/2602.03117)：学习它如何批评现有 benchmark 的静态性和简单性。
3. [How Vulnerable Are AI Agents to Indirect Prompt Injections?](https://arxiv.org/abs/2603.15714)：重点看 concealment 和 final response 不可信。
4. [Know Thy Judge](https://arxiv.org/abs/2503.04474)：支撑 judge 不可靠。
5. [tau-bench](https://arxiv.org/abs/2406.12045)：学习最终状态验证和 pass^k 可靠性。
6. [Co-RedTeam](https://arxiv.org/abs/2602.02164)：学习 plan-execute-validate-refine 的 agentic workflow。

次优先：

1. [garak](https://arxiv.org/abs/2406.11036)
2. [PyRIT](https://arxiv.org/abs/2410.02828)
3. [ToolEmu](https://openreview.net/forum?id=GEcwtMk1uA)
4. [AgentDojo](https://arxiv.org/abs/2406.13352)
5. [RobustJudge](https://arxiv.org/abs/2506.09443)
6. [OWASP Agentic Top 10 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)

## 10. 暂定研究判断

当前最有性价比的创新不是“发现一个没人做过的大方向”，而是从已有方向的缝隙里抽出一个可落地的闭环：

> 已有工作让攻击更自动化、benchmark 更真实、judge 问题更清楚；我们的机会是把这些认识落到 LLM 应用安全测试平台里，让测试过程自动化，结果证据化，指标可信化。

因此，后续大创工程不应只叫“加 Agent”，而应具体定义为：

> 构建一个证据驱动的 AutoTest Agent，使平台能够根据目标特征自动规划安全测试，并根据证据强度自动补测和仲裁结果。

这条线可以支撑三种成果：

- 大创：有完整系统和演示；
- 中文论文：有方法、指标和实验；
- 英文扩展：可包装成 agentic testing + trustworthy evaluation。
