# Provider 配置指南（Formal Pilot v2.4）

3 个账号，**全部可以支付宝**。  
**不要把 API key 发到聊天里。**

## 0. 硅基流动：充值走 .cn，不要走 .com

`.com` 目录更全（有 Kimi-K3 / GLM-5.3），但**不支持支付宝**。  
主表**不需要**硅基上的 K3 / GLM——那两个走 Kimi / 智谱官方。  
硅基只用三个在 `.cn` 上就能买到的开源权重。

| | **.cn（用这个充值）** | .com（别为这篇去办） |
|--|--|--|
| 控制台 | https://cloud.siliconflow.cn 或 https://siliconflow.cn | cloud.siliconflow.com |
| API | `https://api.siliconflow.cn/v1` | api.siliconflow.com |
| 付款 | 支付宝 / 微信 | 通常要外卡 |
| 我们要用的 | `Qwen/Qwen3-32B`、`MiniMaxAI/MiniMax-M2.5`、`deepseek-ai/DeepSeek-V3.1` | 多出来的 K3/GLM 用不上 |

后端 `siliconflow` 默认 base_url 是 **`.cn`**。

## 1. 去办

| # | 平台 | 链接 | 控制台必须能看到 | 建议首充 |
|---|------|------|------------------|----------|
| 1 | 硅基流动 **.cn** | https://cloud.siliconflow.cn | `Qwen/Qwen3-32B`、`MiniMaxAI/MiniMax-M2.5`、`deepseek-ai/DeepSeek-V3.1` | ≥ ¥200 |
| 2 | 月之暗面 / Kimi **官方** | https://platform.kimi.com | **`kimi-k3`** | ¥50–100 |
| 3 | 智谱 **官方** | https://open.bigmodel.cn | **`glm-5.3`** | ¥100–200 |

若 `.cn` 上 `DeepSeek-V3.1` 只剩 `DeepSeek-V3.1-Terminus`，先别自己换，回来重冻。

## 1b. 千问云（https://www.qianwenai.com/models）——可以用，别当唯一钥匙

这是阿里 **2026 千问云 / 百炼** 官方门户，不是灰产中转。  
兼容接口就是仓库里已有的 `qwen`：`https://dashscope.aliyuncs.com/compatible-mode/v1`。  
能支付宝。模型很多（Qwen + 托管的 DeepSeek / Kimi / GLM）。

**可以当：**
- Target-1 的**一厂 Qwen**（比硅基托管的 `Qwen/Qwen3-32B` 更「官方」）
- 硅基某个 ID 没了时的备用通道
- 以后想钉带日期的 DashScope SKU（如 `deepseek-v4-pro-0813`）的 Phase-2

**不要当：**
- 用**一把千问云 key** 把 K3 / GLM / DeepSeek / MiniMax 全打完  
  那样 5 个家族都走阿里云 serving，独立性比「硅基 + Kimi 官方 + 智谱官方」弱，Methods 不好写。

建议：千问云 **+** Kimi 官方 **+** 智谱官方。硅基可以不办。  
若只办了千问云一个号，也能先跑 paid gate，但 Limitations 必须写「第三方家族是阿里云托管」。  
**先别自己改矩阵。** 开通后说一声，再冻 T1 的具体 DashScope ID。

## 2. Provider 槽位

| 槽位 | type | 角色 |
|------|------|------|
| `siliconflow-cn` | `siliconflow` | T1 / T3 / DeepSeek J-V（默认） |
| `qwen-dashscope`（可选） | `qwen` | 千问云 / 百炼；可替硅基的 T1，或整段硅基（须重冻 ID） |
| `moonshot-official` | `moonshot` | T2 `kimi-k3` |
| `glm-official` | `glm` | J-V `glm-5.3` |

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
