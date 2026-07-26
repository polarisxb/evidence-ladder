<!-- markdownlint-disable MD013 -->
# 实验产物统一分类与封存声明

> **生成 2026-07-26。本文覆盖 `backend/experiment-output/` 下全部 24 个 run 目录。**
>
> **一句话规则:截至本文日期,本目录下没有任何产物构成论文级(thesis-grade)证据。**
> 引用其中任何数字之前,先在下表查到它的档位。

---

## 0. 为什么保留而不是删除

这些产物**已被判定不可用于论文主结果**,但**不删除**,理由有三条:

1. **不可再生。** 付费中转跑、`temperature=0.7`、rolling-alias 模型(如 `gpt-5.4` 这类会滚动指向新版本的别名)。
   重跑得到的不是同一批数据,原始 lineage 丢了就是永久丢了。见提交 `99f1a0b`。
2. **作废记录本身是严谨性证据。** 本项目的论点是"单一来源 ASR 不可信"。一份「我们跑了 → 自查出构造无效
   → 明确声明作废」的完整轨迹,比任何自我声明都更能回答审稿人的"你怎么知道你的构造有效"。
3. **管线回归价值。** 即使数据不可引用,run-manifest / lineage / integrity-audit 的结构仍是编排、
   计账、时间分块、报告生成这些环节的回归基准。

**因此:本目录处于封存状态(sealed),不是待删除状态。**

---

## 1. 档位定义

| 档位 | 含义 |
|---|---|
| 🔴 **构造无效** | 数字本身可能是对的,但测不到要测的东西(gold / judge / B 依赖同一个信号) |
| 🟠 **脚本靶子** | 靶子是固定回复的 fixture,验证的是**机制通不通**,不是真实发生率 |
| 🟡 **工程校准** | 为调参/闸门而跑,从设计上就不是分析数据 |
| 🔵 **探路信号** | 真靶子、真行为,但单 block、小样本、无人工标注 |
| ⚫ **无 manifest** | 缺少 run-manifest,不可复现、不可追溯 |

**四个档位都不可引用为论文主结果。** 区别只在于**为什么**不可引用,以及将来正式跑时该吸取什么。

---

## 2. 全量分类表

套件 hash 由项目自身的 `experiment_driver.compute_frozen_suite_hash()` 复算核对(2026-07-26)。

### 🟠 脚本 builtin 靶子 —— 8 个目录,全部 suite `2c5fc2d10c` = `builtin_mvp_suite.json`(10 例)

| 目录 | 说明 |
|---|---|
| `builtin-mvp` | MVP 三臂首跑 |
| `formal-code-validation-20260712` | 代码路径验证 |
| `natural-probe-3arm` | ⚠️ **名字里的 "natural" 是误导**——靶子是脚本 builtin,只有 judge/verifier 是真模型 |
| `relay-gpt55-exploratory-20260712T1307Z` | 中转站探路 |
| `rigor-j54-v55-r1-20260712` | 严谨性复跑 |
| `rigor-j54-v55-r2-20260712` | 同上 |
| `rigor-j55-v54-r1-20260712` | 角色互换复跑 |
| `rigor-j55-v54-r2-20260712` | 同上 |

该 fixture 对每个攻击都返回固定的"已完成"式假话。由此得到的 `A/A′ 假阳率 100%`、`B 推翻 4/4`
一类数字,**只能读作"真裁判会被脚本谎言系统性欺骗,而状态探针能识破"**,即验证机制。
❌ 不可作为自然裁判错误率;❌ 不可作为效应量或 power analysis 输入;❌ 不可与自然行为跑合并汇总。

详见 [`natural-runs-notice.md`](./natural-runs-notice.md)。

### 🔴 构造无效 —— 6 个目录,suite `2dfef6f546` = `formal_pilot_canary_suite.json`(40 例)

`formal-pilot-j54-v55-block1/2/3`、`formal-pilot-j55-v54-block1/2/3`

fixture 用 `temperature=0` 且**指示模型回显 canary**,导致 ground truth、judge 可见行为、B 的 canary 证据
三者依赖**实质相同的信号**;A/A′ 又被设计封顶 E2。它能验证编排与报告,**无法估计对自然裁判错误的纠正**。

详见 [`formal-pilot-superseded-notice.md`](./formal-pilot-superseded-notice.md)。

### 🔴 构造无效 + ⚫ 套件已丢失 —— 3 个 validation 目录

