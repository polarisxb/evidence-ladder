# Stage 1 实施计划：平台底线 + 第一份 Pilot 数据

更新时间：2026-05-03  
所属路线图：[roadmap.zh-CN.md](./roadmap.zh-CN.md)  
工作流：superpowers-workflow（frame → inspect → spec → test-first → implement → review → verify → publication-safety → report）  
预计时长：1-2 周（约 4 天纯开发 + 等 API + 复盘）

---

## 0. Stage 1 在路线图中的位置

| 维度 | 信息 |
|---|---|
| 路线图位置 | Stage 1 / 6 |
| 上一 Stage | 无（v0.1.0 已发布） |
| 下一 Stage | Stage 2：Baseline 复现 + 第一张论文图 |
| 解锁的下游能力 | Pilot 数据 → Baseline 对比 → 标注 → 正式实验 |

---

## 1. Frame（目标 / 边界 / 假设）

### 1.1 目标

让平台稳住两件事：

1. **可被信任**：4 个 P1 安全问题（默认认证关闭 / SSRF / 凭据回传 / WebSocket 鉴权）全部修复，仓库公开后不会被滥用。
2. **能产数据**：Pilot Runner 能一行命令跑出 30 case × 4 变体 × 1 模型 = 120 runs 的原始数据，所有结果带 evidence_level 落库。

### 1.2 In Scope

- 平台 API 默认认证、SSRF 防护、凭据脱敏、WebSocket 鉴权
- Pilot 用例选择（30 个，按风险类别均衡）
- Quartet 变体生成器（自动从逻辑 case 派生 Clean/Attack/Quoted/Distractor）
- Pilot Runner CLI 脚本
- 跑通第一轮：GPT-4o-mini × 30 × 4 = 120 runs
- 结果导出 CSV，肉眼判断分布合理性

### 1.3 Out of Scope（Stage 2+ 才做）

- ❌ Multi-Model Batch Runner（Stage 2）
- ❌ Corrected ASR / V-ASR baseline（Stage 2）
- ❌ matplotlib 论文级图表（Stage 2）
- ❌ 标注 UI（Stage 3）
- ❌ Cohen's κ / Bootstrap CI（Stage 3）
- ❌ Agent 沙箱（Stage 5）

### 1.4 假设

- OpenAI API key 可用，预算 ~$5（Pilot 跑 120 runs，GPT-4o-mini 实测约 $0.5-2）
- 当前 AutoTest pipeline 跑得通（v0.1 已验证 35+ 测试通过）
- 现有 6 类攻击模板可以选出 30 个 Pilot 用例

### 1.5 非目标

- 不追求 Pilot 数据的"统计显著性"（120 runs 太少，本来就不能下结论）
- 不优化跑批性能（Stage 1 单线程跑能跑就行）
- 不做错误恢复机制（API 失败重跑）—— Stage 2 再做

---

## 2. Inspect（现状盘点）

### 2.1 已有可复用模块

| 模块 | 路径 | 复用方式 |
|---|---|---|
| AutoTest planner | `backend/app/services/autotest_planner.py` | Pilot Runner 调用它生成测试计划 |
| Scan runner | `backend/app/services/scan_runner.py` | Pilot Runner 通过它执行扫描 |
| Case executor | `backend/app/services/case_executor.py` | 单 case 执行 |
| Evidence arbiter | `backend/app/services/evidence_arbiter.py` | 自动给每个结果打 E0–E5 |
| AutoTest summary | `backend/app/services/autotest_summary.py` | 跑完后汇总 |
| Control variants | `backend/app/services/control_variants.py` | Quartet 变体生成的基础 |
| AutoTest scan builder | `backend/app/services/autotest_scan_builder.py` | 计划 → ScanCreate |
| 攻击模板 | `backend/app/attack_templates/*.json` | 用例池 |

### 2.2 缺失的（Stage 1 要建）

