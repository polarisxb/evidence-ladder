# Provider 配置指南（Formal Pilot v2.4）

3 个账号。**硅基流动必须办 .com，不要办 .cn。**  
**不要把 API key 发到聊天里。**

## 0. `.cn` 和 `.com` 不是同一份目录

| | 硅基流动 **.com（用这个）** | 硅基流动 .cn（不要用） |
|--|--|--|
| 控制台 | https://cloud.siliconflow.com | siliconflow.cn |
| API | `https://api.siliconflow.com/v1` | `https://api.siliconflow.cn/v1` |
| 目录 | 更全：有 `moonshotai/Kimi-K3`、GLM-5.x 等 | 更瘦，常缺 K3 / GLM-5.3 |

后端 `provider_type=siliconflow` 的默认 base_url 已改为 **.com**。

## 1. 去办

| # | 平台 | 链接 | 控制台必须能看到 | 建议首充 |
|---|------|------|------------------|----------|
| 1 | **硅基流动 .com** | https://cloud.siliconflow.com | `Qwen/Qwen3-32B`、`MiniMaxAI/MiniMax-M2.5`、`deepseek-ai/DeepSeek-V3.1` | ≥ ¥200 |
| 2 | 月之暗面 / Kimi **官方** | https://platform.kimi.com | **`kimi-k3`** | ¥50–100 |
| 3 | 智谱 **官方** | https://open.bigmodel.cn | **`glm-5.3`** | ¥100–200 |

Kimi / 智谱仍走**官方**，是为了 serving 栈和硅基分开（审稿更好看）。  
硅基 .com 上的 `moonshotai/Kimi-K3`、`zai-org/GLM-5.3` 只当官方办不下来时的备选；要换 ID 必须回来重冻 hash。

## 2. Provider 槽位

| 槽位 | type | 角色 |
|------|------|------|
| `siliconflow-com` | `siliconflow` | T1 / T3 / DeepSeek J-V |
| `moonshot-official` | `moonshot` | T2 `kimi-k3` |
| `glm-official` | `glm` | J-V `glm-5.3` |

不要单独办 DeepSeek 官方 key（只有 `deepseek-chat`）。

## 3. 写回 UUID 并重建矩阵

```bash
cd backend
python3 -m scripts.build_formal_pilot_v2_matrices
```

## 4. Paid gate

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
