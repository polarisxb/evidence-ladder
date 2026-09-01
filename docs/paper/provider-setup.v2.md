# Provider 配置指南（Formal Pilot v2.3 — domestic-first）

在首次 **provider-backed** 采集前，创建 **3 个国产 provider**，把 UUID 写回 `backend/experiments/model_roster.v2.json`。全部支持支付宝/微信，不需要外卡。

## 0. 你去办的账号（照这个买）

| # | 平台 | 注册 / 充值 | 控制台里必须能看到的模型 ID | 建议首充 |
|---|------|-------------|------------------------------|----------|
| 1 | **硅基流动 SiliconFlow** | [siliconflow.cn](https://siliconflow.cn) / [cloud.siliconflow.com](https://cloud.siliconflow.com) | `Qwen/Qwen3-32B`、`MiniMaxAI/MiniMax-M2.5`、`deepseek-ai/DeepSeek-V3.1` | ≥ ¥200 |
| 2 | **月之暗面 / Kimi** | [platform.moonshot.cn](https://platform.moonshot.cn) 或 [platform.kimi.com](https://platform.kimi.com)（同一家，`api.moonshot.cn/v1`） | **`kimi-k2.6`**（不要买/不要点 `kimi-k3` 当主表） | ¥50–100 |
| 3 | **智谱** | [open.bigmodel.cn](https://open.bigmodel.cn) | **`glm-4.7`**（不要把 `glm-5.3` 当主表） | ¥100–200 |

办完后在各平台 playground 各打一句「ping」，确认返回模型名与上表一致。**不要把 API key 发到聊天里**，只回「三个平台已开通、ID 对得上」。

若控制台里某个 ID 已下线：先别换别的，回来改 roster 再冻 hash。

## 1. 需要创建的 Provider（3 个 key）

| 槽位名 | provider_type | 承担角色 |
|--------|---------------|----------|
| `siliconflow-cn` | `siliconflow` | T1 `Qwen/Qwen3-32B`、T3 `MiniMaxAI/MiniMax-M2.5`、J/V `deepseek-ai/DeepSeek-V3.1` |
| `moonshot-official` | `moonshot` | T2 `kimi-k2.6` |
| `glm-official` | `glm` | J/V `glm-4.7` |

> base_url 由后端 `PROVIDER_TYPES` 自动填：SiliconFlow `https://api.siliconflow.cn/v1`，Moonshot `https://api.moonshot.cn/v1`，智谱 `https://open.bigmodel.cn/api/paas/v4`。
>
> 不要单独办 DeepSeek 官方 key：官方只有 `deepseek-chat`，会被冻结矩阵拒绝。

## 2. 更新 roster UUID

编辑 `backend/experiments/model_roster.v2.json` 的 `provider_slots.*.provider_id`，然后：

```bash
cd backend
python3 -m scripts.build_formal_pilot_v2_matrices
```

## 3. 冒烟（1 call / provider）

确认 `returned_model` 分别为 `Qwen/Qwen3-32B` 或 `deepseek-ai/DeepSeek-V3.1` / `MiniMaxAI/MiniMax-M2.5`、`kimi-k2.6`、`glm-4.7`。

## 4. Paid gate（API 就绪后）

一次跑完会打到全部 3 个 key（target=Moonshot，judge=SiliconFlow，verifier=智谱）：

```bash
cd backend
python3 -m scripts.run_experiment \
  --suite experiments/stateful_paid_gate_suite.json \
  --models experiments/stateful_paid_gate_v2_models.json \
  --out experiment-output/stateful-paid-gate-v2-block1 \
  --collection-block-id paid-gate-v2-block1 \
  --execution-seed 1301 \
  --bootstrap-seed 2301 \
  --abstention-policy e0
```

## 5. 开源权重 pin（写入协议附录）

| 模型 | HF / 官方参照 | Revision |
|------|---------------|----------|
| Qwen3-32B | `Qwen/Qwen3-32B` | `[TBD]` |
| Kimi K2.6 | Moonshot 官方命名世代 | 采集日 + returned_model |
| MiniMax-M2.5 | `MiniMaxAI/MiniMax-M2.5` | `[TBD]` |
| DeepSeek-V3.1 | `deepseek-ai/DeepSeek-V3.1` | `[TBD]` |
| GLM-4.7 | 智谱官方 `glm-4.7` | 采集日 + returned_model |

T1 decode: temperature=0.7, top_p=0.95, seed=42

## 6. Phase-2

Claude/Gemini/GPT 见 roster `expansion_roster`。不阻塞以上步骤。
