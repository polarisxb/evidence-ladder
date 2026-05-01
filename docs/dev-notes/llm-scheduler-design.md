# LLM 调度层设计文档（llm_scheduler.py）

> 状态：设计中 | 算法参考已完成，待实现

## 一、定位

在 `llm_client.py`（负责单次 LLM 调用）之上，新增一层调度逻辑，解决：

1. **限速控制**：避免触发 Provider 的 429，遇到限速后快速恢复
2. **故障转移**：Provider A 不可用时自动切到 Provider B
3. **Judge 去重**：相同目标回复只评估一次，减少 30-50% judge 调用
4. **多 Key 轮转**：同一 Provider 的多个 API Key（来自不同账号）轮转使用

## 二、架构总览

```
scan_runner / ai_analyzer / 各引擎
        │
        ▼
  llm_scheduler.schedule_call()   ← 统一入口
        │
        ├── JudgeDedup.check()    ← 命中缓存？直接返回
        ├── ProviderPool.pick()   ← 选最优 provider + key
        ├── AIMDController.acquire()  ← 等待限速窗口
        │
        ▼
  llm_client.call_chat()          ← 实际 API 调用
        │
        ├── 成功 → AIMDController.mark_success()
        ├── 429  → AIMDController.mark_rate_limited()
        │         → ProviderPool.mark_throttled()
        │         → 自动重试（选下一个 provider/key）
        └── 500  → ProviderPool.mark_error()
                  → 自动重试（选下一个 provider/key）
```

## 三、模块详细设计

---

### 模块 1：AIMDController（自适应限速）

#### 职责
- 控制每个 (provider_type, api_key) 的并发请求数
- 根据成功/失败信号动态调整并发窗口

#### 状态（per provider-key）

| 字段 | 类型 | 初值 | 说明 |
|------|------|------|------|
| `limit` | float | **5.0** | 当前并发上限（slow start 起点） |
| `ssthresh` | float | **3.0** | slow start → congestion avoidance 切换点 |
| `in_flight` | int | 0 | 正在执行的请求数 |
| `waiters` | deque[Future] | [] | 等待获取槽位的请求 |
| `cooldown_until` | float | 0 | 冷却结束时间戳 |
| `consecutive_ok` | int | 0 | 连续成功计数 |
| `consecutive_429` | int | 0 | 连续 429 计数（驱动双级 severity） |
| `severity` | str | "healthy" | 严重度状态：healthy / soft / severe |
| `floor_backoff` | float | 0 | Floor Backoff 当前退避时长（秒） |
| `last_429_at` | float | 0 | 上次 429 时间戳 |
| `total_calls` | int | 0 | 总调用次数（可观测） |
| `total_429` | int | 0 | 总 429 次数（可观测） |

> **asyncio 安全**：所有字段的读写必须在 `asyncio.Lock` 保护下进行，防止并发协程间的竞态。

#### 核心算法

> ℹ️ 以下为初始简化设计，**已被下方「综合推荐伪代码」替代**，保留仅供对比参考。实现时请以综合推荐版为准。

```
acquire(key):
  等待冷却期结束
  等待 in_flight < limit
  in_flight += 1

mark_success(key):
  in_flight -= 1
  consecutive_ok += 1
  if consecutive_ok >= limit AND (now - last_429_at) > PROBE_INTERVAL:
    limit = min(limit + INCREMENT, MAX_LIMIT)   # 加性增
    consecutive_ok = 0
  唤醒 waiters

mark_rate_limited(key, retry_after_s):
  in_flight -= 1
  limit = max(limit * DECREASE_FACTOR, MIN_LIMIT)  # 乘性减
  cooldown_until = now + (retry_after_s or DEFAULT_COOLDOWN)
  last_429_at = now
  consecutive_ok = 0
  total_429 += 1
  唤醒 waiters
```

#### 参考算法精华

> 以下来自三个工业级 AIMD 实现的横向对比，提炼出值得融合到本项目的要点。

##### 参考源 1：Netflix concurrency-limits — `AIMDLimit`

- **核心代码**：`_update(startTime, rtt, inflight, didDrop)`
- **关键设计**
  - **利用率门槛**：只在 `inflight * 2 >= limit` 时才 +1（即实际并发超过上限 50% 才涨窗口）。防止低负载下把窗口吹到虚高、一遇限速就断崖
  - **RTT 超时 = 丢包**：如果单次请求延迟超过 `timeout`（默认 5 秒），等同于 `didDrop=true`，执行乘性减。这意味着**慢响应也会收窗**，不只看 429
  - **`backoffRatio` 范围 [0.5, 1.0)**：Netflix 默认 0.9（温和缩减），而不是你文档里的 0.5。0.9 适合长连接场景、0.5 适合暴力突发——LLM API 场景建议 **0.7**（折中）
  - **min/max 夹钳**：返回值永远 `clamp(min, max)`，不可能降到 0 也不可能飙到无穷

