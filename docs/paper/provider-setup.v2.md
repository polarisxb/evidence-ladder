# Provider 配置指南（Formal Pilot v2.2 — domestic-first）

在首次 **provider-backed** 采集前，在 Dashboard 或数据库中创建 **3 个国产 provider**，并将 UUID 写回 `backend/experiments/model_roster.v2.json`。全部平台支持国内支付（支付宝/微信），**不需要** OpenAI/Anthropic/Google 充值。

## 1. 需要创建的 Provider（3 个 key）

| 槽位名 | provider_type | 平台 / 充值入口 | 承担角色 |
|--------|---------------|-----------------|----------|
| `siliconflow-cn` | `siliconflow` | 硅基流动 siliconflow.cn（支付宝/微信充值） | T1 `Qwen/Qwen3-32B`、T3 `MiniMaxAI/MiniMax-M1-80k`、J/V `deepseek-ai/DeepSeek-V3.1` |
| `moonshot-official` | `moonshot` | Moonshot 开放平台 platform.moonshot.cn | T2 `kimi-k2-0905-preview`（dated 快照） |
| `glm-official` | `glm` | 智谱开放平台 open.bigmodel.cn | J/V `glm-4.5` |

> base_url 由后端 `PROVIDER_TYPES` 按 provider_type 自动填充，无需手工配置。
>
> **可选第 4 key（非必需）**: 若希望 DeepSeek 判官走别的通道，注意官方 API 只有滚动别名 `deepseek-chat`，会被 `allow_rolling_aliases=false` 拒绝——保持 SiliconFlow 精确 id 即可。

## 2. 建议充值额度（Phase-1 全程）

- SiliconFlow: 承担 3 个模型槽位，建议首充 ≥ ¥200
- Moonshot: 单 target，建议首充 ¥50–100
- 智谱: J/V 高频调用，建议首充 ¥100–200

（软顶预算 $3,000 见 `decisions.zh-CN.md` 签署表；以上为 gate+pilot 起步额度。）

## 3. 更新 roster UUID

编辑 `backend/experiments/model_roster.v2.json`：

```json
"provider_slots": {
  "siliconflow-cn": {
    "provider_id": "<粘贴 Dashboard 中的 UUID>",
    ...
  }
}
```

然后重新生成矩阵（hash 会随 UUID 变化，须重新归档）：

```bash
cd backend
python3 -m scripts.build_formal_pilot_v2_matrices
```

## 4. 冒烟测试（1 call / provider）

对每个 provider 发 1 次最小 completion，确认：

- `returned_model` 与矩阵中 `expected_returned_model` 一致（SiliconFlow 返回完整 id 如 `deepseek-ai/DeepSeek-V3.1`；Moonshot 返回 `kimi-k2-0905-preview`；智谱返回 `glm-4.5`）
- 溯源字段（response id 等）非空或可接受为 null 并记录
- 若 SiliconFlow 上任一 id 已下线，选等价 pinned id 替换并**重新冻结 hash**（一行 roster 改动）

## 5. Paid gate 命令（API 就绪后）

单次 gate 运行即触达全部 3 个 key（target=Moonshot，judge=SiliconFlow，verifier=智谱）：

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

通过 G1 四判据后再扩 pilot v2 / formal blocks。

## 6. 开源权重 pin 清单（写入协议附录）

| 模型 | HF repo | Revision |
|------|---------|----------|
| Qwen3-32B | `Qwen/Qwen3-32B` | `[TBD — 首次付费调用前记录]` |
| Kimi K2 0905 | `moonshotai/Kimi-K2-Instruct-0905` | `[TBD]` |
| MiniMax-M1-80k | `MiniMaxAI/MiniMax-M1-80k` | `[TBD]` |
| DeepSeek-V3.1 | `deepseek-ai/DeepSeek-V3.1` | `[TBD]` |
| GLM-4.5（参照） | `zai-org/GLM-4.5` | `[TBD]` |

- T1 decode: temperature=0.7, top_p=0.95, seed=42

## 7. Phase-2 扩展（不阻塞以上任何步骤）

Claude/Gemini/GPT 见 roster `expansion_roster`。激活前提：Phase-1 formal 归档 + 官方充值可用（或接受 AnyRouter 等第三方通道并写 Limitations 披露）。届时新增 provider、冻结 v2.3+ 矩阵，Phase-1 hash 不动。
