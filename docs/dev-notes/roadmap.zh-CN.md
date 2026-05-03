# Evidence-Ladder 长期路线图（v0.1 → v0.5）

更新时间：2026-05-03  
当前版本：v0.1.0  
主要作者：徐子豪 (polarisxb)  
关联文档：[opening_report.zh-CN.md](../opening_report.zh-CN.md)、[evaluation_protocol.md](../evaluation_protocol.md)

---

## 0. 文档作用与维护规则

本文档是 Evidence-Ladder 项目从 v0.1（2026-05-02 已发布）到 v0.5（论文 preprint）的**滚动式长期路线图**。

它**不是**一次性写完的甘特图，而是按 Stage 推进、阶段性复盘、按需微调的**活文档**。

### 维护规则

- **路线图本身不频繁修改**：6 个 Stage 的总目标与顺序在没有重大触发（见 §8）的情况下保持稳定。
- **每完成一个 Stage**：在 §11 历史复盘记录里追加一条复盘条目，并按需更新该 Stage 之后未启动 Stage 的预计时长。
- **进入 Stage N-1 末期时**：才开始详化 Stage N 的实施文档（`docs/dev-notes/stageN_plan.zh-CN.md`）。提前过度规划是禁止的。
- **任何"我想加新方向"的诱惑**：写入 §9 反诱惑清单的"已记录但不做"条目，等 v0.6 后再考虑。

---

## 1. 北极星目标（North Star）

> **在 4 个月内（2026 年 9 月底前），让仓库能一键产出 v0.5 paper preprint 所需的全部代码、数据、图表，并把 preprint 上传 arXiv。**

### 量化标准

| 指标 | 目标值 |
|---|---|
| Pilot 数据可复现 | 30 case × 4 变体 × 2 模型 = 240 runs，一行命令复现 |
| Baseline 复现 | Coin Flip / Scanners Lie / Noisy-but-Valid 三个 baseline 在同一份数据上跑通 |
| 人工标注 | ≥ 200 条双人盲标，Cohen's κ ≥ 0.6 |
| 正式实验 | 100+ 用例 × 3-5 模型 |
| Agent 沙箱 | 邮件 + 电商两个最小沙箱跑通 E5 Probe-Verified |
| 论文图 | 5 张核心图全部脚本化生成 |
| 复现包 | 包含 dataset + scripts + configs 的 tarball 可下载 |

---

## 2. Scope（明确要做的）

| 类别 | 内容 |
|---|---|
| 平台代码 | 实验 runner、Quartet 变体生成器、复测真实执行、Agent 沙箱 |
| 评测协议 | E0–E5 证据分层、Quartet 四元对照、E×K 二维矩阵 |
| Baseline 实现 | Corrected ASR (Coin Flip)、Verification-layer ASR (Scanners Lie)、Noisy-but-Valid 假设检验 |
| 标注与统计 | 标注 UI、双人盲标、Cohen's κ、Bootstrap CI、Power analysis、多重比较校正 |
| 数据导出 | CSV、LaTeX 表、matplotlib/plotly 图 |
| 平台底线 | 安全修复（默认认证 / SSRF / 凭据回传 / WebSocket）、CI、复现包 |

## 3. Out of Scope（明确不做的）

| 类别 | 理由 |
|---|---|
| 新的 jailbreak 算法 | AgenticRed、AutoDAN-Turbo 已经做透，不进入红海 |
| 大规模 benchmark（HarmBench-scale） | 维护成本巨大，论文角度不需要 |
| UI 视觉 / 设计大改 | 不影响论文，浪费精力 |
| 商业化 / SaaS 化 | 学术阶段不考虑 |
| 跨语言完整本地化 | 中文+英文 README 已够 |
| MCP 工具投毒 / 搜索 Agent / 多模态 | 范围漂移，留给后续工作（v1.0+） |

## 4. Non-Goals（明确不追求的）

- ❌ 一个项目囊括所有 LLM 安全问题
- ❌ 在攻击成功率上超过 AgenticRed
- ❌ 比 garak / PyRIT 功能更全
- ❌ 在 v0.5 之前发布"通用 benchmark"
- ❌ 取代任何现有商业产品

---

## 5. 6 个 Stage 概览

