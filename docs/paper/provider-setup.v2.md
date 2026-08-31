# Provider 配置指南（Formal Pilot v2）

在首次 **provider-backed** 采集前，在 Dashboard 或数据库中创建 4 个 model provider，并将 UUID 写回 `backend/experiments/model_roster.v2.json`。

## 1. 需要创建的 Provider

| 槽位名 | provider_type | 用途 | 环境变量 / Key |
|--------|---------------|------|----------------|
| `openai-official` | `openai` | GPT-5.5 / GPT-5.4-mini targets | `OPENAI_API_KEY` |
| `anthropic-official` | `claude` | Claude Sonnet 5 judge/verifier | Anthropic API key |
| `google-gemini-official` | `gemini` | Gemini 3.5 Flash judge/verifier | Google AI API key |
| `vllm-qwen3-anchor` | `custom` | Qwen3-32B 自托管 | vLLM base URL + key（如有） |

## 2. 更新 roster UUID

编辑 `backend/experiments/model_roster.v2.json`：

```json
"provider_slots": {
  "openai-official": {
    "provider_id": "<粘贴 Dashboard 中的 UUID>",
    ...
  }
}
```

然后重新生成矩阵：

```bash
cd backend
python3 -m scripts.build_formal_pilot_v2_matrices
```

## 3. 冒烟测试（1 call / provider）

对每个 provider 发 1 次最小 completion，确认：

- `returned_model` 与矩阵中 `expected_returned_model` 一致
- 溯源字段（`system_fingerprint` / response id）非空或可接受为 null 并记录

## 4. Paid gate 命令（API 就绪后）

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

## 5. 开源锚点 pin 清单（写入协议附录）

- HF repo: `Qwen/Qwen3-32B`
- Revision commit: `[TBD]`
- vLLM version: `[TBD]`
- Decode: temperature=0.7, top_p=0.95, seed=42
