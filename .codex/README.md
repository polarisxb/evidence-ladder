# 项目级 Codex Skills 总览

本目录存放本仓库的项目级 Codex 资产，核心是 `.codex/skills/` 下的 11 个 skill。

这些 skill 的目标不是替代仓库文档，而是给进入本仓库工作的 Codex 会话和项目成员提供一套稳定的“如何做事”入口，减少重复说明和上下文漂移。

如果你在这个仓库里工作，默认先看：

- 仓库级约定：[project-conventions](./skills/project-conventions/SKILL.md)
- 旧 `.cursor/rules` 的迁移说明：[RULES_MIGRATION.md](./RULES_MIGRATION.md)

## 项目内 Codex 资产说明

- `.codex/skills/`：项目级 skill 正文目录
- `SKILL.md`：skill 的使用说明和操作约束
- `agents/openai.yaml`：skill 的 UI 元数据
- `references/`：仅在个别 skill 下存在，用于承载补充参考材料

本仓库当前共维护 11 个项目级 skill：

| Skill | 解决什么问题 | 何时使用 | 常和谁一起用 | 路径 |
| --- | --- | --- | --- | --- |
| `project-conventions` | 仓库级架构、模块边界、通用约定 | 进入仓库、跨模块改动、拿不准仓库做法时 | `fastapi-patterns`、`react-dashboard`、`verification-before-completion` | [`.codex/skills/project-conventions/SKILL.md`](./skills/project-conventions/SKILL.md) |
| `superpowers-workflow` | Superpowers 风格的结构化开发流程适配层 | 用户提到 Superpowers、广义功能开发、需要 brainstorm/spec/plan/TDD/review/verify 流程时 | `project-conventions`、任务领域 skill、`verification-before-completion` | [`.codex/skills/superpowers-workflow/SKILL.md`](./skills/superpowers-workflow/SKILL.md) |
| `ai-security-knowledge` | AI/LLM 安全领域知识、攻击分类、防御思路 | 调整攻击覆盖、响应分析、风险映射时 | `attack-template-authoring`、`openai-integration` | [`.codex/skills/ai-security-knowledge/SKILL.md`](./skills/ai-security-knowledge/SKILL.md) |
| `attack-template-authoring` | 攻击模板 JSON 的编写、命名、结构约束 | 新增或修改 `backend/app/attack_templates/**/*.json` 时 | `ai-security-knowledge`、`fastapi-patterns` | [`.codex/skills/attack-template-authoring/SKILL.md`](./skills/attack-template-authoring/SKILL.md) |
| `defense-in-depth` | 分层校验、输入边界、防止脏数据穿透 | 修高风险 bug、补校验、设计安全边界时 | `fastapi-patterns`、`systematic-debugging` | [`.codex/skills/defense-in-depth/SKILL.md`](./skills/defense-in-depth/SKILL.md) |
| `fastapi-patterns` | 后端 API、服务层、异步流程、数据模型约定 | 改 FastAPI 路由、服务、数据库模型时 | `project-conventions`、`defense-in-depth`、`verification-before-completion` | [`.codex/skills/fastapi-patterns/SKILL.md`](./skills/fastapi-patterns/SKILL.md) |
| `frontend-design` | 前端视觉方向、页面风格、交互观感 | 做新页面、重做视觉、补高质量 UI 时 | `react-dashboard` | [`.codex/skills/frontend-design/SKILL.md`](./skills/frontend-design/SKILL.md) |
| `openai-integration` | OpenAI 集成、结构化输出、分析提示词设计 | 改 LLM 调用、分析器、prompt 结构时 | `ai-security-knowledge`、`fastapi-patterns` | [`.codex/skills/openai-integration/SKILL.md`](./skills/openai-integration/SKILL.md) |
| `react-dashboard` | React 页面、状态流、数据展示和交互约定 | 改 dashboard、结果页、报告页、表单时 | `project-conventions`、`frontend-design`、`verification-before-completion` | [`.codex/skills/react-dashboard/SKILL.md`](./skills/react-dashboard/SKILL.md) |
| `systematic-debugging` | 四阶段排障，先定位根因再修 | 遇到 bug、回归、异常行为、测试失败时 | `defense-in-depth`、`verification-before-completion` | [`.codex/skills/systematic-debugging/SKILL.md`](./skills/systematic-debugging/SKILL.md) |
| `verification-before-completion` | 交付前验证、证据先于结论 | 提交前、提测前、宣称“完成”之前 | 所有实现类 skill | [`.codex/skills/verification-before-completion/SKILL.md`](./skills/verification-before-completion/SKILL.md) |

