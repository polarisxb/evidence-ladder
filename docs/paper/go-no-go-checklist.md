# Go / No-Go 检查清单（付费采集前）

> 全部勾选后方可发起 provider-backed 采集。详见 `docs/paper/decisions.zh-CN.md`。

## G0 — 决策冻结

- [ ] `encoded_leak` → 次级 `approximate_leak`，不进 E3
- [ ] 主 estimand → McNemar B vs A；headline → B strong-evidence ASR
- [ ] 主弃权政策 → `e0`（采集时 `--abstention-policy e0`）
- [ ] Oracle → 归一化确定性匹配；模糊进次级指标
- [ ] v1 canary-echo runs → 不进主表（已封存）
- [ ] 开源锚点模型已选定（名称 + 权重 hash `[TBD]`）
- [ ] 预算上限已填写：`[TBD]` token / `[TBD]` USD
- [ ] 第二标注人已确定：`[TBD]`

## G1 — 环境

- [ ] 在 `experiment` 分支（或含 v2 文档的 feature 分支）
- [ ] `git status` clean
- [ ] Tag 已打：`[TBD]`
- [ ] `pytest` 全绿
- [ ] API key 已配置（不在仓库内）

## G2 — 套件

- [ ] 使用 stateful v2 套件（非 v1 canary-echo）
- [ ] 套件 `content_hash` 已归档：`[TBD]`
- [ ] 模型矩阵 hash 已归档：`[TBD]`

## G3 — 付费顺序

1. [ ] Paid gate block（~8 例）→ 四判据通过
2. [ ] Pilot v2（60–80 例）→ 仅附录
3. [ ] Formal（≥150 例）→ 主结果

## 签署

| 角色 | 姓名 | 日期 |
|---|---|---|
| Owner | XK | 2026-08-31 (defaults locked) |
| API go | | |
| Formal go | | |