| 缺什么 | 建议位置 | 备注 |
|---|---|---|
| Quartet 变体生成器（高层 API） | `backend/app/services/quartet_generator.py` | 输入逻辑 case → 输出 4 变体 |
| Pilot Runner CLI | `backend/app/scripts/run_pilot.py` | 命令行入口 |
| CSV 导出脚本 | `backend/app/scripts/export_pilot_csv.py` | 从 ScanResult 导出 |
| 4 个安全修复 | 见 §3.1 | 跨多个文件 |

### 2.3 已知风险

| 风险 | 缓解 |
|---|---|
| `core.quotepath=false` 中文路径在 PowerShell 上的 git/grep 兼容性问题 | 已在 superpowers-workflow §6 列入 |
| `git ls-files "<中文目录>"` 才靠谱（不要用 `Select-String 中文`） | 同上 |
| `git push --tags` 会推所有 tag（含 backup） | 用 `git push origin <tag-name>` |

---

## 3. Spec / Plan（任务详表）

### 3.1 任务 1.1：P1 安全修复

| 子任务 | 描述 | 关键文件 | 预计 |
|---|---|---|---|
| 1.1a | **默认认证开启**：API 默认要求 token，匿名访问被拒；提供 `auth_required: false` 显式 opt-out 用于本地开发 | `backend/app/config.py`、`backend/app/api/__init__.py`、`backend/app/core/auth.py` | 3h |
| 1.1b | **SSRF 防护**：target URL 进入前过白名单（黑名单 loopback/内网 IP/特殊 scheme） | 新建 `backend/app/services/url_guard.py`，在 `target_client.py` 调用 | 3h |
| 1.1c | **凭据回传修复**：API 响应里不带 raw API key、不回显 system prompt 里的 secret | `backend/app/api/scans.py`、`backend/app/api/reports.py`、response sanitizer | 2h |
| 1.1d | **WebSocket 鉴权**：`/ws/scans/{task_id}` 连接前校验 token | `backend/app/api/` 下 ws 路由（找一下） | 2h |

**任务 1.1 总预计：10h（约 1.5 工作日）**

### 3.2 任务 1.2：Quartet 变体生成器

| 子任务 | 描述 | 关键文件 | 预计 |
|---|---|---|---|
| 1.2a | 设计输入/输出 schema：输入 `LogicalCase` → 输出 `[CleanVariant, AttackVariant, QuotedVariant, DistractorVariant]` | `backend/app/schemas/quartet.py`（如不存在） | 1h |
| 1.2b | Generator 主体：从攻击模板 + 任务上下文派生 4 变体 | `backend/app/services/quartet_generator.py` | 3-4h |
| 1.2c | 单元测试：覆盖 1 个 PI 用例 + 1 个 SP-Ext 用例 | `backend/tests/test_quartet_generator.py` | 1h |

**任务 1.2 总预计：5-6h（约 1 工作日）**

### 3.3 任务 1.3：Pilot Runner CLI

| 子任务 | 描述 | 关键文件 | 预计 |
|---|---|---|---|
| 1.3a | CLI 参数：`--cases <count>`、`--model <name>`、`--output-dir <path>`、`--seed <n>` | `backend/app/scripts/run_pilot.py` | 1h |
| 1.3b | 用例选择器：从 6 类攻击模板按 owasp_id 均衡选 30 个（每类 5 个） | 同上 | 1.5h |
| 1.3c | 主流程：选用例 → 调 Quartet generator → 调 AutoTest pipeline → 落库 → 打印 summary | 同上 | 2h |
| 1.3d | run_id + config snapshot：写入 `data/pilot/v0.1/run_<id>/config.json` | 同上 | 1h |

**任务 1.3 总预计：5-6h（约 1 工作日）**

### 3.4 任务 1.4：第一轮跑通

| 子任务 | 描述 | 预计 |
|---|---|---|
| 1.4a | 准备 OpenAI API key（如果还没装到 .env） | 0.2h |
| 1.4b | 跑 dry-run 模式（不真调 OpenAI，验证 pipeline） | 0.5h |
| 1.4c | 真跑：`python -m backend.app.scripts.run_pilot --cases 30 --model gpt-4o-mini --output-dir data/pilot/v0.1/run_001` | 1-2h（API 等待 + 监控） |
| 1.4d | 验证落库：前端 / SQL 看到 120 条带 evidence_level 的 ScanResult | 0.3h |