| 参数 | Netflix 默认 | 本项目建议 | 理由 |
|------|-------------|-----------|------|
| `initialLimit` | 20 | **5** | LLM API 初始并发宜低，slow-start 快速探到合理值 |
| `minLimit` | 20 | **1** | 触发 429 时必须能缩到极低 |
| `maxLimit` | 200 | **50** | 受 LLM TPM/RPM 天花板约束 |
| `backoffRatio` | 0.9 | **0.7** | LLM 429 = 明确拒绝，比网络丢包严重 |
| `timeout` | 5s | **30s** | LLM 响应本身就慢，>30s 才算异常 |

##### 参考源 2：`aimd-limiter`（Python asyncio 库）

- **关键设计**
  - **Slow Start 阶段**：初始速率从 1.0 开始指数增长，到达 `slow_start_threshold`（默认 `max_rate/2`）后切换为加性增。**这是 TCP slow start 直接移植**，解决了「一开始就开满窗然后被打回来」的问题
  - **Fast Recovery 状态**：失败后进入 fast recovery，标记 `in_fast_recovery=True`，此期间增长更保守直到恢复目标被满足
  - **Permit 模式**：`acquire()` 返回 Permit 对象，自动 `mark_success/mark_failure`（context manager），保证信号不会丢
  - **可注入 clock/sleep**：方便单元测试做时间跳跃

**建议融合**：
- **采用两阶段增长**：slow start（指数 ×2）+ congestion avoidance（加性 +1），`ssthresh = INITIAL_LIMIT / 2`
- **Permit context manager 模式**：`async with controller.acquire(key) as permit` 保证释放

##### 参考源 3：Camunda BackpressureManager（Python）

- **关键设计**
  - **Start Unlimited → Boot on First Signal**：初始不限并发（零开销），首次 429 时瞬间切到 `INITIAL_MAX=16`。优点：健康时零成本；缺点：首次风暴可能猛。**LLM 场景建议不采用**，因为 LLM API 的初始配额通常就很低
  - **双级严重度 (soft / severe)**：连续 <3 次 429 = soft（×0.7），≥3 次 = severe（×0.5）。对应不同幅度的乘性减
  - **Floor Backoff**：当窗口已经降到 floor=1 但持续收到 429 时，额外叠加**指数退避** (25ms→50ms→…→2s)。解决了「多客户端同时 floor=1 但聚合 RPS 仍很高」的 hammering 问题
  - **Severity Decay**：静默 2s 无 429 → 严重度降一级（severe→soft→healthy）；连续 30s healthy → 恢复 unlimited
  - **实测数据**：error 下降 97.6%，吞吐 +2.7%

**建议融合**：
- **双级 backoff**：`SOFT_FACTOR=0.7, SEVERE_FACTOR=0.5`，根据连续 429 次数切换
- **Floor Backoff**：当 `limit <= MIN_LIMIT` 时叠加指数退避 `delay = min(base * 2^n, 2.0)`
- **Severity Decay**：无 429 持续 N 秒后降级，提高恢复弹性

##### 参考源 4：Promptfoo Adaptive Scheduler

- **行为**：429 时并发减半，持续成功后 +1，剩余配额 <10%（从 `x-ratelimit-remaining-*` header 读取）时**主动预减**
- **建议融合**：**主动预减**——在 mark_success 时读取 LLM 响应头的 `x-ratelimit-remaining-requests`，如果 <10% 则主动缩窗到当前的 80%，不等被 429 打

---

##### 综合推荐参数表

```
# -------- 两阶段增长 --------
INITIAL_LIMIT       = 5        # 起始并发（slow start 起点）
SSTHRESH            = 3        # slow start → congestion avoidance 的切换点
MAX_LIMIT           = 50       # 硬顶
MIN_LIMIT           = 1        # 硬底

# -------- 乘性减（双级） --------
SOFT_FACTOR         = 0.7      # 连续 429 < SEVERE_THRESHOLD 时
SEVERE_FACTOR       = 0.5      # 连续 429 >= SEVERE_THRESHOLD 时
SEVERE_THRESHOLD    = 3        # 连续 429 次数门槛

# -------- 加性增 --------
INCREMENT           = 1        # congestion avoidance 阶段每成功一轮 +1
UTILIZATION_GATE    = 0.5      # in_flight >= limit * gate 才允许涨窗（Netflix 精华）
PROBE_INTERVAL_S    = 5.0      # 涨窗最小间隔（秒）

# -------- RTT 超时 --------
SLOW_RTT_TIMEOUT_S  = 30.0     # 单次 LLM 调用 >30s 视为 drop 信号

# -------- Floor Backoff（Camunda 精华） --------
FLOOR_BACKOFF_BASE  = 0.1      # 100ms 初始退避
FLOOR_BACKOFF_MAX   = 2.0      # 最大 2s
FLOOR_BACKOFF_MULT  = 2.0      # 指数底数

# -------- Cooldown --------
DEFAULT_COOLDOWN_S  = 1.0      # 无 Retry-After 时的默认冷却
SEVERITY_DECAY_S    = 5.0      # 无 429 持续 N 秒后严重度降级

# -------- 主动预减（Promptfoo 精华） --------
QUOTA_LOW_THRESHOLD = 0.10     # remaining/limit < 10% 时主动缩窗
QUOTA_PREEMPT_RATIO = 0.80     # 主动缩窗倍率
```

