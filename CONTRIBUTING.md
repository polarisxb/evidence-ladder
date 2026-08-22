# 贡献指南 / Contributing

本仓库采用 **分支 → PR → CI 全绿 → 合并** 的工作流。`main` 是受保护分支，**禁止直接 push**，所有改动都要走 Pull Request 并通过 CI。

---

## 分支命名 / Branch naming

按改动类型加短横线描述，例如：

- `feat/<topic>` — 新功能
- `fix/<topic>` — 缺陷修复
- `chore/<topic>` — 基建/杂项（CI、依赖、配置）
- `test/<topic>` — 仅测试
- `docs/<topic>` — 仅文档

从最新的 `main` 切出分支：

```bash
git checkout main && git pull
git checkout -b feat/my-change
```

## 提交信息 / Commit messages

使用英文 + [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>
```

`type` ∈ `feat | fix | chore | test | docs | refactor | perf | ci`。例如：
`feat(canary): channel-aware provenance tracer`。

## 提交前本地自检 / Local checks before pushing

CI 会跑这四项，提前在本地过一遍能省一轮往返：

```bash
# 后端
cd backend
pytest app/tests tests    # 与 CI 相同；需 AUTH_REQUIRED=false 等测试 env
ruff check app tests conftest.py

# 前端
cd frontend
npm run test              # vitest
npm run build             # tsc + vite build
```

## 开 PR / Opening a PR

1. push 分支：`git push -u origin <branch>`
2. 在 GitHub 上开 PR 进 `main`，按 PR 模板填写。
3. 等 CI 三个 check 全绿：
   - **Backend tests (pytest)**
   - **Backend lint (ruff)**
   - **Frontend test + build (vitest + tsc + vite)**
4. CI 绿后合并（默认 **squash**，保持 `main` 历史线性）。
5. 合并后删除已合并的分支。

## CI / 持续集成

工作流定义在 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)，在 `push` 和 `pull_request` 上触发。`main` 的分支保护要求上述三个 check 全部通过后才能合并。

## 不要提交的内容 / Do not commit

- `.env` / 任何密钥（已在 `.gitignore`）
- 运行期产物：`backend/data/`、构建产物 `frontend/dist/`
- 临时脚本/笔记：`.tmp_*`、`*_tmp.md`
- 参赛/私有材料（见 `.gitignore` 中相关条目）
- 未发表论文稿与本地工程笔记：`docs/paper/`、`docs/dev/`、`docs/guides/`、`_归档_比赛材料/`

### 安装发布防护钩子 / Install the publish guard

有一部分分支与路径是**本地专用**的（未发表草稿、参赛材料、内部工作文档）。`.gitignore` 挡不住它们——那些文件在专门用于版本化它们的分支上是**被跟踪的**，而 `.gitignore` 对已跟踪文件无效。所以闸门是一个 `pre-push` 钩子。

**每个 clone 装一次**（钩子目录不受版本控制，clone 不会带过来）：

```bash
sh scripts/install-hooks.sh
```

它会拒绝推送私有分支，以及任何触碰不可发布路径的推送。确有需要时用 `git push --no-verify` 绕过。