| Stage | 目标（一句话） | 完成标志 | 预计 | 状态 | 实施文档 |
|---|---|---|---|---|---|
| **1** | 修底线 + 跑出第一份 Pilot 数据 | 4 个安全 P1 修复 + 1 模型 × 30 case × 4 变体 = 120 runs 落库 | 1-2 周 | 🟡 当前 | [stage1_plan.zh-CN.md](./stage1_plan.zh-CN.md) |
| **2** | 复现 baseline + 出第一张论文图 | Coin Flip + Scanners Lie baseline 跑通；Judge vs Stratified ASR 对比柱状图 | 1-2 周 | ⏳ 待开 | _进入 Stage 1 末期时创建_ |
| **3** | 建标注体系 + 接统计严谨性 | 标注 UI + Cohen's κ + Bootstrap CI；50-100 条 gold label | 2-3 周 | ⏳ 待开 | _进入 Stage 2 末期时创建_ |
| **4** | 跨模型正式实验 | 100+ case × 3-5 模型；200+ 双盲标注；κ ≥ 0.6；多重比较校正 | 3-4 周 | ⏳ 待开 | _后续创建_ |
| **5** | Agent 沙箱 + E×K 矩阵 | 邮件/电商 Agent 跑通 E5；5×4 矩阵图；Kill-chain stage tracker | 4-6 周 | ⏳ 待开 | _后续创建_ |
| **6** | 论文初稿 + arXiv preprint | 10-12 页 preprint；5 张图脚本化；公开数据集 + 复现包 | 3-4 周 | ⏳ 待开 | _后续创建_ |

**总预计：约 3.5-5 个月到 v0.5。**

### 5.5 v0.2.5 临时分支：品牌清理

不算独立 Stage，触发条件：**比赛公示完全结束**（外部触发）。

完成标志：

- 36 处 `天鉴` / `TianJian Libra` / `JianHeng` 字样从代码、UI、文档全部清理为 `Evidence-Ladder`
- README 加回一行 `> 中文别名：天鉴·衡（早期参赛代号）` 作为情怀
- `frontend/src/components/icons/JianHengLogo.tsx` 重命名为 `EvidenceLadderLogo.tsx`
- v0.2.5 release 发布

预计耗时：1-2 小时（半自动化）。

---

## 6. 当前 Stage 详细计划

→ 见 [stage1_plan.zh-CN.md](./stage1_plan.zh-CN.md)

---

## 7. 复盘机制

### 7.1 每个 Stage 完成时的 5 个复盘问题

```text
1. 完成度：原计划交付物有多少做到了？（0-100%）
2. 意外发现：跑数据 / 写代码过程中，发现了什么没预料的？
3. 数字合理度：实验数字 / 测试结果是否合理？哪里反常？
4. 资源消耗：实际花了多少时间 / 多少 API 成本？vs 预估差多少？
5. 下一步是否还成立：原本规划的下一个 Stage 还合理吗？要不要调整？
```

### 7.2 复盘后的 3 种结果

| 结果 | 应对 |
|---|---|
| **绿灯**（完成度 ≥ 80%、数字合理、下一步明确） | 直接详化下一 Stage 实施文档，开干 |
| **黄灯**（完成 50-80%、有意外但可控） | 微调下一 Stage 范围，记录在 §11；继续推进 |
| **红灯**（完成 < 50% 或数字反常或方向有疑） | **停下**，先解决根因；可能要拆分或重排 Stage |

### 7.3 强制复盘点

- 每个 Stage 自然结束时
- 跑出的 ASR 数字与人工抽样判断 **大幅偏离**（> 30%）时
- 任意 milestone 实际耗时 **超出预估 50%** 时
- 出现新的 2026/2027 直接撞车论文时（需要更新差异声明）

---

## 8. 调整原则

### 8.1 应该重新规划的情况（重大触发）

| 触发条件 | 应对 |
|---|---|
| 当前 Stage 数据出现"反预期"现象 | 立刻停，分析原因。可能是 bug，也可能是真发现。 |
| 出现新的直接撞车论文（如有人发了"Evidence-Layered ASR for LLM Apps"） | 加 §3.5 差异声明，重新定位本工作。可能影响 Stage 6 论文 framing。 |
| 比赛公示日期发生变化 | 仅影响 v0.2.5 时机，其他不变。 |
| 找不到标注同学 | Stage 3 改用 LLM-as-2nd-annotator + 你本人裁定 100 条样本。 |
| 个人时间发生重大变化（实习/搬家/家事） | 拉长每 Stage 时长，不变结构。 |
| API 预算告急 | 优先选便宜模型；缩减 Stage 4 的模型数量到 3 个。 |