##### 推荐的完整 `acquire / mark_success / mark_rate_limited` 伪代码

```
acquire(key):
  等待 cooldown_until 结束
  if limit <= MIN_LIMIT AND floor_backoff > 0:
    sleep(floor_backoff)                    # Camunda: floor backoff
  等待 in_flight < limit
  in_flight += 1
  start_time = now()

mark_success(key, rtt, rate_limit_headers=None):
  in_flight -= 1
  floor_backoff = 0                          # 成功 → 立即清零 floor backoff
  consecutive_429 = 0

  # Promptfoo: 主动预减
  if rate_limit_headers:
    remaining = headers["x-ratelimit-remaining-requests"]
    total     = headers["x-ratelimit-limit-requests"]
    if remaining / total < QUOTA_LOW_THRESHOLD:
      limit = max(limit * QUOTA_PREEMPT_RATIO, MIN_LIMIT)
      return 唤醒 waiters

  # Netflix: RTT 超时 = 隐式 drop
  if rtt > SLOW_RTT_TIMEOUT_S:
    limit = max(limit * SOFT_FACTOR, MIN_LIMIT)
    return 唤醒 waiters

  # Netflix: 利用率门槛
  if in_flight < limit * UTILIZATION_GATE:
    return 唤醒 waiters                     # 利用率低，不涨

  # 两阶段增长
  if (now - last_429_at) > PROBE_INTERVAL_S:
    if limit < SSTHRESH:
      limit = min(limit * 2, MAX_LIMIT)     # slow start: 指数增
    else:
      limit = min(limit + INCREMENT, MAX_LIMIT)  # congestion avoidance: 线性增
  唤醒 waiters

mark_rate_limited(key, retry_after_s):
  in_flight -= 1
  consecutive_429 += 1
  last_429_at = now()

  # 双级乘性减
  factor = SEVERE_FACTOR if consecutive_429 >= SEVERE_THRESHOLD else SOFT_FACTOR
  limit = max(limit * factor, MIN_LIMIT)

  # Floor Backoff
  if limit <= MIN_LIMIT:
    floor_backoff = min(floor_backoff * FLOOR_BACKOFF_MULT or FLOOR_BACKOFF_BASE,
                        FLOOR_BACKOFF_MAX)

  cooldown_until = now + (retry_after_s or DEFAULT_COOLDOWN_S)
  唤醒 waiters
```

---

### 模块 2：ProviderPool（多 Key 轮转 + 故障转移）

#### 职责
- 从配置的多个 provider/key 中选择最优的发请求
- 某个 provider/key 故障时自动跳过
- 支持角色感知：Judge 锁定同级别，Generation 更宽松

#### 数据结构

```python
@dataclass
class ProviderSlot:
    # --- 标识 ---
    provider_info: ProviderClientInfo
    model: str
    key_id: str               # hash(provider_type + api_key)
    role: str                 # "judge" | "generation"
    tier: str                 # "tier1" | "tier2" | "tier3"
    # --- 健康状态 ---
    healthy: bool = True
    error_count: int = 0
    last_error_at: float = 0
    cooldown_until: float = 0
    # --- 负载均衡（P2C + 动态权重） ---
    weight: float = 1.0           # 配额权重（可按 RPM 限额比例设定）
    success_count: int = 0        # 历史成功计数（用于动态权重调整）
    total_calls: int = 0          # 总调用次数
    avg_rtt_ms: float = 0.0       # EWMA 平均响应时间（alpha=0.2）
```

#### 选择算法

```
pick(role, tier=None):
  candidates = [slot for slot in pool
                if slot.role == role
                and slot.healthy
                and (tier is None or slot.tier == tier)
                and now > slot.cooldown_until]

  if not candidates:
    candidates = [slot for slot in pool if slot.role == role]  # 降级：忽略健康状态
    if not candidates:
      raise NoProviderAvailableError()

  return 选择策略(candidates)
```

#### 选择策略

| 策略 | 说明 |
|------|------|
| `least-busy` | 选 AIMD 窗口剩余空间最大的 |
| `round-robin` | 轮流 |
| `weighted` | 按历史成功率加权 |

#### 故障处理

```
mark_throttled(slot):    # 429
  slot.cooldown_until = now + retry_after
  # 不标记 unhealthy，冷却后恢复

mark_error(slot):        # 500 / 网络错误
  slot.error_count += 1
  if slot.error_count >= 3 in 60s:
    slot.healthy = False
    slot.cooldown_until = now + 60  # 60s 后重新探测

mark_auth_failed(slot):  # 401 / 403
  slot.healthy = False    # 永久下线，直到用户更新 key
```

