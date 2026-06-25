# capstone-project-26t2-9900-t17b-bread

## 中文

COMP9900 毕业设计项目 — **新闻叙事差异对比工具**（T17B BREAD）。

一个基于浏览器的工具：用户输入两篇关于同一话题的新闻文章 URL，系统对比并可视化不同媒体在叙事框架上的差异。

### 仓库结构

| 路径 | 说明 |
|------|------|
| `backend/` | FastAPI 后端 — 文章抓取、清洗、预处理、对比 API |
| `backend/API中文.md` | **前端对接文档（中文）** |
| `backend/APIenglish.md` | **Frontend integration guide (English)** |
| `backend/DATABASE_INTEGRATION.md` | **数据库对接文档**（表结构、连接配置、联调步骤）/ Database integration guide |

### 后端（Sprint 1）

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API：<http://localhost:8000>
- Swagger 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

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

COMP9900 capstone project — **Comparison of Diverging Narratives in News Articles** (T17B BREAD).

A browser-based tool that lets users submit two news article URLs about the same topic and explore how different outlets frame the story.

### Repository layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend — article fetch, cleaning, preprocessing, comparison API |
| `backend/APIenglish.md` | **Frontend integration guide** (endpoints, schemas, examples) |
| `backend/DATABASE_INTEGRATION.md` | **Database integration guide** (schema, connection, verification) |

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

For full request/response formats, error handling, and frontend examples, see **[backend/APIenglish.md](backend/APIenglish.md)**.

### Frontend integration

Frontend developers should read `backend/APIenglish.md` before wiring URL submission and the side-by-side viewer. The main endpoint is `POST /api/compare`; CORS is enabled for `http://localhost:3000` and `http://localhost:5173` by default.
