<!-- markdownlint-disable MD041 MD033 -->
<div align="center">

# Evidence-Ladder

### 面向大模型应用的多源证据分层安全评测框架
### Multi-Source Evidence-Stratified Evaluation for LLM Application Security

*基于多源证据分层（E0–E5）与冲突驱动闭环补测的可信攻击成功率度量框架。*  
***Beyond LLM-as-a-Judge.***

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Status: research-preview](https://img.shields.io/badge/status-research--preview-orange.svg)](#七项目状态)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LLM Application Security](https://img.shields.io/badge/scope-LLM%20applications-7c3aed.svg)](#一项目动机)

[English README](./README.en.md) · [评测协议](./docs/evaluation_protocol.md)

</div>

---

## 一、项目动机

近一年内，多项研究从不同角度指出：在 LLM 安全评测中，**单一来源的攻击成功率不可靠**——

- ***A Coin Flip for Safety*** (arXiv:2603.06594, 2026)：6642 条人工标注证明 LLM-as-a-Judge 在对抗性分布下接近随机，许多"高 ASR"攻击实际利用的是 judge false positive。
- ***When Scanners Lie*** (arXiv:2603.14633, 2026)：开源扫描器（garak）25 个攻击类别中 22 个评测器不稳定，ASR 漂移可达 ±33%。
- ***Kill-Chain Canaries*** (arXiv:2603.28013, 2026)：多 Agent 系统安全评测必须按攻击传播阶段（Exposed → Persisted → Relayed → Executed）分解。

上述工作主要关注基础模型层面的裁判可靠性，**尚未充分覆盖 LLM 应用层评测中的额外混淆因素**：prompt 拼装模板、检索内容、后处理、工具调用、业务状态变化。

**Evidence-Ladder** 面向真实部署的 LLM 应用提供一种黑盒安全评测框架，把"攻击是否成功"问题转化为：

> *在何种证据强度下、在攻击传播链的哪个阶段被确认？*

---

## 二、方法概览

### 2.1 多源证据分层（E0–E5）

将攻击结果按证据来源与强度分为 6 级，避免把弱证据、误判证据和真实业务副作用混为同一类成功：

| 等级 | 名称 | 判定依据 |
|---|---|---|
| **E0** | Not Evaluable | 基础设施失败、协议错误或目标不可用 |
| **E1** | Text Claim | 模型仅在文本中声称执行 |
| **E2** | Judge-Suspected | LLM 裁判判定疑似成功 |
| **E3** | Rule-Verified | Canary token / 隐藏字符串 / 强规则命中 |
| **E4** | Tool-Observed | 工具调用日志显示越权调用 |
| **E5** | Probe-Verified | 业务状态差异或 probe 查询确认 |

### 2.2 Quartet 四元对照

每个攻击用例同时执行四个变体，隔离误判与过度防御：

| 变体 | 用途 |
|---|---|
| **Clean** | 衡量 Utility（原任务可完成性） |
| **Attack** | 衡量 Attack Success |
| **Quoted Attack** | 识别 judge 把"讨论"误判为"执行"的 false positive |
| **Benign Distractor** | 识别 over-defense（过度防御） |

理想情况下，安全可用的应用应满足：Clean 成功、Attack 失败、Quoted Attack 不被判成功、Benign Distractor 不被拒答。

### 2.3 Evidence-Stratified ASR

按证据来源与强度分层报告：

- **Raw / Judge / Text-Claim / Rule-Verified / Tool-Observed / Probe-Verified ASR**
- **Quartet-Validated ASR**：经过四元对照后保留的强证据子集
- **Utility Rate**、**Over-Defense Rate**、**Evaluability Rate**

> **与 Corrected ASR 的关系**：本指标在数学上**正交**于 *A Coin Flip for Safety* 的 Corrected ASR：
>
> - **Corrected ASR** 通过裁判 precision 做**统计后校正**（标量倍乘单一来源）。
> - **Evidence-Stratified ASR** 按**异质证据来源做分层切分**（无标量调整、无源融合）。
>
> 两者可在同一实验中并列报告，作为互补诊断指标。

### 2.4 冲突驱动闭环补测

弱证据 finding 通过 `conflict-type → retest-action` 状态机自动触发复测：

| `conflict_type` | 触发条件 | 补测策略 |
|---|---|---|
| `judge_without_rule_evidence` | Judge 判成功但规则/probe 无证据 | Quartet 复测 |
| `quoted_attack_success` | Quoted Attack 也成功 | 标记为 judge false-positive 候选 |
| `secret_disclosure_suspected` | 疑似泄露但无 canary 命中 | Canary 重测 |
| `unauthorized_action_claim` | 文本声称但无工具日志 | Probe 验证 |
| `clean_failed` | 原任务失败 | 标记 `not_evaluable` / `utility_failure` |

每个 finding 保留可审计的补测历史（`initial → retest_1 → ... → final`），最终标记为 `confirmed` / `overturned` / `manual_review_needed`。

### 2.5 Canary 通道溯源

Canary 命中按通道记录证据强度与一个粗粒度传播标签：当前实现区分 **exposed**（出现在响应文本）与 **executed**（工具调用或业务状态）。完整的 Exposed / Persisted / Relayed / Executed 阶段矩阵尚未实现，列入路线图 v0.4。

---

## 三、与现有工作的差异

| 现有工作 | 他们的角度 | 本工作的正交角度 |
|---|---|---|
| *A Coin Flip for Safety* (2026) | 基于裁判精度的统计后校正 | 按异质证据来源分层切分 |
| *When Scanners Lie* (2026) | 单 verifier 二阶段验证 | 多类异质证据 + 冲突驱动状态机 |
| *Kill-Chain Canaries* (2026) | 单维度攻击传播阶段 | 应用层 canary 通道溯源（exposed / executed）；完整阶段矩阵列入后续工作 |
| HarmBench / JailbreakBench | 基础模型 benchmark | 应用层评测 + 业务状态 probe |
| AgentDojo / tau-bench / AgentHarm | Agent / 工具调用 benchmark | 与证据分层协议绑定的状态验证 |
| garak / PyRIT / Promptfoo / DeepTeam | 红队工具框架 | 可信度感知的报告与补测闭环 |

完整文献分析与差异化论证将随论文一并发布。

---

## 四、快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- OpenAI-compatible API Key

### 后端

```bash
cd backend
cp .env.example .env  # 编辑 .env，填入模型/API 配置
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问：

- 前端 Dashboard：<http://localhost:5173>
- 后端 API：<http://localhost:8000/docs>

### Docker

```bash
cp .env.example .env
docker compose up --build
```

---

## 五、可复现性

仓库提供：

| 模块 | 路径 |
|---|---|
| 攻击模板库 | `backend/app/attack_templates/` |
| 黑盒判定服务 | `backend/app/services/verdict_*`、`evidence_arbiter.py` |
| AutoTest Agent v1 | `backend/app/services/autotest_*` |
| AutoTest API | `backend/app/api/autotest.py` |
| 前端可视化 | `frontend/src/pages/AutoTest.tsx`、`Report.tsx` |
| 测试套件 | `backend/app/tests/`、`backend/tests/` |
| 评测协议 | [`docs/evaluation_protocol.md`](./docs/evaluation_protocol.md) |

实验数据、人工标注校准集、跨模型对比表正在准备中，将在后续版本陆续发布。

---

## 六、引用方式

仓库提供 [`CITATION.cff`](./CITATION.cff)，GitHub 会自动在仓库主页右侧渲染 *Cite this repository* 按钮。

```bibtex
@software{xu_evidence_ladder_2026,
  author       = {Xu, Zihao},
  title        = {Evidence-Ladder: Multi-Source Evidence-Stratified Evaluation
                  for LLM Application Security},
  year         = {2026},
  version      = {0.1.0},
  url          = {https://github.com/polarisxb/evidence-ladder},
  license      = {MIT}
}
```

---

## 七、项目状态

**研究预览版（v0.1.0）** —— 方法框架、评测协议、AutoTest agent v1 实现已完成。实验数据、人工校准集与论文初稿正在推进中。

**路线图：**

| 版本 | 计划内容 |
|---|---|
| **v0.1**（当前） | 方法框架 + 平台实现 + 评测协议 + AutoTest agent v1 |
| **v0.2** | Pilot 实验（30 用例 × 4 变体 × 2 模型） + 小规模人工标注 |
| **v0.3** | 跨模型正式实验（100+ 用例 × 3–5 模型） + Cohen's κ + 与 Corrected / Verification-layer ASR baseline 对比 |
| **v0.4** | 邮件 / 电商 Agent 沙箱；扩展 canary 传播阶段（若实现） |
| **v0.5** | 公开数据集发布 + arXiv preprint |

---

## 八、协议与致谢

[MIT 协议](./LICENSE)。

本项目站在以下开源工作之上：HarmBench、JailbreakBench、AgentDojo、tau-bench、ToolEmu、AgentHarm、garak、PyRIT、Promptfoo、OWASP LLM Top 10 / Agentic Top 10。差异化分析另引用 2026 年裁判可靠性与攻击传播研究：*A Coin Flip for Safety*、*When Scanners Lie*、*Kill-Chain Canaries*、*Noisy but Valid*、*Know Thy Judge*、*RobustJudge*。

---

## 九、联系方式

- **GitHub Issues / Discussions**：<https://github.com/polarisxb/evidence-ladder>
- **作者**：徐子豪（Xu Zihao） · GitHub [@polarisxb](https://github.com/polarisxb)