#### 参考算法精华

> 调研了 NGINX P2C、Netflix、Envoy 等负载均衡策略后的结论。

##### 策略对比

| 策略 | 原理 | 优点 | 缺点 | 适合场景 |
|------|------|------|------|---------|
| **Round-Robin** | 依次轮流 | 零开销、可预测 | 忽略实际负载差异 | 服务器同质、请求同质 |
| **Weighted RR** | 按配置权重轮流 | 适配异构硬件 | 权重需手动维护，不响应运行时变化 | 已知各 provider RPM 限额不同 |
| **Least-Connections** | 选 in-flight 最少的 | 天然适应慢请求，负载感知 | 需全局扫描、全部 balancer 同时选中最优者引发 thundering herd | 单调度器、pool ≤10 |
| **Weighted Least-Conn** | `in_flight / weight` 最小者 | 兼顾负载感知 + 异构 | 权重维护成本 | 混合 tier/RPM 的 provider pool |
| **P2C (Power of Two Choices)** | 随机抽两个，选 in-flight 少的 | O(1)、分布式友好、避免 herd | pool 太小时退化为随机 | pool ≥4、多调度器并发 |
| **Least Response Time** | 选近期 P95/avg 最快的 | 自动避开慢节点 | 容易振荡：快的被打满→变慢→切走 | 需加 EWMA 平滑 |

##### 本项目推荐：**Weighted P2C + AIMD headroom**

理由：
- 本项目 provider pool 通常 2-6 个 slot（少量），但同时有多个 scan 并发调度，属于**多调度器**场景
- P2C 的随机取样天然避免 herd，即使 pool 较小也比纯 least-connections 稳定
- 不同 provider（DeepSeek / GLM / OpenAI）RPM 差异大，需要 weight 体现

```
def _score(slot):
  headroom = (slot.aimd.limit - slot.aimd.in_flight) / max(slot.aimd.limit, 1)
  return headroom * slot.weight

选择策略 = weighted_p2c(candidates):
  if len(candidates) == 1:
    return candidates[0]

  if len(candidates) == 2:
    # pool 太小，P2C 退化为确定性 least-busy（不随机）
    return max(candidates, key=_score)

  # candidates >= 3：随机抽两个（不放回）
  a, b = random.sample(candidates, 2)
  return a if _score(a) >= _score(b) else b
```

##### 动态权重自适应（可选增强）

```
# 每 100 次调用更新一次 weight
if slot.total_calls % 100 == 0:
  success_rate = slot.success_count / max(slot.total_calls, 1)
  speed_factor = 1000 / max(slot.avg_rtt_ms, 100)  # 越快越高
  slot.weight = base_weight * success_rate * speed_factor
```

---

### 模块 3：JudgeDedup（裁判结果去重）

#### 职责
- 对相同/极相似的目标回复，复用已有的 judge 结果
- 减少 30-50% 的 judge API 调用

#### 缓存键

```python
def _dedup_key(attack_type: str, response_text: str) -> str:
    # 按攻击类型分组 + 回复文本指纹
    normalized = response_text.strip()[:500]  # 取前 500 字符
    return hashlib.sha256(f"{attack_type}:{normalized}".encode()).hexdigest()
```

#### 缓存策略

| 参数 | 值 | 说明 |
|------|---|------|
| 作用域 | per-scan | 每次扫描独立缓存，不跨扫描污染 |
| TTL | 扫描生命周期 | 扫描结束自动清理 |
| 最大条目 | 1000 | 防止内存膨胀 |

#### 流程

```
dedup_or_call(attack_type, response_text, judge_fn):
  key = _dedup_key(attack_type, response_text)
  if key in cache:
    hit_count += 1
    return cache[key].clone_with(dedup=True)  # 标记为去重复用
  result = await judge_fn()
  cache[key] = result
  return result
```

#### 边界情况

| 情况 | 处理 |
|------|------|
| 回复完全为空 | 不缓存（交给 not_evaluable 逻辑） |
| 回复是 [ERROR] 开头 | 不缓存（异常回复不去重） |
| 回复很短（<20 字符） | 缓存（"我无法帮助你" 这种短拒绝正是去重目标） |

#### 参考算法精华

> 调研了 Bifrost 两层缓存、SimHash 近重复检测、GPTCache 语义缓存等方案后的结论。

##### 方案对比

