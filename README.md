# capstone-project-26t2-9900-t17b-bread

## 中文

COMP9900 毕业设计项目：**新闻叙事差异对比工具**（T17B BREAD）。

这是一个基于浏览器的工具：用户输入两篇关于同一话题的新闻文章 URL，系统抓取、清洗并对比文章内容，帮助用户查看不同媒体在叙事框架上的差异。

### 仓库结构

| 路径 | 说明 |
|------|------|
| `backend/` | FastAPI 后端：文章抓取、清洗、预处理、对比 API |
| `backend/API.md` | 前端对接文档：接口、请求/响应结构、示例 |
| `frontend/` | React + Vite frontend |
| `frontend/README.md` | Frontend setup, local run instructions, backend proxy, and feature notes |
| `database/` | PostgreSQL 初始化脚本和数据库说明 |

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

完整请求/响应格式、错误处理与前端示例见 **[backend/API.md](backend/API.md)**。

---

## English

COMP9900 capstone project: **Comparison of Diverging Narratives in News Articles** (T17B BREAD).

A browser-based tool that lets users submit two news article URLs about the same topic and explore how different outlets frame the story.

### Repository layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend: article fetch, cleaning, preprocessing, comparison API |
| `backend/API.md` | Frontend integration guide: endpoints, schemas, examples |
| `frontend/` | React + Vite frontend: URL inputs, comparison form, side-by-side article viewer |
| `frontend/README.md` | Frontend setup, local run instructions, backend proxy, and feature notes |
| `database/` | PostgreSQL initialization script and database notes |

### Backend (Sprint 1)

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
| `POST` | `/api/compare` | Process two articles for side-by-side display |

For full request/response formats, error handling, and frontend examples, see **[backend/API.md](backend/API.md)**.

### Frontend

The frontend is a React + Vite app for submitting two article URLs and rendering cleaned backend output side by side.

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

The frontend calls the backend with a relative API path:

```text
/api/compare
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

- Two article URL inputs
- URL format validation
- Comparison focus selector
- Live backend API integration
- Side-by-side cleaned article display
- Per-article backend error display
- Loading state while comparing
- Prepared Al Jazeera / ABC demo URLs
- Offline demo copy fallback when the demo URLs are used and the backend is unavailable

#### Not implemented yet

- Semantic sentence alignment
- Colour-coded similarity/difference highlighting
- Explanation panel
- Summary generation
- Database-backed comparison history
