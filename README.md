# capstone-project-26t2-9900-t17b-bread

## 中文

COMP9900 毕业设计项目：**新闻叙事差异对比工具**（T17B BREAD）。

这是一个基于浏览器的工具：用户输入两篇关于同一话题的新闻文章 URL，系统抓取、清洗并对比文章内容，帮助用户查看不同媒体在叙事框架上的差异。

### 仓库结构

| 路径 | 说明 |
|------|------|
| `backend/` | FastAPI 后端：文章抓取、清洗、预处理、对比 API |
| `backend/API中文.md` | **前端对接文档（中文）** |
| `backend/APIEnglish.md` | **Frontend integration guide (English)** |
| `frontend/` | React + Vite frontend |
| `frontend/README.md` | Frontend setup, local run instructions, backend proxy, and feature notes |
| `database/` | PostgreSQL 初始化脚本和数据库说明 |
| `backend/DATABASE_INTEGRATION.md` | **数据库对接文档**（表结构、连接配置、联调步骤）/ Database integration guide |

### 后端（Sprint 1）

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Swagger 文档: <http://localhost:8000/docs>
- 健康检查: <http://localhost:8000/health>

#### 接口速览

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/fetch` | 抓取并清洗单篇文章 |
| `POST` | `/api/compare` | 处理两篇文章，供双栏展示 |

完整请求/响应格式、错误处理与前端示例见 **[backend/API中文.md](backend/API中文.md)**。

### 前端对接

前端开发请先阅读 `backend/API中文.md`。主接口为 `POST /api/compare`；默认已开启 CORS，允许 `http://localhost:3000` 与 `http://localhost:5173`。
---

## English

COMP9900 capstone project: **Comparison of Diverging Narratives in News Articles** (T17B BREAD).

A browser-based tool that lets users submit two news article URLs about the same topic and explore how different outlets frame the story.

### Repository layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend: article fetch, cleaning, preprocessing, comparison API |
| `backend/APIEnglish.md` | **Frontend integration guide** (endpoints, schemas, examples) |
| `frontend/` | React + Vite frontend: URL/file inputs, comparison form, highlighted article viewer |
| `frontend/README.md` | Frontend setup, local run instructions, backend proxy, and feature notes |
| `database/` | PostgreSQL initialization script and database notes |
| `backend/DATABASE_INTEGRATION.md` | **Database integration guide** (schema, connection, verification) |

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Swagger docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

#### API overview

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/api/fetch` | Fetch and clean a single article |
| `POST` | `/api/compare/stream` | Compare two URL articles with live progress |
| `POST` | `/api/compare/files/stream` | Compare URL and/or PDF/Word article inputs with live progress |

For full request/response formats, error handling, and frontend examples, see **[backend/APIenglish.md](backend/APIenglish.md)**.

### Frontend

The frontend is a React + Vite app for comparing two news reports from URLs or uploaded PDF/Word documents, then rendering matched evidence, highlights, explanations, and filters.

#### Requirements

- Node.js LTS
- npm
- A running FastAPI backend for live article fetching
- Modern browser such as Chrome, Edge, Firefox, or Safari

Check Node and npm are available:

```powershell
node --version
npm --version
```

Install frontend dependencies once before running the app:

```powershell
cd frontend
npm install
```

#### Run locally

From the `frontend` directory:

```powershell
npm run dev
```

Open the local Vite URL shown in the terminal, usually:

```text
http://localhost:5173
```

#### Backend connection

The frontend calls the backend with relative API paths:

```text
/api/compare/stream
/api/compare/files/stream
```

During local development, Vite proxies `/api` requests to the FastAPI backend:

```text
http://localhost:8000
```

Start the backend from the project `backend` directory:

```powershell
uvicorn app.main:app --reload
```

CORS is enabled for `http://localhost:3000` and `http://localhost:5173` by default. Frontend developers should read **[backend/API.md](backend/API.md)** before wiring URL submission and the side-by-side viewer.

#### Current features

- Two article inputs with URL or PDF/Word upload mode
- URL format validation
- PDF/Word file validation
- Comparison focus selector
- Live backend API integration through streaming compare endpoints
- Progress bar for long-running article processing
- Side-by-side cleaned article display on desktop
- Mobile Article A / Article B tab view on narrow screens
- Per-article backend error display
- User-friendly error messages for invalid links, blocked sites, paywalls, login-required pages, and upload problems
- Colour-coded comparison highlights for aligned, partially aligned, and divergent matches
- Highlight legend and relationship filters
- Click-to-inspect explanation panel for matched evidence
- Prepared Al Jazeera / ABC demo URLs
- Offline demo copy fallback when the demo URLs are used and the backend is unavailable

#### Not implemented yet

- Backend-generated semantic sentence alignment
- Backend-generated comparison explanations
- Summary generation
- Database-backed comparison history

Frontend developers should read `backend/APIEnglish.md` before changing API integration. URL-only comparisons use `POST /api/compare/stream`; mixed URL/file comparisons use `POST /api/compare/files/stream`. CORS is enabled for `http://localhost:3000` and `http://localhost:5173` by default.