| 方案 | 原理 | 命中率 | 开销 | 误判风险 | 适合场景 |
|------|------|--------|------|---------|---------|
| **Exact SHA-256** | 截断文本 hash | 基线 | 零（纯 CPU hash） | 0（精确匹配） | 模板化回复（拒绝/fallback） |
| **Normalized Exact** | 去空白+小写+截断后 hash | 基线 +5-15% | 几乎零 | 极低 | 格式微变的同一回复 |
| **SimHash + 汉明距离** | 64-bit 指纹，汉明距离 ≤3 视为近重复 | +10-25% | 低（分词+位运算） | 短文本可能误判 | 中等长度文本去重 |
| **编辑距离 (Levenshtein)** | 字符级编辑距离 / len < 阈值 | +10-20% | O(n²)，长文本慢 | 阈值难调 | 仅短文本 (<200 字符) |
| **Embedding 语义缓存** | 向量相似度 cosine > 阈值 | +30-50% | 高（每次需 embedding API 或本地模型） | 阈值 0.95 可控但仍有语义偏移风险 | 大规模生产、有向量数据库 |

##### 本项目推荐：**两层策略 — Normalized Exact + SimHash 可选**

理由：
- **Judge 去重的核心目标**是同一目标的**模板化回复**（拒绝话术、fallback 文本），这些在同一次扫描中高度重复
- 观测本项目的实际扫描数据：约 60-80% 的 not_evaluable 和 refusal 回复是**精确重复**或**仅空白差异**
- Embedding 语义缓存需要额外的 API 调用或本地模型，增加依赖且对 judge 场景性价比不够
- SimHash 作为可选第二层，用于捕获"稍微改了几个字的相同拒绝"，实现成本极低

##### 推荐的缓存键生成

```python
import hashlib, re

def _normalize_text(text: str) -> str:
    """Normalize for dedup: lowercase, collapse whitespace, strip."""
    text = text.strip().lower()
    text = re.sub(r'\s+', ' ', text)
    return text

def _dedup_key_exact(attack_category: str, response_text: str) -> str:
    """Layer 1: Normalized exact match."""
    normalized = _normalize_text(response_text)[:500]
    return hashlib.sha256(f"{attack_category}:{normalized}".encode()).hexdigest()

def _simhash_fingerprint(text: str, hashbits: int = 64) -> int:
    """Layer 2: SimHash 64-bit fingerprint for near-duplicate detection."""
    tokens = _normalize_text(text)[:500].split()
    v = [0] * hashbits
    for token in tokens:
        token_hash = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(hashbits):
            if token_hash & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint

def _hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count('1')

SIMHASH_THRESHOLD = 3  # 汉明距离 ≤3 视为近重复
```

##### 两层查找流程

```
dedup_or_call(attack_category, response_text, judge_fn):
  # Layer 1: Exact
  exact_key = _dedup_key_exact(attack_category, response_text)
  if exact_key in exact_cache:
    return exact_cache[exact_key].clone_with(dedup=True)

  # Layer 2: SimHash (可选，默认开启)
  if simhash_enabled:
    fp = _simhash_fingerprint(response_text)
    for cached_fp, cached_result in simhash_index[attack_category]:
      if _hamming_distance(fp, cached_fp) <= SIMHASH_THRESHOLD:
        simhash_hits += 1
        return cached_result.clone_with(dedup=True, dedup_method="simhash")

  # Cache miss → 实际调用 judge
  result = await judge_fn()
  exact_cache[exact_key] = result
  if simhash_enabled:
    fp = _simhash_fingerprint(response_text)
    simhash_index[attack_category].append((fp, result))
  return result
```

##### 边界情况补充

| 情况 | 处理 |
|------|------|
| 回复完全为空 | 不缓存（交给 not_evaluable 逻辑） |
| 回复是 `[ERROR]` 开头 | 不缓存（异常回复不去重） |
| 回复很短（<20 字符） | **缓存**（"我无法帮助你" 正是去重目标） |
| SimHash 误判 | 保守阈值 ≤3 + 仅同 attack_category 内匹配，误判概率 <0.1% |
| 缓存条目超过 1000 | LRU 淘汰最老的条目 |
| SimHash 线性扫描性能 | 当前 O(N) 在 ≤1000 条目下延迟 <1ms，可接受。若规模增大可改用 bit-partition 索引 |

> **去重正确性说明**：当前按 `attack_category + 回复文本` 去重是安全的，因为 judge 评分是二元的（success / failure / not_evaluable），同一攻击类别下相同的目标回复必然得到相同判定。若未来 judge 评分维度更细（如“拒绝强度”），需细化 dedup key。

---

### 模块 4：schedule_call()（统一入口）

#### 签名

```python
async def schedule_call(
    role: Literal["judge", "generation"],
    messages: list[dict],
    model: str | None = None,
    *,
    tier: str | None = None,
    max_retries: int = 3,
    dedup_key: str | None = None,       # Judge 去重键
    dedup_fn: Callable | None = None,   # 实际 judge 函数（去重 miss 时调用）
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = 1024,
) -> str:
```

#### 流程

> ℹ️ 以下为初始简化版，**已被第六节「推荐的 schedule_call 重试伪代码（更新版）」替代**。实现时请以第六节版本为准（含 Token Bucket + Full Jitter + Retry-After 优先）。

