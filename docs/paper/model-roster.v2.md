# Formal Pilot v2 — 模型花名册（冻结 2026-08-31）

> **Roster version**: `formal-pilot.v2.1`  
> **Canonical config**: `backend/experiments/model_roster.v2.json`  
> **Generated matrices**: run `cd backend && python3 -m scripts.build_formal_pilot_v2_matrices`

---

## 固定模型清单

| 角色 | 模型 | API ID / 部署 | Provider 槽位 |
|------|------|---------------|---------------|
| **Target-1 开源锚点** | Qwen3-32B-Instruct | `Qwen/Qwen3-32B`（vLLM 自托管） | `vllm-qwen3-anchor` |
| **Target-2 前沿闭源** | GPT-5.5 dated | `gpt-5.5-2026-04-23` | `openai-official` |
| **Target-3 低成本** | GPT-5.4-mini dated | `gpt-5.4-mini-2026-03-17` | `openai-official` |
| **Judge（矩阵 A）** | Claude Sonnet 5 | `claude-sonnet-5` | `anthropic-official` |
| **Verifier（矩阵 A）** | Gemini 3.5 Flash | `gemini-3.5-flash` | `google-gemini-official` |
| **Judge（矩阵 B）** | Gemini 3.5 Flash | `gemini-3.5-flash` | `google-gemini-official` |
| **Verifier（矩阵 B）** | Claude Sonnet 5 | `claude-sonnet-5` | `anthropic-official` |

### 矩阵文件

| 文件 | content_hash | 用途 |
|------|--------------|------|
| `formal_pilot_v2_jclaude_vgemini_models.json` | `45c4fdd…` | Judge=Claude, Verifier=Gemini |
| `formal_pilot_v2_jgemini_vclaude_models.json` | `9626a52…` | 角色互换 |
| `stateful_paid_gate_v2_models.json` | `1383875…` | Paid gate（单 target: GPT-5.5） |

完整 hash 以生成脚本输出为准。

---

## 明确不使用（2026-08 调研结论）

- **GPT-5.6** 全系 — 无 dated 不可变快照
- **gemini-2.5-pro** — 2026-10-16 关停
- **Relay 中转** `b98979c7-…` — v2 正式采集弃用
- **Qwen3.8 / DeepSeek V4-Pro** — 过新，锚定成熟度不足

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-31 | v2.1 花名册定稿：Claude Sonnet 5 + Gemini 3.5 Flash 互换；GPT dated snapshots；Qwen3-32B 锚点 |
| 2026-07-12 | v1 relay gpt-5.4/5.5 矩阵（已封存，construct-invalid） |

---

## 下一步

1. 按 [`provider-setup.v2.md`](./provider-setup.v2.md) 注册 4 个 provider 并更新 `model_roster.v2.json` 中的 UUID
2. 重跑 `build_formal_pilot_v2_matrices.py`
3. Pin Qwen3 HF revision → 写入协议附录
4. 配置 API keys → 跑 **paid gate v2**（`stateful_paid_gate_v2_models.json`）