**任务 1.4 总预计：2-3h + API 等待**

### 3.5 任务 1.5：CSV 导出

| 子任务 | 描述 | 关键文件 | 预计 |
|---|---|---|---|
| 1.5a | 导出脚本：从指定 run_id 拉数据 → 写 CSV | `backend/app/scripts/export_pilot_csv.py` | 2h |
| 1.5b | CSV schema：`run_id, case_id, variant, model, evidence_level, blackbox_outcome, raw_text, judge_verdict, rule_hits, ...` | 同上 | 0.5h |
| 1.5c | 跑一遍 + 肉眼检查：分布是否合理（见 §10.1 复盘检查项） | — | 1h |

**任务 1.5 总预计：3-4h**

### 3.6 总工作量

约 **25-30h 纯开发**（按 5h/工作日 = 5-6 个工作日 = 1-2 周日历）。

---

## 4. Test-first 计划

| 任务 | Test-first 写什么 |
|---|---|
| 1.1a 默认认证 | `test_api_auth.py::test_anonymous_request_rejected` 先红，再开发 |
| 1.1b SSRF | `test_url_guard.py::test_blocks_loopback`、`test_blocks_private_ip` |
| 1.1c 凭据回传 | `test_response_sanitizer.py::test_no_api_key_in_response` |
| 1.1d WebSocket 鉴权 | `test_websocket_auth.py::test_unauthenticated_ws_rejected` |
| 1.2 Quartet generator | `test_quartet_generator.py::test_pi_case_yields_four_variants`、`test_distractor_is_benign` |
| 1.3 Pilot Runner | `test_run_pilot.py::test_dry_run_outputs_120_planned_runs` |
| 1.5 CSV 导出 | `test_export_pilot_csv.py::test_csv_contains_all_evidence_levels` |

---

## 5. 实现切片顺序

按依赖关系 + 可独立验证原则：

```text
切片 A：1.1abcd 安全修复（4 项可并行）
        ↓ （让仓库可被安全公开）
切片 B：1.2 Quartet 生成器（独立，可与 A 并行）
        ↓
切片 C：1.3 Pilot Runner CLI（依赖 B）
        ↓
切片 D：1.4 第一轮跑通（依赖 C）
        ↓
切片 E：1.5 CSV 导出 + 肉眼复盘（依赖 D）
```

每个切片完成后，独立做一次 micro-review，再进入下一切片。

---

## 6. Review 自查清单

每个切片合并前，自检：

- [ ] 涉及的代码文件是否在 `services/` / `api/` / `schemas/` / `scripts/` 等正确目录
- [ ] 新增 schema 是否符合 Pydantic v2 风格
- [ ] async/await 一致性（不要混用 sync DB 调用）
- [ ] 没有引入新的硬编码 API key 或 URL
- [ ] 所有 evidence_level 字段保持向后兼容
- [ ] 单元测试覆盖了 happy path + 至少 1 个 error path
- [ ] commit message 用 Conventional Commits 风格（`feat:` / `fix:` / `chore:` / `test:` / `docs:`）

---

## 7. Verify 命令清单

每完成一个切片后跑：

```powershell
# 后端静态检查
python -m compileall -q backend\app

# 涉及任务的单元测试
python -m pytest backend\tests\test_url_guard.py            # 1.1b 之后
python -m pytest backend\tests\test_quartet_generator.py    # 1.2 之后
python -m pytest backend\tests\test_run_pilot.py            # 1.3 之后

# 全量回归（每个切片完成后必跑一次）
python -m pytest backend\tests\

# 前端构建未破坏（如果碰了前端）
cd frontend
npm run build
```

Stage 1 全部完成时（再次跑全套）：

```powershell
python -m compileall -q backend\app
python -m pytest backend\tests\
cd frontend ; npm run build ; cd ..
```