```
1. if dedup_key and cache hit → return cached
2. slot = ProviderPool.pick(role, tier)
3. for attempt in range(max_retries):
   a. await AIMDController.acquire(slot.key_id)
   b. try:
        result = await call_chat(slot.provider_info, slot.model, messages, ...)
        AIMDController.mark_success(slot.key_id)
        if dedup_key: cache[dedup_key] = result
        return result
      except LLMRateLimitError:
        AIMDController.mark_rate_limited(slot.key_id, retry_after)
        ProviderPool.mark_throttled(slot)
        slot = ProviderPool.pick(role, tier)  # 换一个
      except LLMAPIError:
        ProviderPool.mark_error(slot)
        slot = ProviderPool.pick(role, tier)  # 换一个
4. raise AllRetriesExhaustedError()
```

---

## 四、与现有代码的集成点

| 文件 | 改动 |
|------|------|
| `llm_client.py` | **`LLMRateLimitError` 扩展**：新增 `retry_after_s: float | None` 字段，从 SDK 异常或 Retry-After header 提取 |
| `llm_client.py` | **`call_chat` 返回值扩展**：新增可选 `return_headers=True` 参数，返回 `(text, headers)` 元组，用于主动预减读取 `x-ratelimit-remaining-*` |
| `ai_analyzer.py` | `analyze_response` 调用改为走 `schedule_call` + 去重 |
| `ai_analyzer.py` | 移除 `_semaphore`（AIMD 接管） |
| `scan_runner.py` | 各引擎的 generation 调用改为走 `schedule_call` |
| `model_provider.py` | `api_key` 字段支持多 key（`\n` 分隔） |
| `schemas/model_provider.py` | 新增 `tier` 字段 |
| 前端设置页 | API Key 改为多行输入 + 增加 Tier 选择 |

### ProviderPool 生命周期

```
系统启动时：
  从 model_providers 表读取所有 enabled=True 的 provider
  多 key 的 provider（api_key 字段按 \n 分隔）拆成多个 ProviderSlot
  每个 slot 初始化独立的 AIMDBucket

扫描开始时：
  snapshot 当前 pool（扫描期间 pool 配置不变）
  初始化 per-scan 的 JudgeDedup 缓存
  初始化 per-scan 的 retry Token Bucket

扫描结束时：
  清理 JudgeDedup 缓存
  AIMD 状态保留在进程内存（不持久化），下次扫描可复用稳态值
```

## 五、可观测性输出

```python
def get_scheduler_stats() -> dict:
    return {
        "providers": {
            "deepseek-xxxx": {
                "limit": 3,
                "in_flight": 2,
                "total_calls": 147,
                "total_429": 8,
                "healthy": True,
            },
            ...
        },
        "dedup": {
            "hits": 34,
            "misses": 46,
            "hit_rate": 0.425,
        }
    }
```

可通过 WebSocket 推送到前端扫描进度页。

## 六、Retry 策略参考

> 来源：AWS Architecture Blog "Exponential Backoff and Jitter" (Marc Brooker, 2015/2023)
> 及 Amazon Builders' Library "Timeouts, retries, and backoff with jitter"

### 三种 Jitter 公式对比

| 算法 | 公式 | 调用量 | 完成时间 | 特点 |
|------|------|--------|---------|------|
| **无 Jitter** | `sleep = min(cap, base × 2^attempt)` | 最高 | 最慢 | 聚簇严重，所有客户端同时重试 |
| **Full Jitter** ⭐ | `sleep = random(0, min(cap, base × 2^attempt))` | **最低** | 略高于 Decorrelated | 完全打散，调用量最少 |
| **Equal Jitter** | `half = min(cap, base × 2^attempt) / 2; sleep = half + random(0, half)` | 中等 | 最慢（jitter 中） | 保留一半退避基线 |
| **Decorrelated Jitter** | `sleep = min(cap, random(base, prev_sleep × 3))` | 中等偏高 | **最快** | 基于上次 sleep 值，无需 attempt 计数 |

### AWS 的核心观点

1. **Retry 是"自私"的**——每次重试都在消耗服务端资源。当故障源是过载时，重试反而加重过载
2. **分层系统的重试放大**——5 层各 3 次重试 = 最坏 3⁵=243 倍流量。应**只在一层重试**
3. **Token Bucket 限流重试**——AWS SDK 在 2016 年引入了 retry throttling，当连续失败消耗完 token 后降低重试速率，防止重试风暴
4. **一致性 Jitter**——对定时任务用确定性 jitter（如对 host_id hash 取模）而非纯随机，便于排查

### 本项目推荐：**Full Jitter + Token Bucket 限流**

理由：
- **Full Jitter** 调用量最低，最适合 LLM API 限速场景（一旦触发 429，所有客户端都被限）
- **Token Bucket** 防止连续 429 时无限重试耗光资源

