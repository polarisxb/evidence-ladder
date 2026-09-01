# Formal Pilot v2 — 模型花名册（v2.3 domestic-first，冻结 2026-09-01）

> **Roster version**: `formal-pilot.v2.3`（strategy: **domestic-first**；v2.2 的下线 ID 刷新，协议未改）  
> **Canonical config**: `backend/experiments/model_roster.v2.json`  
> **Generated matrices**: run `cd backend && python3 -m scripts.build_formal_pilot_v2_matrices`

---

## 分期路径

- **Phase-1（现在）**: 全国产可充值 API → paid gate → pilot v2 → formal blocks。**不依赖** OpenAI/Anthropic/Google 充值。
- **Phase-2（可选，非阻塞）**: `expansion_roster` 中的 Claude/Gemini/GPT；激活时冻结 `formal-pilot.v2.4+`，不动 Phase-1 hash。

## 固定模型清单（Phase-1）

| 角色 | 模型 | API ID（控制台里就找这个） | Provider 槽位 | 家族 |
|------|------|---------------------------|---------------|------|
| **Target-1 开源锚点** | Qwen3-32B | `Qwen/Qwen3-32B` | `siliconflow-cn` | Qwen |
| **Target-2 国产闭源** | Kimi K2.6 | `kimi-k2.6` | `moonshot-official` | Moonshot |
| **Target-3 低成本** | MiniMax-M2.5 | `MiniMaxAI/MiniMax-M2.5` | `siliconflow-cn` | MiniMax |
| **Judge（矩阵 A）** | DeepSeek-V3.1 | `deepseek-ai/DeepSeek-V3.1` | `siliconflow-cn` | DeepSeek |
| **Verifier（矩阵 A）** | GLM-4.7 | `glm-4.7` | `glm-official` | GLM |
| **Judge（矩阵 B）** | GLM-4.7 | `glm-4.7` | `glm-official` | GLM |
| **Verifier（矩阵 B）** | DeepSeek-V3.1 | `deepseek-ai/DeepSeek-V3.1` | `siliconflow-cn` | DeepSeek |

共 **5 个互相独立的国产家族**；J/V 跨家族、跨 provider 对调，且与全部 target 家族不重叠（无自评偏置）。

### 矩阵文件

| 文件 | content_hash | 用途 |
|------|--------------|------|
| `formal_pilot_v2_jdeepseek_vglm_models.json` | `d144c541…` | Judge=DeepSeek-V3.1, Verifier=GLM-4.7 |
| `formal_pilot_v2_jglm_vdeepseek_models.json` | `353a6ef4…` | 角色互换 |
| `stateful_paid_gate_v2_models.json` | `6d7db3ae…` | Paid gate（单 target: `kimi-k2.6`；一次触达全部 3 key） |

完整 hash 以生成脚本输出为准。替换 provider UUID 后 hash 会变化，须重跑脚本并归档。

---

## 选型理由

1. **只选 2026-09-01 仍在卖的 ID**。v2.2 的 `kimi-k2-0905-preview`（Moonshot 已下线）和 `MiniMaxAI/MiniMax-M1-80k`（SiliconFlow 2026-02-08 下线）不能再买。
2. **Kimi 用 `kimi-k2.6` 不用 `kimi-k3`**：K2.6 是当前仍在线的命名世代；K3 是旗舰滚动线，漂移更快。采集日写入 `returned_model`。
3. **DeepSeek 不走官方 API**：官方只有 `deepseek-chat` 滚动别名，会被 `allow_rolling_aliases=false` 拒绝。SiliconFlow 精确权重 id `deepseek-ai/DeepSeek-V3.1` 仍在模型枚举中。
4. **裁判用 `glm-4.7` 不用 `glm-5.3`**：4.7 在智谱仍有独立文档；5.3 太新，留给附录。
5. **MiniMax-M2.5**：SiliconFlow 上 M1 / M2.1 已下线后的现行 id，复用同一把 SiliconFlow key。
6. **SiliconFlow 披露**：第三方推理，但服务的是 pinned 开源权重。Limitations 写明 serving stack；用 `returned_model` + 固定 decode 缓解。

---

## Phase-2 expansion_roster（非阻塞）

| 候选 | pinned ID | 预定角色 |
|------|-----------|----------|
| Claude Sonnet 5 | `claude-sonnet-5` | J/V 对调（vs Gemini） |
| Gemini 3.5 Flash | `gemini-3.5-flash` | J/V 对调（vs Claude） |
| GPT-5.5 dated | `gpt-5.5-2026-04-23` | target（frontier closed） |
| GPT-5.4-mini dated | `gpt-5.4-mini-2026-03-17` | target（low cost） |

**激活条件**: ① Phase-1 formal 归档；② 官方充值可用或接受聚合通道并写 Limitations；③ 冻结为 `formal-pilot.v2.4+`，不改 Phase-1 hash。

---

## 明确不使用

- **`kimi-k2-0905-preview`** — Moonshot 已下线
- **`kimi-k3`** — Phase-1 不用（旗舰漂移）
- **`MiniMax-M1-80k` / `MiniMax-M2.1`** — SiliconFlow 已下线
- **`deepseek-chat` / DeepSeek V4** — 滚动别名或过新
- **`glm-5.3`** — Phase-1 不用
- **GPT-5.6 / gemini-2.5-pro / relay `b98979c7-…`**

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-09-01 | **v2.3 live-id refresh**: T2→`kimi-k2.6`；T3→`MiniMaxAI/MiniMax-M2.5`；J/V GLM→`glm-4.7`。协议未改，且尚未付费采集。 |
| 2026-08-31 | v2.2 domestic-first（Kimi 0905 + MiniMax-M1 + GLM-4.5）— 未采集即因厂商下线被取代 |
| 2026-08-31 | v2.1（Claude/Gemini + GPT dated）— 未采集，移入 expansion_roster |
| 2026-07-12 | v1 relay 矩阵（已封存，construct-invalid） |

---

## 下一步

1. 按 [`provider-setup.v2.md`](./provider-setup.v2.md) 办 **3 个账号** 并在控制台确认上表 ID 仍在售
2. 注册 provider，把 UUID 写回 `model_roster.v2.json`，重跑矩阵脚本
3. 跑 paid gate v2
