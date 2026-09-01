# Provider 配置指南（Formal Pilot v2.4）

3 个国产账号，支付宝/微信。**不要把 API key 发到聊天里。**

## 0. 去办

| # | 平台 | 链接 | 控制台必须能看到 | 建议首充 |
|---|------|------|------------------|----------|
| 1 | 硅基流动 | [siliconflow.cn](https://siliconflow.cn) | `Qwen/Qwen3-32B`、`MiniMaxAI/MiniMax-M2.5`、`deepseek-ai/DeepSeek-V3.1` | ≥ ¥200 |
| 2 | 月之暗面 / Kimi | [platform.kimi.com](https://platform.kimi.com) / [platform.moonshot.cn](https://platform.moonshot.cn) | **`kimi-k3`**（官方当前默认；`api.moonshot.cn/v1`） | ¥50–100 |
| 3 | 智谱 | [open.bigmodel.cn](https://open.bigmodel.cn) | **`glm-5.3`**（官方当前默认） | ¥100–200 |

Playground 各 ping 一次。某个 ID 已下线：先别自己换，回来按「付费前替换」重冻。

## 1. Provider 槽位

| 槽位 | type | 角色 |
|------|------|------|
| `siliconflow-cn` | `siliconflow` | T1 / T3 / DeepSeek J-V |
| `moonshot-official` | `moonshot` | T2 `kimi-k3` |
| `glm-official` | `glm` | J-V `glm-5.3` |

不要单独办 DeepSeek 官方 key（只有 `deepseek-chat`）。

## 2. 写回 UUID 并重建矩阵

```bash
cd backend
python3 -m scripts.build_formal_pilot_v2_matrices
```

## 3. Paid gate

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

## 4. 采集日必记

每个模型：请求 id、`returned_model`、日期。`kimi-k3` 和 `glm-5.3` 尤其要记（产品别名）。
