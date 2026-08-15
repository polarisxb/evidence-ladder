# 安装与配置说明

| 项目 | 内容 |
|------|------|
| **文档类型** | 部署与运维指南 |
| **版本** | 1.1 |
| **文档状态** | 正式发布 |
| **读者对象** | 部署工程师、本地开发者、竞赛环境搭建人员 |
| **关联文档** | [用户操作手册](./user-guide.md) · [攻击模板库说明](./attack-templates-guide.md) |

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.1 | 2026-04 | 版式专业化；补充摘要与文档交叉引用 |
| 1.0 | 2026-04 | 初版 |

---

## 摘要

本文说明 Evidence-Ladder 在 **Docker** 与 **本地手动** 两种路径下的安装步骤、端口约定、环境变量与模型供应商配置优先级。生产部署请结合第 8 节加固网络与密钥管理。日志与任务时间以 **服务器/容器本地时区** 为准；若需统一为北京时间，请在编排或主机层面设置 `TZ=Asia/Shanghai`。

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速部署（Docker）](#2-快速部署docker)
3. [手动部署](#3-手动部署)
4. [环境变量配置](#4-环境变量配置)
5. [模型供应商配置](#5-模型供应商配置)
6. [验证部署](#6-验证部署)
7. [常见部署问题](#7-常见部署问题)
8. [生产环境建议](#8-生产环境建议)
9. [仓库目录结构](#9-仓库目录结构)

---

## 1. 环境要求

### 1.1 Docker 部署（推荐）

| 组件 | 版本要求 |
|------|----------|
| Docker | 20.10+ |
| Docker Compose | v2.0+ |
| 内存 | ≥ 2 GB |
| 磁盘 | ≥ 1 GB（含镜像与数据卷） |

### 1.2 手动部署

| 组件 | 版本要求 |
|------|----------|
| Python | 3.11+ |
| Node.js | 20+ |
| npm | 9+ |

### 1.3 外部依赖

| 依赖 | 用途 | 必需性 |
|------|------|--------|
| OpenAI 兼容 API Key | 裁判分析、攻击变体生成等 | 必需 |
| Anthropic API Key | Claude 原生目标类型 | 可选 |

---

## 2. 快速部署（Docker）

### 2.1 启动步骤

```bash
git clone <repo-url> ai-security
cd ai-security

cp .env.example .env
# 编辑根目录 .env，填入 API Key（见第 4 节）

docker-compose up --build
```

### 2.2 服务端口

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | Web UI |
| 后端 API | http://localhost:8000 | FastAPI |
| OpenAPI 文档 | http://localhost:8000/docs | Swagger |

### 2.3 Compose 结构说明

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./.env          # 统一读取根目录 .env
    volumes:
      - ./backend/data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      backend:
        condition: service_healthy
```

### 2.4 常用命令

```bash
docker-compose down
docker-compose logs -f
docker-compose logs -f backend
```

---

## 3. 手动部署

### 3.1 后端

```bash
# 根目录配置（首次需做，后续共用）
cp .env.example .env
# 编辑根目录 .env，填入 API Key 等配置

cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**主要 Python 依赖（节选）**：

| 包 | 用途 |
|----|------|
| fastapi / uvicorn | Web 与 ASGI |
| sqlalchemy[asyncio] / aiosqlite | 异步 ORM 与 SQLite |
| pydantic / pydantic-settings | 校验与配置 |
| openai / anthropic | 模型 SDK |
| httpx | HTTP 客户端 |
| jinja2 / weasyprint | 报告渲染 |
| cvss | 风险评分辅助 |

版本下界以 `requirements.txt` 为准。

### 3.2 前端

```bash
cd frontend
npm install
npm run dev
npm run build
```

构建产物位于 `frontend/dist/`。

**技术栈（节选）**：React 18、TypeScript（严格）、Vite、TailwindCSS、Recharts。

### 3.3 数据库

默认使用 **SQLite**，无需单独安装数据库服务。

| 项目 | 说明 |
|------|------|
| 默认路径 | `backend/data/app.db` |
| 初始化 | 首次启动时创建库表 |
| 自定义 | 通过环境变量 `DATABASE_URL` 覆盖 |

---

## 4. 环境变量配置

### 4.1 统一配置文件

所有服务（后端、ShopBot 靶机、FinanceBot 靶机）**共用项目根目录的 `.env`**，只需维护一个文件。

```
ai-security/
├── .env              ← 唯一配置文件（改这个就够了）
├── .env.example      ← 模板
├── backend/          → 自动读取根目录 .env
├── mock_targets/
│   ├── shopbot/      → 自动读取根目录 .env
│   └── financebot/   → 自动读取根目录 .env
```

编辑根目录 `.env`，典型配置如下（示例值须替换为真实密钥）：

```bash
# ─── 共享凭据（所有服务通用）───────────────
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.deepseek.com/v1

# ─── 后端：安全分析引擎 ────────────────────
OPENAI_MODEL=deepseek-reasoner       # Judge 模型（分析攻击结果）
OPENAI_MINI_MODEL=deepseek-chat      # 生成模型（生成攻击变体）
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
CORS_ORIGINS=["http://localhost:5173"]
ALLOW_LOCALHOST_TARGETS=true

# ─── 靶机：ShopBot & FinanceBot ───────────
TARGET_MODEL=deepseek-chat            # 靶机对话模型
```

### 4.2 变量说明

| 变量 | 作用范围 | 说明 |
|------|----------|------|
| `OPENAI_API_KEY` | 全部服务 | API 密钥，所有服务共用 |
| `OPENAI_BASE_URL` | 全部服务 | API 端点，所有服务共用 |
| `OPENAI_MODEL` | 后端 | Judge 模型，用于分析攻击结果（需强推理能力） |
| `OPENAI_MINI_MODEL` | 后端 | 生成模型，用于攻击变体生成（快速/经济即可） |
| `TARGET_MODEL` | 靶机 | 靶机 AI 对话用的模型（经济模型即可） |
| `DATABASE_URL` | 后端 | 数据库连接串 |
| `CORS_ORIGINS` | 后端 | 允许的前端 Origin |
| `ALLOW_LOCALHOST_TARGETS` | 后端 | 是否允许扫描 localhost 目标 |

### 4.3 配置优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 最高 | 系统环境变量 | 通过 `export` 或 Docker 传入 |
| 高 | 设置页「模型供应商」 | UI 多供应商管理，覆盖后端 `.env` |
| 中 | 服务本地 `.env` | 各服务目录下的 `.env`，覆盖根目录值 |
| 低 | 根目录 `.env` | 统一基础配置 |
| 最低 | 代码默认值 | 无配置时的兜底 |

推荐：**日常以根目录 `.env` 为准**；需要多供应商切换时使用 UI 页面配置。

### 4.4 服务级覆盖（可选）

如果某个服务需要使用不同的 API Key 或模型，可以在该服务目录下创建本地 `.env`，仅写入需要覆盖的变量：

```bash
# mock_targets/shopbot/.env（仅覆盖 ShopBot 的模型和 Key）
TARGET_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-另一个key
OPENAI_BASE_URL=https://api.openai.com/v1
```

未在本地 `.env` 中出现的变量仍读取根目录的值。

---

## 5. 模型供应商配置

### 5.1 通过 UI 配置（推荐）

1. 打开 **设置**。  
2. 在 **模型供应商** 中 **新建供应商**。  
3. 选择类型并填写 API Key。  
4. 使用 **刷新模型列表** 拉取远端模型。  
5. 分别指定 **裁判** 与 **生成** 所用模型，并可设为默认。  

### 5.2 供应商类型参考

| 类型 | 默认 Base URL（示例） | 备注 |
|------|----------------------|------|
| OpenAI | https://api.openai.com/v1 | 官方兼容接口 |
| DeepSeek | https://api.deepseek.com | 国产兼容常见选型 |
| Qwen | 阿里云兼容模式 Base URL | 以控制台文档为准 |
| GLM | 智谱 OpenAPI Base URL | 同上 |
| MiniMax / Gemini / Claude / 自定义 | 见界面说明 | Claude 走 Anthropic 协议时需对应 Key |

### 5.3 角色分工

| 角色 | 职责 | 选型建议 |
|------|------|----------|
| 裁判（Judge） | 判定攻击是否成功、生成分析标签 | 强推理或高对齐模型 |
| 生成（Generation） | 变体生成、PAIR/TAP 等辅助 | 性价比与延迟可接受即可 |

---

## 6. 验证部署

### 6.1 健康检查

```bash
curl http://localhost:8000/health
# 期望: {"status":"ok"}（以实际响应为准）
```

### 6.2 文档与界面

- 浏览器打开 http://localhost:8000/docs  
- 打开 http://localhost:5173 进入仪表盘  

### 6.3 端到端冒烟

1. **设置** → 添加供应商并 **测试** 连通。  
2. **新建扫描** → 内置靶场低等级 → 启动任务。  
3. 待完成后查看 **结果** 与 **报告**。  

---

## 7. 常见部署问题

**Docker 构建失败（WeasyPrint / Cairo）**  
WeasyPrint 依赖系统图形栈。Dockerfile 已处理容器内依赖；裸机部署时需安装 Cairo、Pango 等（Linux 可用发行版包管理器，macOS 可用 Homebrew）。

**前端无法调用后端**  
检查 `CORS_ORIGINS` 是否包含前端 Origin；开发环境核对 `vite.config.ts` 代理。

**扫描报 API 错误**  
确认至少一个供应商可用、Key 有效、Base URL 可达（设置页 **测试**）。

**SQLite database is locked**  
避免多进程同时写同一库；或规划迁移至 PostgreSQL 等并发友好引擎。

**前端构建后样式异常**  
清理 `dist` 与 Vite 缓存后重新 `npm run build`。

---

## 8. 生产环境建议

| 维度 | 建议 |
|------|------|
| 密钥 | 勿提交真实 Key；使用密钥管理或注入 |
| 扫描目标 | 生产可设 `ALLOW_LOCALHOST_TARGETS=false` 降低 SSRF 面 |
| CORS | 收紧为实际前端域名 |
| 传输 | 反向代理（如 Nginx）终止 TLS |
| 性能 | 多 worker 部署 uvicorn；高并发写库考虑 PostgreSQL |
| 备份 | 定期备份 `app.db` 或等价数据源 |

---

## 9. 仓库目录结构

```text
ai-security/
├── .env                  ← 统一配置文件（API Key、模型等）
├── .env.example          ← 配置模板
├── docker-compose.yml
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py    ← 读取根目录 .env + 本地 .env
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   ├── services/
│   │   ├── core/
│   │   └── attack_templates/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── types/
│   │   ├── i18n/
│   │   └── utils/
│   ├── package.json
│   └── Dockerfile
├── mock_targets/
│   ├── shopbot/          ← 读取根目录 .env（TARGET_MODEL）
│   └── financebot/       ← 读取根目录 .env（TARGET_MODEL）
└── docs/
```

---

*— 文档结束 —*