### 8.2 不该改路线图的情况

- 单纯做得不耐烦
- 看到别人的 cool paper 想跟风
- 当前 Stage 比预计慢（拖延 ≠ 错向，硬推完）
- 想美化代码 / UI / 文档（除非影响标注效率）

---

## 9. 反诱惑清单（"已记录但不做"）

> 任何冒出来的"想加点 X"，都先写到这里，等 v0.6+ 再考虑。这样既不丢失想法，也不漂移当前路线。

| 想做的事 | 为什么诱人 | 为什么先不做 | 记录日期 |
|---|---|---|---|
| 加新攻击算法（如 PAPILLON、JailbreakRadar 类） | 看起来很 cool | AgenticRed 已经做透，且不是本论文核心 | 2026-05-03 |
| UI 重新设计 | 视觉吸引力提升 | 不影响论文，浪费精力 | 2026-05-03 |
| 多语言完整 i18n（除中英） | 国际化感 | 中英已够 reviewer 看 | 2026-05-03 |
| MCP 工具投毒红队 | 2026 热点 | 范围漂移，留 v1.0 | 2026-05-03 |
| 搜索 Agent 红队 | SafeSearch 启发 | 范围漂移，留 v1.0 | 2026-05-03 |
| 多模态攻击（图像/音频 prompt injection） | 前沿 | 完全不在当前协议范围 | 2026-05-03 |
| 接入 5+ 家国内大模型 API（GLM/Qwen/Baichuan/Hunyuan/...） | 国内学术圈友好 | Stage 4 用 3-5 个就够；过多会爆预算 | 2026-05-03 |
| 写技术博客 / 公众号 | 推广 | v0.5 之后再说 | 2026-05-03 |
| 重构后端架构 | 工程洁癖 | 当前能跑能扩，不重构 | 2026-05-03 |
| Docker compose 极致优化 | 工程感 | 现有能跑就行 | 2026-05-03 |

---

## 10. 关键依赖与外部资源

### 10.1 必须有的

| 资源 | 用途 | 预算 / 安排 |
|---|---|---|
| OpenAI API key（GPT-4o-mini） | Stage 1+ 主力测试模型 | $20-30 总预算 |
| DeepSeek API key（DeepSeek-V3） | Stage 2+ 中文场景对比 | $5-10 总预算 |
| ≥ 1 个标注同学 | Stage 3+ 双人盲标 | 找 1 个研究方向相关同学 |
| GitHub repo（已有） | 代码 + release 托管 | 免费 |

### 10.2 可选但有用

| 资源 | 用途 |
|---|---|
| 智谱 GLM-4 API | Stage 4 国内大模型对比 |
| Qwen-Max / Claude API | Stage 4 多家对比 |
| arXiv 投稿账号（需 endorsement） | Stage 6 preprint 上传 |
| 学校的 LaTeX 模板 | Stage 6 论文排版 |

---

## 11. 历史复盘记录

> 每个 Stage 完成后追加一条。格式：日期 / Stage / 完成度 / 关键发现 / 下一步调整。

### 2026-05-03 · 路线图首次发布

- 完成度：N/A（仅规划）
- 关键发现：v0.1 已经稳定发布到 GitHub，参赛文件夹隔离 + README 学术化均已就位。
- 下一步：进入 Stage 1。

### Stage 1 复盘 · _待 Stage 1 完成后填写_

```text
日期：
完成度：
原计划交付：
实际交付：
意外发现：
数字是否合理：
实际时间 vs 预估：
实际 API 成本：
是否需要调整 Stage 2：
```

---

## 12. 与 superpowers-workflow 的对接

本路线图是 superpowers-workflow 的"宏观规划层"。每个 Stage 在执行时，遵循 superpowers 9 阶段：

```text
frame -> inspect -> spec/plan -> test-first -> implement
      -> review   -> verify    -> publication-safety -> report
```

阶段实施文档（`stageN_plan.zh-CN.md`）按这 9 阶段组织。

参考：
- [.cursor/skills/superpowers-workflow/SKILL.md](../../.cursor/skills/superpowers-workflow/SKILL.md)
- [.codex/skills/superpowers-workflow/SKILL.md](../../.codex/skills/superpowers-workflow/SKILL.md)