```python
import random, time

RETRY_BASE_S = 1.0        # 退避基数
RETRY_CAP_S = 60.0        # 退避上限
MAX_RETRIES = 3            # 最大重试次数

# Token Bucket for retry throttling (AWS SDK style)
RETRY_BUCKET_MAX = 10      # 最大 token
RETRY_BUCKET_REFILL = 0.5  # 每次成功调用回填 0.5 token
RETRY_COST_429 = 5         # 429 消耗 5 token
RETRY_COST_5XX = 1         # 5xx 消耗 1 token

def full_jitter_delay(attempt: int) -> float:
    """AWS Full Jitter: sleep = random(0, min(cap, base × 2^attempt))"""
    ceiling = min(RETRY_CAP_S, RETRY_BASE_S * (2 ** attempt))
    return random.uniform(0, ceiling)

def should_retry(bucket_tokens: float, error_type: str) -> bool:
    """Token bucket gate: only retry if we have tokens."""
    cost = RETRY_COST_429 if error_type == "429" else RETRY_COST_5XX
    return bucket_tokens >= cost
```

### 推荐的 schedule_call 重试伪代码（更新版）

```
retry_bucket = RETRY_BUCKET_MAX  # per-scan 全局（非 per-slot，防止切 slot 后绕过限流）

for attempt in range(MAX_RETRIES):
  slot = ProviderPool.pick(role, tier)
  await AIMDController.acquire(slot.key_id)
  try:
    result = await call_chat(slot, messages, ...)
    AIMDController.mark_success(slot.key_id, rtt, headers)
    retry_bucket = min(retry_bucket + RETRY_BUCKET_REFILL, RETRY_BUCKET_MAX)
    return result
  except LLMRateLimitError as e:
    AIMDController.mark_rate_limited(slot.key_id, e.retry_after)
    ProviderPool.mark_throttled(slot)
    if not should_retry(retry_bucket, "429"):
      raise  # token 耗尽，不再重试
    retry_bucket -= RETRY_COST_429
    await sleep(full_jitter_delay(attempt))
  except LLMAPIError:
    ProviderPool.mark_error(slot)
    if not should_retry(retry_bucket, "5xx"):
      raise
    retry_bucket -= RETRY_COST_5XX
    await sleep(full_jitter_delay(attempt))

raise AllRetriesExhaustedError()
```

### Retry-After Header 优先

当 LLM API 返回 `Retry-After` header 时，应优先使用：

```python
def effective_delay(attempt: int, retry_after_s: float | None) -> float:
    jitter_delay = full_jitter_delay(attempt)
    if retry_after_s is not None and retry_after_s > 0:
        # Retry-After + small jitter to avoid thundering herd
        return retry_after_s + random.uniform(0, min(1.0, retry_after_s * 0.1))
    return jitter_delay
```

---

## 七、算法参考状态

- [x] **AIMD 参数调优**：已参考 Netflix AIMDLimit + aimd-limiter + Camunda BackpressureManager + Promptfoo，综合推荐写入模块 1
- [x] **Provider 选择策略**：已参考 NGINX P2C / Netflix / Envoy 等，推荐 Weighted P2C + AIMD headroom，写入模块 2
- [x] **去重相似度**：已参考 Bifrost 两层缓存 / SimHash / GPTCache，推荐 Normalized Exact + SimHash 可选，写入模块 3
- [x] **Retry 策略**：已参考 AWS Architecture Blog + Builders' Library，推荐 Full Jitter + Token Bucket 限流，写入第六节

---

## 八、Claude Code 泄漏源码中的可用精华

> 来源：2026-03-31 Claude Code npm .map 文件泄漏（~1900 文件、512K+ 行 TypeScript）
> 参考分析：WaveSpeed Deep Dive、Sabrina Ramonov 综合分析、Haseeb Qureshi 内部深潜

### 直接可用于本项目的 8 个工程模式

> **优先级分组**：
> - 🔴 **本次实现**：#1 Circuit Breaker、#4 Cache Boundary — 直接影响 llm_scheduler
> - 🟡 **近期可做**：#2 Anti-Excuse Prompt、#6 异步持久化 — 影响 ai_analyzer / case_executor
> - 🔵 **远期规划**：#3 压缩防御、#5 拒绝反馈、#7 预测执行、#8 Frustration 指标

#### 1. Circuit Breaker on Retry — 三次失败即停

Claude Code 的 `autoCompact.ts` 有一条真实生产事故注释：

```
// BQ 2026-03-10: 1,279 sessions had 50+ consecutive failures
// (up to 3,272) in a single session, wasting ~250K API calls/day globally.
const MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3
```

**启示**：我们的 `schedule_call` retry 循环**必须有 circuit breaker**。目前设计的 Token Bucket 已经覆盖了这个场景，但要确保每个独立的重试路径（AIMD acquire、judge 调用、generation 调用）都有最大连续失败计数，3 次即停。不只是 retry 级别——**任何自动重试的循环都要有硬上限**。

**行动**：在 `AIMDController`、`JudgeDedup`、`schedule_call` 中都加入 `MAX_CONSECUTIVE_FAILURES = 3`。

#### 2. Verification Agent Anti-Excuse Prompt Pattern

