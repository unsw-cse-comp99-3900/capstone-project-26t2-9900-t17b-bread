# 后端数据库对接指南

本文档面向团队中的 **数据库开发人员**。说明如何将 PostgreSQL 实例接入 FastAPI 后端、后端期望的表结构、何时写入数据，以及如何验证对接是否成功。

后端开发人员 **无需** 在本地安装数据库即可运行 API。持久化是可选的，由单个环境变量控制。

---

## 1. 职责划分

| 角色 | 负责内容 |
|------|----------|
| **数据库开发人员** | PostgreSQL 实例、`database/database/init_db.sql`、账号/权限、表结构变更 |
| **后端开发人员** | `backend/` 代码、`backend/.env` 连接配置、`app/db/` 中的读写逻辑 |

### 原则

1. **表结构唯一来源：** `database/database/init_db.sql`
2. 后端 **不会** 自动建表或执行迁移，由数据库团队运行初始化脚本。
3. 若 `DATABASE_URL` 为空，API 可正常运行，但 **不会持久化** 任何数据。

---

## 2. 后端如何连接数据库

后端从 `backend/.env` 读取 **`DATABASE_URL`**（该文件已加入 gitignore）。

### 连接字符串格式

```text
postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
```

示例：

```text
postgresql+psycopg://postgres:your_password@localhost:5432/postgres
```

普通 URL 也可使用（后端会自动添加异步驱动）：

```text
postgresql://postgres:your_password@localhost:5432/postgres
```

### 配置步骤（数据库开发人员本机）

```powershell
cd backend
copy .env.example .env
# 编辑 .env，填入 PostgreSQL 凭据的 DATABASE_URL

pip install -r requirements.txt
uvicorn app.main:app --reload
```

**重要：** 修改 `.env` 后请 **重启 uvicorn**。配置在启动时加载并缓存。

后端按绝对路径加载 `backend/.env`，因此无论从仓库根目录还是 `backend/` 启动 uvicorn 均可。

---

## 3. 所需表结构（Sprint 1）

后端当前读写 **两张表**，定义见 `database/database/init_db.sql`：

| 表名 | 用途 |
|------|------|
| `articles` | 清洗后的文章标题、域名与正文 |
| `user_sessions` | 每次成功的对比请求对应一行 |

### 3.1 `articles`

| 列名 | 类型 | 约束 | 写入来源 |
|------|------|------|----------|
| `id` | SERIAL | PRIMARY KEY | 自动生成 |
| `url` | TEXT | UNIQUE NOT NULL | `ProcessedArticle.url` |
| `title` | TEXT | 可空 | `ProcessedArticle.title` |
| `source_domain` | VARCHAR(255) | 可空 | `ProcessedArticle.source_domain` |
| `main_body` | TEXT | NOT NULL | 段落以 `\n\n` 拼接 |
| `created_at` | TIMESTAMP | DEFAULT now | 服务端默认 |

**字段映射说明：** API 响应使用 `body_text` / `paragraphs`，数据库列名为 **`main_body`**。

**Upsert 行为：** 若同一 `url` 再次对比，会更新该行（标题、域名、正文）。

### 3.2 `user_sessions`

| 列名 | 类型 | 约束 | 写入来源 |
|------|------|------|----------|
| `id` | SERIAL | PRIMARY KEY | 自动生成 |
| `session_token` | VARCHAR(255) | NOT NULL | 后端生成的 UUID hex |
| `article_a_url` | TEXT | NOT NULL | 请求中的 `article_a_url` |
| `article_b_url` | TEXT | NOT NULL | 请求中的 `article_b_url` |
| `created_at` | TIMESTAMP | DEFAULT now | 服务端默认 |

---

## 4. 何时写入数据

| 接口 | 是否写库 | 说明 |
|------|----------|------|
| `POST /api/fetch` | 否 | 仅预览 |
| `POST /api/compare` | 是 | 至少有一篇文章处理成功时 |
| `GET /health` | 否 | 仅应用健康检查 |
| `GET /health/db` | 否（仅探测） | 执行 `SELECT 1` |

### `POST /api/compare` 写入流程

