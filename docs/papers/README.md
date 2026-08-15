<!-- markdownlint-disable MD013 -->
# 参考文献索引 / Reference Index

本目录**不再分发论文全文**。此前这里放过 5 篇论文的正文逐字提取（`.txt`），已移除：那与 `.gitignore`
中排除 PDF 所依据的版权理由是同一条，换个容器不改变性质。第三方论文一律以标识符和官方链接引用，
请从出版方获取原文。

> This directory does **not** redistribute paper full text. Third-party papers are cited by
> identifier and official link only; obtain them from the publisher.

---

## 一、攻击引擎与其来源论文

`backend/app/services/` 下每个攻击引擎都在模块 docstring 里注明来源。此表为汇总，权威说明以各模块
docstring 为准。

| 引擎模块 | 来源论文 | 出处 |
|---|---|---|
| `pair_engine.py` | Jailbreaking Black Box Large Language Models in Twenty Queries (PAIR) — Chao et al. | [arXiv:2310.08419](https://arxiv.org/abs/2310.08419) |
| `tap_engine.py` | Tree of Attacks: Jailbreaking Black-Box LLMs Automatically (TAP) — Mehrotra et al., NeurIPS 2024 | [arXiv:2312.02119](https://arxiv.org/abs/2312.02119) |
| `crescendo_engine.py` | Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack — Russinovich, Salem, Eldan (Microsoft) | [USENIX Security 2025](https://www.usenix.org/conference/usenixsecurity25/presentation/russinovich) |
| `fitd_engine.py` | Foot-In-The-Door: A Multi-turn Jailbreak for LLMs — Weng, Jin, Jia, Zhang | [arXiv:2502.19820](https://arxiv.org/abs/2502.19820) |
| `msj_engine.py` | Many-shot Jailbreaking — Anil et al. (Anthropic), NeurIPS 2024 | [anthropic.com](https://www.anthropic.com/research/many-shot-jailbreaking) |
| `ice_engine.py` | Exploring Jailbreak Attacks on LLMs through Intent Concealment and Diversion | [ACL Findings 2025](https://aclanthology.org/2025.findings-acl.1067) |
| `iris_engine.py` | GPT-4 Jailbreaks Itself with Near-Perfect Success Using Self-Explanation (IRIS) — 本项目为其自解释思路的黑盒改写，非原方法复现 | — |
| `mutation_engine.py` | 变异策略取自 LLM-Fuzzer (USENIX Security 2024) 与 PAPILLON (USENIX Security 2025) 的黑盒变体，以及通用混淆/绕过文献 | [LLM-Fuzzer](https://www.usenix.org/conference/usenixsecurity24/presentation/yu-jiahao) |

未在引擎中实现但在差异化分析中引用：

| 论文 | 出处 | 用途 |
|---|---|---|
| Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG) — Zou et al. | [arXiv:2307.15043](https://arxiv.org/abs/2307.15043) | 白盒方法，作为对照说明本项目的黑盒定位 |

## 二、评测可靠性文献

本项目的核心主张——单一来源 ASR 不可信——建立在以下工作之上，详见根目录 `README.md` 的动机与对标章节：

| 论文 | 标识 |
|---|---|
| A Coin Flip for Safety | arXiv:2603.06594 |
| When Scanners Lie | arXiv:2603.14633 |
| Kill-Chain Canaries | arXiv:2603.28013 |

## 三、引用本项目

见仓库根目录的 [`CITATION.cff`](../../CITATION.cff)。