期望：所有现有测试 + 新增测试 = 0 failures。

---

## 8. Publication-safety 检查（pre-push 必查）

```text
□ 没有 *.env 文件被 staged（只允许 *.env.example）
□ 没有 raw API key 出现在新代码 / 新测试 fixtures
□ 没有 .cursor/mcp.json
□ 没有 *.pdf 在 docs/papers/ 下被 staged
□ 没有 参赛总文件夹/ 或 *-参赛总文件夹/ 被 staged
       验证命令：git ls-files "参赛总文件夹" "2026045244-参赛总文件夹"
       期望输出：空
□ 没有"天鉴 / TianJian / JianHeng"出现在 README.md / README.en.md / 仓库 Description / Topics
       （比赛公示完全结束之前）
□ git status 看清楚要 push 的文件，最后再 push
```

---

## 9. 完成标志

Stage 1 完成 = **所有以下都满足**：

- [ ] 1.1abcd：4 项安全修复合并 + 测试全过
- [ ] 1.2：Quartet generator 单元测试通过
- [ ] 1.3：Pilot Runner CLI 可用，dry-run 输出符合预期
- [ ] 1.4：跑出 120 条带 evidence_level 的真实 ScanResult，落库可查
- [ ] 1.5：CSV 导出可用，肉眼检查分布合理（见 §10.1）
- [ ] git tag `v0.1.1` 标记 Stage 1 结束
- [ ] 在 [roadmap.zh-CN.md §11](./roadmap.zh-CN.md) 追加 Stage 1 复盘条目

---

## 10. Stage 1 复盘问题（完成后填写）

### 10.1 数据合理性自查

跑完 120 个 Pilot run 后，必须看的 5 个数字：

| 数字 | 期望范围 | 异常处理 |
|---|---|---|
| `not_evaluable_rate` (E0 比例) | < 20% | > 30% → 检查 Quartet generator / target 配置 |
| `judge_asr` 与 `text_claim_asr` 差距 | judge 显著高于 text-claim | 几乎相等 → judge 没起作用 |
| `rule_verified` (E3) 出现率 | > 5% | 0 → canary token 没注入或没匹配 |
| 平均跑一条 case 耗时 | < 30s | > 60s → Stage 2 必须做并发优化 |
| 单条 run 的 API cost | < $0.02 | > $0.05 → 不能扩展到 v0.3 规模 |

### 10.2 Stage 1 复盘条目（完成后填）

```text
日期：
完成度（0-100%）：
原计划交付 → 实际交付：
意外发现：
数字是否合理：
实际时间 vs 预估：
实际 API 成本：
是否需要调整 Stage 2：
  □ 不调整，原计划继续
  □ 微调（描述：__________）
  □ 重大调整（停下重新规划）
进入 Stage 2 的前置条件是否就绪：
```

填完同步追加到 [roadmap.zh-CN.md §11](./roadmap.zh-CN.md)。

---

## 11. 协作约定

- 本文档由徐子豪 (polarisxb) 维护；AI 助手按 superpowers-workflow 协助实现
- 任何任务的实施代码必须有对应单元测试
- 任何"完成"声明必须附带验证命令的实际输出，不接受"应该 OK"
- 发现 Stage 1 范围之外的诱惑想法，写入 [roadmap.zh-CN.md §9 反诱惑清单](./roadmap.zh-CN.md)，不立刻做

---

## 12. 与 superpowers-workflow 的对接

本计划严格遵循 superpowers-workflow 的 9 阶段：

| 阶段 | 在本文档对应章节 |
|---|---|
| Frame | §1 |
| Inspect | §2 |
| Spec/Plan | §3 |
| Test-first | §4 |
| Implement | §5 |
| Review | §6 |
| Verify | §7 |
| Publication-safety | §8 |
| Report | §9 + §10 |

参考：
- [.cursor/skills/superpowers-workflow/SKILL.md](../../.cursor/skills/superpowers-workflow/SKILL.md)
- [roadmap.zh-CN.md](./roadmap.zh-CN.md)