1. 后端抓取并处理两篇文章（此阶段不涉及数据库）。
2. 若已配置 `DATABASE_URL` 且至少一篇文章处理成功：
   - 将每篇成功的文章 **UPSERT** 到 `articles`（以 `url` 为键）。
   - 向 `user_sessions` **INSERT** 一行。
   - **COMMIT** 事务。
   - 在 JSON 响应中返回 `session_token`。
3. 若数据库不可达或写入失败：错误 **仅记录日志**。API 仍返回 `200` 及处理后的文章（尽力持久化）。

响应片段示例：

```json
{
  "focus": "general",
  "articles": ["..."],
  "errors": [],
  "comparison": null,
  "session_token": "a1b2c3d4e5f6789..."
}
```

当持久化未启用或写入失败时，`session_token` 为 `null`。

---

## 5. 后端代码对照

通常 **无需修改** 以下文件。若表结构变更，请保持 `init_db.sql` 与 `app/db/models.py` 一致。

| 路径 | 作用 |
|------|------|
| `app/config.py` | 从 `backend/.env` 加载 `DATABASE_URL` |
| `app/db/base.py` | 异步引擎、会话工厂、健康探测 |
| `app/db/models.py` | SQLAlchemy ORM 模型（须与 SQL 表结构一致） |
| `app/db/repositories.py` | `ArticleRepository`、`UserSessionRepository` |
| `app/api/routes/compare.py` | 处理成功后调用持久化逻辑 |
| `scripts/check_db.py` | 连接测试 + 可选运行初始化脚本 |

**驱动：** SQLAlchemy 2 异步 + **`psycopg`**（见 `requirements.txt`）。旧版 `postgresql+asyncpg://` URL 会自动转换。

---

## 6. 验证清单

### 步骤 1 — 创建表

在 pgAdmin 或 psql 中运行初始化脚本（`database/database/init_db.sql` 的内容）。

或在 **`backend/`** 目录下执行：

```powershell
cd backend
python scripts\check_db.py --init
```

预期输出：

```text
CONNECTION_OK
tables: ['articles', 'user_sessions']
articles rows: 0
user_sessions rows: 0
```

表为空是正常的。只有调用 `POST /api/compare` 后才会出现数据行。

### 步骤 2 — 检查后端连通性

启动 uvicorn 后访问：

<http://localhost:8000/health/db>

| 响应 | 含义 |
|------|------|
| `{"database":"ok"}` | 已连接 |
| `{"database":"error"}` | 凭据错误、PostgreSQL 未运行或缺少表 |
| `{"database":"disabled"}` | `.env` 中 `DATABASE_URL` 为空 |

### 步骤 3 — 写入测试

1. 打开 <http://localhost:8000/docs>
2. 调用 `POST /api/compare`，传入两篇可访问的新闻文章 URL
3. 在数据库中查询：

```sql
SELECT id, url, title, source_domain, LEFT(main_body, 80) AS preview
FROM articles
ORDER BY id DESC
LIMIT 5;

SELECT id, session_token, article_a_url, article_b_url, created_at
FROM user_sessions
ORDER BY id DESC
LIMIT 5;
```

---

## 7. 常见问题

**为什么配置完成后表仍是空的？**  
只有 `POST /api/compare` 会写入数据，`POST /api/fetch` 不会。

**可以修改表结构吗？**  
可以。需同步更新：

1. `database/database/init_db.sql`
2. `backend/app/db/models.py`
3. `backend/app/db/repositories.py`（若写入逻辑有变）

然后重新执行对接验证。

**Sprint 2 的表（`embeddings`、`comparison_results`）呢？**  
架构图中已规划，但 **当前 init 脚本尚未包含**，将在后续 Sprint 添加。

**后端日志出现 "Database health check failed"？**  
请检查 `backend/.env` 中的用户名、密码、主机、端口和数据库名。修改后需重启 uvicorn。

---

## 8. 相关文档

| 文档 | 读者 |
|------|------|
| [API中文.md](API中文.md) / [APIenglish.md](APIenglish.md) | 前端 — HTTP 接口 |
| [database/database/README.md](../database/database/README.md) | 数据库 — 初始化脚本说明 |
| 本文档 / [DATABASE_INTEGRATION.md](DATABASE_INTEGRATION.md) | 数据库 ↔ 后端对接 |

---

## 9. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-25 | Sprint 1 对接指南初版（articles + user_sessions） |