## 按任务选 Skill

如果不知道先看哪个 skill，可以按任务类型选：

- 后端接口、服务层、数据模型：先看 [project-conventions](./skills/project-conventions/SKILL.md)，再看 [fastapi-patterns](./skills/fastapi-patterns/SKILL.md)
- 前端页面、结果表格、报告交互：先看 [project-conventions](./skills/project-conventions/SKILL.md)，再看 [react-dashboard](./skills/react-dashboard/SKILL.md)
- Superpowers 风格结构化开发：先看 [superpowers-workflow](./skills/superpowers-workflow/SKILL.md)，再按任务类型加载本仓库已有 skill
- 前端视觉升级或新页面设计：在 `react-dashboard` 基础上再看 [frontend-design](./skills/frontend-design/SKILL.md)
- 攻击模板和 payload 覆盖：先看 [attack-template-authoring](./skills/attack-template-authoring/SKILL.md)，需要领域背景时再看 [ai-security-knowledge](./skills/ai-security-knowledge/SKILL.md)
- LLM 分析器、结构化输出、OpenAI 调用：先看 [openai-integration](./skills/openai-integration/SKILL.md)，再结合 [ai-security-knowledge](./skills/ai-security-knowledge/SKILL.md)
- 安全边界、输入校验、容错：看 [defense-in-depth](./skills/defense-in-depth/SKILL.md)
- 排查异常、定位回归：看 [systematic-debugging](./skills/systematic-debugging/SKILL.md)
- 准备交付、声称完成、准备提 PR：最后看 [verification-before-completion](./skills/verification-before-completion/SKILL.md)

推荐的默认组合关系：

- 仓库级基线：`project-conventions`
- 结构化开发入口：`superpowers-workflow` + `project-conventions`
- 后端实现：`project-conventions` + `fastapi-patterns`
- 前端实现：`project-conventions` + `react-dashboard`
- 攻击模板：`attack-template-authoring` + `ai-security-knowledge`
- LLM 相关实现：`openai-integration` + `ai-security-knowledge`
- 交付前检查：任意实现类 skill + `verification-before-completion`

## 典型开发任务快速手册

如果你只想快速开工，可以直接按下面的顺序选 skill：

### 1. 新开一个后端功能

阅读顺序：

1. [project-conventions](./skills/project-conventions/SKILL.md)
2. [fastapi-patterns](./skills/fastapi-patterns/SKILL.md)
3. [defense-in-depth](./skills/defense-in-depth/SKILL.md)
4. [verification-before-completion](./skills/verification-before-completion/SKILL.md)

适用场景：

- 新增 API
- 改服务层逻辑
- 新增模型或 schema

### 2. 用 Superpowers 流程做一个较大的功能或改造

阅读顺序：

1. [superpowers-workflow](./skills/superpowers-workflow/SKILL.md)
2. [project-conventions](./skills/project-conventions/SKILL.md)
3. 按实际改动面选择后端、前端、攻击模板或 LLM 相关 skill
4. [verification-before-completion](./skills/verification-before-completion/SKILL.md)

适用场景：

- 用户明确提到 Superpowers
- 跨前后端功能开发
- 需要先梳理 spec、测试计划、分阶段实现和 review gate 的任务

### 3. 新开一个前端页面或重做结果页

阅读顺序：

1. [project-conventions](./skills/project-conventions/SKILL.md)
2. [react-dashboard](./skills/react-dashboard/SKILL.md)
3. [frontend-design](./skills/frontend-design/SKILL.md)
4. [verification-before-completion](./skills/verification-before-completion/SKILL.md)

适用场景：

- 新建页面
- 改 dashboard
- 调整结果页、报告页、表单交互

### 4. 修改攻击模板或补新的 payload

阅读顺序：

1. [attack-template-authoring](./skills/attack-template-authoring/SKILL.md)
2. [ai-security-knowledge](./skills/ai-security-knowledge/SKILL.md)
3. [verification-before-completion](./skills/verification-before-completion/SKILL.md)

适用场景：

- 新增模板分类
- 扩攻击覆盖
- 调整成功指示器或模板结构

### 5. 修改分析器、Judge 或 OpenAI 调用

阅读顺序：

