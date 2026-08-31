# Formal Pilot v2 — 模型花名册（v2.2 domestic-first，冻结 2026-08-31）

> **Roster version**: `formal-pilot.v2.2`（strategy: **domestic-first**）  
> **Canonical config**: `backend/experiments/model_roster.v2.json`  
> **Generated matrices**: run `cd backend && python3 -m scripts.build_formal_pilot_v2_matrices`

---

## 分期路径

- **Phase-1（现在）**: 全国产可充值 API → paid gate → pilot v2 → formal blocks。**不依赖** OpenAI/Anthropic/Google 充值。
- **Phase-2（可选，非阻塞）**: `expansion_roster` 中的 Claude/Gemini/GPT；激活条件见下文。

## 固定模型清单（Phase-1）

| 角色 | 模型 | API ID | Provider 槽位 | 家族 |
|------|------|--------|---------------|------|
| **Target-1 开源锚点** | Qwen3-32B | `Qwen/Qwen3-32B` | `siliconflow-cn` | Qwen |
| **Target-2 国产前沿（dated）** | Kimi K2 0905 | `kimi-k2-0905-preview` | `moonshot-official` | Moonshot |
| **Target-3 低成本** | MiniMax-M1-80k | `MiniMaxAI/MiniMax-M1-80k` | `siliconflow-cn` | MiniMax |
| **Judge（矩阵 A）** | DeepSeek-V3.1 | `deepseek-ai/DeepSeek-V3.1` | `siliconflow-cn` | DeepSeek |
| **Verifier（矩阵 A）** | GLM-4.5 | `glm-4.5` | `glm-official` | GLM |
| **Judge（矩阵 B）** | GLM-4.5 | `glm-4.5` | `glm-official` | GLM |
| **Verifier（矩阵 B）** | DeepSeek-V3.1 | `deepseek-ai/DeepSeek-V3.1` | `siliconflow-cn` | DeepSeek |

共 **5 个互相独立的国产家族**；J/V 跨家族、跨 provider 对调，且与所有 target 家族不重叠（无自评偏置）。

### 矩阵文件

| 文件 | content_hash | 用途 |
|------|--------------|------|
| `formal_pilot_v2_jdeepseek_vglm_models.json` | `96488a0b…` | Judge=DeepSeek-V3.1, Verifier=GLM-4.5 |
| `formal_pilot_v2_jglm_vdeepseek_models.json` | `206ec729…` | 角色互换 |
| `stateful_paid_gate_v2_models.json` | `7cb9173d…` | Paid gate（单 target: Kimi K2；一次触达全部 3 key） |

完整 hash 以生成脚本输出为准。**注意**: 替换 provider UUID 后 hash 会变化，须重跑脚本并归档新 hash。

---

## 选型理由（关键约束）

1. **DeepSeek 官方 API 不可用于冻结矩阵**: 官方仅暴露滚动别名 `deepseek-chat` / `deepseek-reasoner`，被 driver 的 `allow_rolling_aliases=false` 守卫显式拒绝（`_ROLLING_MODEL_ALIASES`）。改用 SiliconFlow 精确开源权重 id `deepseek-ai/DeepSeek-V3.1`。
2. **SiliconFlow 定位**: 第三方推理平台，但服务的是 **pinned 开源权重 checkpoint**（任何人可重新托管同一权重复现）。已列入 Limitations 披露；以逐调用 `returned_model` 校验 + 固定 decode 缓解。
3. **Kimi K2 0905**: Moonshot 官方 API 提供 **带日期的不可变快照** id，且权重开源（`moonshotai/Kimi-K2-Instruct-0905`）双重可审计——国产 target 中锚定性最强。
4. **MiniMax-M1-80k**: 复用 SiliconFlow key（零新增 key），提供第 5 个独立家族。备选替换（同为一行 roster 改动 + 重新冻结）：Qwen 官方 dated 快照（需加 DashScope key，且与 T1 同家族）。
5. **T1 锚点从 vLLM 自托管改为 SiliconFlow**: 消除自托管运维成本；HF revision 仍作为审计参照记录在 roster `weights_reference`。

## Phase-2 expansion_roster（非阻塞）

| 候选 | pinned ID | 预定角色 |
|------|-----------|----------|
| Claude Sonnet 5 | `claude-sonnet-5` | J/V 对调（vs Gemini） |
| Gemini 3.5 Flash | `gemini-3.5-flash` | J/V 对调（vs Claude） |
| GPT-5.5 dated | `gpt-5.5-2026-04-23` | target（frontier closed） |
| GPT-5.4-mini dated | `gpt-5.4-mini-2026-03-17` | target（low cost） |

**激活条件**（全部满足）: ① Phase-1 formal 归档完成；② 官方充值可用，**或**接受 AnyRouter 等第三方通道且在 Limitations 显式披露 + 逐调用 returned_model 校验；③ 冻结为 `formal-pilot.v2.3+`，不改动 Phase-1 任何 hash。

---

## 明确不使用

- **`deepseek-chat` / `deepseek-reasoner`** 官方滚动别名 — 无法 pin
- **GPT-5.6** 全系 — 无 dated 不可变快照
- **gemini-2.5-pro** — 2026-10-16 关停
- **Relay 中转** `b98979c7-…` — v2 正式采集弃用；任何不可复现 relay UUID 禁止静默替换
- **Qwen3.8 / DeepSeek V4-Pro** — 过新，锚定成熟度不足

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-31 | **v2.2 domestic-first**: 5 国产家族矩阵（Qwen/Moonshot/MiniMax targets + DeepSeek↔GLM J/V 对调）；Claude/Gemini/GPT 移入 expansion_roster（Phase-2 非阻塞）；`jclaude/jgemini` 矩阵文件移除 |
| 2026-08-31 | v2.1 花名册（Claude Sonnet 5 + Gemini 3.5 Flash 互换；GPT dated snapshots；Qwen3-32B vLLM 锚点）— 未用于采集即被 v2.2 取代 |
| 2026-07-12 | v1 relay gpt-5.4/5.5 矩阵（已封存，construct-invalid） |

---

## 下一步

1. 按 [`provider-setup.v2.md`](./provider-setup.v2.md) 注册 **3 个国产 provider**（SiliconFlow / Moonshot / 智谱）并更新 `model_roster.v2.json` 中的 UUID
2. 重跑 `build_formal_pilot_v2_matrices.py` → 归档新 hash
3. 记录 Qwen3-32B / Kimi-K2-0905 / MiniMax-M1 / DeepSeek-V3.1 的 HF 权重 revision → 写入协议附录
4. 跑 **paid gate v2**（`stateful_paid_gate_v2_models.json`，一次验证全部 3 个 key）