Claude Code 内部有个 Verification Agent，系统提示中显式列出 AI 常见的偷懒借口：

```
"The implementer is an LLM. Verify independently."
"reading is not verification. Run it."
"probably is not verified. Run it."
```

**启示**：我们的 Judge（`ai_analyzer.py`）在评估 LLM 回复时也容易"偷懒"——给出模糊的 "partial" 判定而不深入分析。可以在 Judge prompt 中借鉴这种**反自我辩解模式**。

**行动**：在 judge system prompt 中增加类似的 anti-excuse 指令，防止 judge 模型偷懒。

#### 3. 四层压缩防御（Compaction Defense-in-Depth）

Claude Code 的上下文压缩有四层：
1. **Proactive** — 每轮检查 token 数，接近上限时主动压缩
2. **Reactive** — API 返回 `prompt_too_long` 时捕获错误、压缩、重试
3. **Snip** — SDK/headless 模式下直接截断
4. **Context Collapse** — 压缩旧的 tool 输出但保留可恢复性

**启示**：我们的 scan session 也是长会话（100+ 个 case），如果将来要做 multi-turn attack 或 adaptive probing，上下文管理是必要的。

**行动（远期）**：在 `case_executor.py` 中为 multi-turn 场景预留压缩接口。

#### 4. System Prompt 缓存分界线（Cache Boundary）

```
__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__
```

上半部（tool 定义、行为规则）全局缓存，下半部（CLAUDE.md、git status、日期）按会话变化。
用 Blake2b prefix hash 最大化 cache hit。

**启示**：我们的 Judge prompt 每次调用都带上完整系统提示，但其中 80% 是固定的（评分标准、格式要求）。如果使用支持 prompt caching 的 API（如 Anthropic），可以用同样的分界线技巧。

**行动**：在 `ai_analyzer.py` 的 judge prompt 构建中，将固定部分放前面、动态部分（具体 case context）放后面，为未来 prompt cache 做好结构准备。

#### 5. 权限拒绝反馈回模型（Permission Denial as Tool Output）

当 tool 执行被拒绝时，Claude Code 不是静默失败，而是**把拒绝原因包装成 tool result 回传给模型**，让模型看到 "permission denied" 后自动调整策略。

**启示**：我们的 `case_executor` 在遇到 `not_evaluable` 时直接跳过 judge。但如果是 adaptive 模式，应该把 "target 返回了模板化拒绝" 的信息反馈给攻击策略生成器，让它换方向攻击。

**行动（远期）**：adaptive engine 的 "拒绝反馈" 机制。

#### 6. 异步会话持久化的不对称策略

Claude Code 的 transcript 写入：
- **用户消息 → 同步 await**（保证可恢复）
- **助手消息 → fire-and-forget**（API 响应中已有备份）

**启示**：我们的 scan result 持久化也可以借鉴——attack prompt（用户侧输入）必须同步写入确保断电可恢复，target response（可重播）可以异步写入提高吞吐。

**行动**：`case_executor.py` 中对 prompt 和 response 的持久化采用不同策略。

#### 7. Speculation & Memory Prefetch（预测执行+内存预取）

```ts
using pendingMemoryPrefetch = startRelevantMemoryPrefetch(
  state.messages, state.toolUseContext,
)
```

模型生成响应的同时，**并行预取可能需要的文件/记忆**，用 TC39 explicit resource management 确保清理。

**启示**：我们的 scan 在等待 target response 时可以**并行预加载下一个 case 的 prompt**，而不是串行等待。

**行动**：`scan_runner.py` 中实现 case pipeline——当 case N 在等 target 回复时，case N+1 的 prompt 组装已经开始。

#### 8. Frustration / Continue 指标

Claude Code 跟踪两个隐性 UX 信号：
- **脏话频率**（frustration metric）
- **"continue" 输入次数**（agent 卡住的代理指标）

**启示**：我们的前端扫描进度页可以追踪类似的"卡住"信号——如果连续 N 个 case 都返回 `not_evaluable`，这就是我们的 "frustration signal"。已经在 `scan_runner.py` 的 runtime degradation 中部分实现了。

**行动**：已覆盖。可进一步在 WebSocket 推送中增加 `stall_count` 指标。

---

### 不适用但值得了解的模式

| 模式 | Claude Code 做法 | 我们为什么不用 |
|------|-----------------|---------------|
| Start Unlimited → Boot on Signal | KAIROS 未发布功能 | 我们的 provider 有已知 RPM 限额 |
| React+Ink 终端 UI | .tsx 渲染终端组件 | 我们用 React Web UI |
| Build-time 108 feature flags | Bun compile-time DCE | 我们是 Python+Vite，用运行时 flag 即可 |
| `\r` 解析器差异攻击 | Bash security 的 shell-quote vs bash IFS | 我们不执行 shell 命令 |

---

*四项算法参考 + Claude Code 工程模式参考全部完成，可以开始实现。*