1. [project-conventions](./skills/project-conventions/SKILL.md)
2. [openai-integration](./skills/openai-integration/SKILL.md)
3. [ai-security-knowledge](./skills/ai-security-knowledge/SKILL.md)
4. [verification-before-completion](./skills/verification-before-completion/SKILL.md)

适用场景：

- 改结构化输出
- 改分析 prompt
- 改模型调用、判定逻辑、成本控制

### 6. 修 bug 或排查回归

阅读顺序：

1. [systematic-debugging](./skills/systematic-debugging/SKILL.md)
2. [project-conventions](./skills/project-conventions/SKILL.md)
3. 视问题类型补看 [fastapi-patterns](./skills/fastapi-patterns/SKILL.md) 或 [react-dashboard](./skills/react-dashboard/SKILL.md)
4. [verification-before-completion](./skills/verification-before-completion/SKILL.md)

适用场景：

- 接口异常
- 页面行为不对
- 构建失败
- 线上回归定位

### 7. 拿不准从哪里开始

默认顺序：

1. [project-conventions](./skills/project-conventions/SKILL.md)
2. 按任务类型选择一个实现类 skill
3. 结束前看 [verification-before-completion](./skills/verification-before-completion/SKILL.md)

## 与 `.cursor/rules` 的对应关系

本仓库保留原始 `.cursor/rules` 仅供参考，Codex 实际使用的等价能力已经迁移到项目级 skill。

对应关系如下：

- `.cursor/rules/project.mdc` -> [project-conventions](./skills/project-conventions/SKILL.md)
- `.cursor/rules/backend-python.mdc` -> [fastapi-patterns](./skills/fastapi-patterns/SKILL.md)
- `.cursor/rules/frontend-react.mdc` -> [react-dashboard](./skills/react-dashboard/SKILL.md)
- `.cursor/rules/attack-templates.mdc` -> [attack-template-authoring](./skills/attack-template-authoring/SKILL.md)
- `.cursor/rules/cursorfather.mdc` -> 未原样迁移；可适配部分已收敛进 [project-conventions](./skills/project-conventions/SKILL.md)

更完整的迁移说明见：[RULES_MIGRATION.md](./RULES_MIGRATION.md)

## 维护与更新约定

- 新增项目级 skill 时，同步更新本页的总览表和“按任务选 skill”部分
- 调整 skill 名称、用途或触发边界时，同步更新 `agents/openai.yaml`
- 如果变更涉及旧 `.cursor/rules` 的迁移关系，同步更新 [RULES_MIGRATION.md](./RULES_MIGRATION.md)
- 如果一个任务跨前后端或跨实现层，默认先回到 [project-conventions](./skills/project-conventions/SKILL.md) 校准仓库级约定
- 在本仓库内，准备交付前默认再看一次 [verification-before-completion](./skills/verification-before-completion/SKILL.md)

## 与 `.cursor/skills/` 的双目录同步约定

为了让同一套 skill 在 Codex CLI 和 Cursor IDE 两个环境里都可用，本仓库在
`.codex/skills/` 之外，也维护一份 `.cursor/skills/`（Cursor 通过 `description`
frontmatter 自动激活 skill）。

**两份 skill 文件必须保持功能性一致：**

- 修改 `.codex/skills/<name>/SKILL.md` 时，必须在同一 commit 里同步修改
  `.cursor/skills/<name>/SKILL.md`，反之亦然
- 新增 skill 时，必须在两个目录同时创建对应子目录与 `SKILL.md`
- `.cursor/skills/<name>/SKILL.md` 的 frontmatter 不需要 `Source:` 字段
  （Cursor 不需要），其余 markdown 内容与 Codex 版本保持一致
- `.cursor/skills/` 的索引位于 [`../.cursor/skills/README.md`](../.cursor/skills/README.md)，
  与本文件互为镜像（结构对齐，措辞可按目标受众微调）

简单 sanity check（PowerShell）：

```powershell
$cursor = Get-ChildItem .cursor/skills -Directory | Select-Object -ExpandProperty Name
$codex  = Get-ChildItem .codex/skills  -Directory | Select-Object -ExpandProperty Name
Compare-Object $cursor $codex -PassThru
```

输出为空即为同步状态正确；任何只在一侧出现的 skill 都需要补齐。

> 历史背景：早期只维护 `.codex/skills/`，导致 Cursor IDE 实际无法激活
> `superpowers-workflow` / `project-conventions` / `attack-template-authoring`
> 等核心 skill。2026-05-03 之后，强制要求双目录同步。
