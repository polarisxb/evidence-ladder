# Formal Pilot v2 — 模型花名册（v2.4，冻结 2026-09-01）

> **Roster version**: `formal-pilot.v2.4`（domestic-first + **current-catalog**）  
> **Canonical config**: `backend/experiments/model_roster.v2.json`  
> **Rebuild**: `cd backend && python3 -m scripts.build_formal_pilot_v2_matrices`

---

## 先回答两个担心

**厂商会下架。** 会。规则是：第一次付钱之前下架 → 换成目录里还在卖的现行 SKU，重冻 hash。付钱之后下架 → **不换主表**，当「某日快照」写 Limitations；要补新模型就另开 Phase-2，不动旧 hash。

**不是最新是不是没效力。** 对**这篇论文**没有。主估计是协议（A vs A′ vs B 的测量误差），不是模型排行榜。没有效力的是测**已经下架、别人复跑不了**的产品。JailbreakBench 用带日期的 GPT 和开源锚点，不要求周更 SOTA。

因此闭源位用厂商**当前默认 SKU**（Kimi K3、GLM-5.3），开源位用可复托管的权重（Qwen3-32B、DeepSeek-V3.1）。一边代表「现在还在卖的系统」，一边保证别人能复核。

---

## Phase-1 清单（去买这些）

| 角色 | API ID | 平台 | 档位 |
|------|--------|------|------|
| Target-1 | `Qwen/Qwen3-32B` | 硅基流动 | 开源锚点（~32B 档，不追旗舰） |
| Target-2 | `kimi-k3` | Moonshot / Kimi 官方 | **现行**闭源默认 |
| Target-3 | `MiniMaxAI/MiniMax-M2.5` | 硅基流动 | **现行**低成本 |
| Judge A / Verifier B | `deepseek-ai/DeepSeek-V3.1` | 硅基流动 | 开源权重裁判 |
| Verifier A / Judge B | `glm-5.3` | 智谱官方 | **现行**闭源裁判 |

矩阵：`formal_pilot_v2_jdeepseek_vglm_models.json` / `jglm_vdeepseek`；paid gate 单 target `kimi-k3`。

---

## 三规则（冻结后照此执行）

1. **现行目录**：冻结日必须在售。闭源 target + 一名裁判 = 厂商当前默认生产 SKU。
2. **采集日冻结**：`(vendor, model_id, date, returned_model)`。别名会漂，采集开始后不静默换。
3. **替换窗口**：付费前可换并重冻；付费后只追加、不替换。

---

## Phase-2

Claude / Gemini / GPT 在 `expansion_roster`。激活冻 `v2.5+`。

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-09-01 | **v2.4** 现行目录：T2→`kimi-k3`，J/V GLM→`glm-5.3`；写入三规则 |
| 2026-09-01 | v2.3（k2.6 + glm-4.7）— 未采集，被现行默认取代 |
| 2026-08-31 | v2.2 — ID 已下线，未采集 |
| 2026-08-31 | v2.1 — 移入 expansion |