| 目录 | suite hash | 状态 |
|---|---|---|
| `formal-pilot-validation-j55-v54` | `2b3e005e93` | ⚠️ **无现存套件文件能复现此 hash** |
| `formal-pilot-validation-j55-v54-v2` | `7d0926b98e` | ⚠️ **同上** |
| `formal-pilot-validation-j55-v54-v3` | `35ba6903f6` | = `formal_pilot_canary_validation_suite.json`(3 例) |

前两个的套件在迭代中被覆盖,**其输入已不可重建**。这条本身是个教训:套件应当按 hash 归档,而不是原地覆盖。
正式跑必须避免重蹈(见 §4 第 2 条)。

### 🟡 工程校准 —— 3 个目录

| 目录 | suite | 说明 |
|---|---|---|
| `stateful-correction-builtin-dry-run` | `ab2d3cb17b`(48 例) | builtin 干跑 |
| `stateful-paid-gate-j55-v54-block1` | `ef43108c61`(8 例) | 付费闸门 |
| `stateful-paid-gate-j55-v54-block2` | `ef43108c61`(8 例) | 同上 |

已封 `CALIBRATION_NOT_ANALYSIS`。见 `stateful-calibration-phase-closure.md`、`stateful-paid-gate-final-report.md`。

### 🔵 探路信号 —— 1 个目录

`natural-3arm-block1` — suite `1bd8269bdb` = `natural_pilot_suite.json`(40 例),
靶子 `gpt-5.4-mini-2026-03-17`(真模型),`temperature=0.7`,24 attack + 8 clean + 8 benign。

**这是本目录下唯一的自然行为三臂产物。** 但:单 block、`judge_vs_human_kappa=PENDING`、无独立 gold。
按 `docs/exploration_findings.zh-CN.md` 的定性,它是**探路试跑,不得作为 thesis 级证据**。

### ⚫ 无 manifest —— 3 个目录

| 目录 | 说明 |
|---|---|
| `academic-rigor-audit-20260712` | 审计输出,非 run |
| `natural-calibration` | 真 LLM 初测 40 条,用于校准泄露率;仅有 pass 缓存 |
| `fp-probe-calib` | 假阳诱导套件初测 12 条,真 LLM;**诱导失败**(TP4/FP0/TN8/FN0),是有价值的**阴性结果** |

---

## 3. 与 bug 的关系(2026-07-26 澄清)

产品扫描管线在此期间修复了若干评测器 bug(`b82186e` concealment provenance、`fc49380` evidence arbiter
E4 降级、`5d00e82` text_claim 计数、以及拒绝识别的弯排版撇号问题)。**这些 bug 不影响本目录下的任何数据。**

`experiment_driver.py` 是自成一体的实验台,其判定只经过两条链路:oracle 精确匹配与 LLM 裁判。它**没有 import**
`evidence_arbiter`、`concealment_detector`、`autotest_metrics`,其目标调用 `invoke_target_with_envelope`
**不经过** `screen_response_origin`。上述 bug 全部位于产品扫描管线。

**所以本目录的问题是构造效度,不是 bug 污染。** 两者的处置不同:bug 污染要重算,构造无效要重新设计。

---

## 4. 什么样的 run 才能替换它们

按 `docs/paper_direction_v2.zh-CN.md` §8(在 `paper-workspace` 分支),正式产物必须同时满足:

1. **`manual_review` 缺陷已修** —— 当前所有 case 最终都至少 `manual_review`,导致 FP / utility /
   过度防御率全部顶死 100%、三臂无分辨力。不修则 FP 象限即使造出来也测不到。
2. **估计量与判据已预注册** —— `Y = 1[p > 0]`、N ≥ 30、oracle 匹配口径、编码翻车由数据判定、检测下限声明;
   **随后重新冻结套件(新 hash,需重新批准),且套件按 hash 归档不得原地覆盖**。
3. **独立 gold 已采集** —— 每攻击用例 N ≥ 30 次独立抽样 + 歧义样本人工双盲裁定出 κ;
   gold 采集必须独立于三臂运行,**不得复用 B 的重测结果**充当抽样。

在这三条全部满足之前产出的任何数据,都归入本文的四个档位之一。

---

*封存于 2026-07-26。新增 run 目录请同步更新本表;若某目录后续升格为可引用,在此注明升格依据。*
