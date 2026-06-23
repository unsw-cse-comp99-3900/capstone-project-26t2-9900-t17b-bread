# Backend API 对接文档（前端）

本文档说明 **T17B BREAD** 后端当前对外暴露的 HTTP 接口，供前端（React）对接使用。

- **当前版本**：Sprint 1
- **已实现**：文章抓取、清洗、分句、双栏展示所需的数据
- **尚未实现**：语义对比、高亮、解释（`comparison` 字段预留，Sprint 2 填充）

---

## 1. 基本信息

| 项目 | 值 |
|------|-----|
| 本地 Base URL | `http://localhost:8000` |
| 交互式文档 | `http://localhost:8000/docs` |
| Content-Type | `application/json` |
| 已启用 CORS | 默认允许 `http://localhost:3000`、`http://localhost:5173` |

启动后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

---

## 2. 接口总览

| 方法 | 路径 | 用途 | Sprint |
|------|------|------|--------|
| `GET` | `/health` | 健康检查 | 1 |
| `POST` | `/api/fetch` | 抓取并清洗单篇文章（预览） | 1 |
| `POST` | `/api/compare` | 处理两篇文章，返回对比就绪结构 | 1（对比结果 Sprint 2） |

---

## 3. `GET /health`

检查后端是否在线。

### 响应 `200`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 4. `POST /api/fetch`

抓取一篇新闻文章，返回清洗后的标题、来源域名和正文。适合「单篇预览」场景；完整对比流程请用 `/api/compare`。

### 请求体

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 必须以 `http://` 或 `https://` 开头 |

### 成功响应 `200`

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx",
  "title": "Budget passed by parliament",
  "source_domain": "www.bbc.com",
  "body_text": "The government announced a sweeping new national budget..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | string | 实际请求的 URL |
| `title` | string \| null | 文章标题 |
| `source_domain` | string \| null | 来源域名 |
| `body_text` | string | 清洗后的正文（已去除导航、广告、页脚等噪声） |

### 失败响应 `422`

```json
{
  "detail": {
    "stage": "fetch",
    "message": "Server returned HTTP 403 for the article.",
    "article_ref": null,
    "url": "https://example.com/story"
  }
}
```

### `stage` 错误阶段说明

| `stage` | 含义 | 前端建议提示 |
|---------|------|--------------|
| `validation` | URL 格式不合法 | 「请输入有效的 http/https 链接」 |
| `fetch` | 网络请求失败（超时、403、404 等） | 「无法访问该文章，请换一篇试试」 |
| `extraction` | 页面能打开但提取不出正文 | 「该页面无法识别为新闻正文」 |

---

## 5. `POST /api/compare`（主接口）

前端「提交对比」按钮应调用此接口。后端会并发处理 Article A 和 Article B，返回结构化段落与句子，供左右双栏展示。

### 请求体

```json
{
  "article_a_url": "https://outlet-a.com/story",
  "article_b_url": "https://outlet-b.com/story",
  "focus": "general"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `article_a_url` | string | 是 | 文章 A 的 URL |
| `article_b_url` | string | 是 | 文章 B 的 URL |
| `focus` | string | 否 | 对比焦点，默认 `"general"` |

### `focus` 可选值

| 值 | 含义 |
|----|------|
| `general` | 通用对比（默认） |
| `political` | 政治框架 |
| `sentiment` | 情感倾向 |
| `economic` | 经济视角 |
| `social` | 社会视角 |

> Sprint 1 仅记录 `focus` 并原样返回；Sprint 2 起该字段会影响对比权重。

### 成功响应 `200`（两篇都成功）

```json
{
  "focus": "general",
  "articles": [
    {
      "article_ref": "A",
      "url": "https://outlet-a.com/story",
      "title": "Budget passed",
      "source_domain": "outlet-a.com",
      "paragraphs": [
        "The government announced a new budget today. Critics said it favours the wealthy.",
        "Officials defended the plan."
      ],
      "sentences": [
        {
          "id": "A-0",
          "article_ref": "A",
          "text": "The government announced a new budget today.",
          "paragraph_index": 0,
          "sentence_index": 0,
          "char_start": 0,
          "char_end": 44
        },
        {
          "id": "A-1",
          "article_ref": "A",
          "text": "Critics said it favours the wealthy.",
          "paragraph_index": 0,
          "sentence_index": 1,
          "char_start": 45,
          "char_end": 81
        }
      ]
    },
    {
      "article_ref": "B",
      "url": "https://outlet-b.com/story",
      "title": "...",
      "source_domain": "outlet-b.com",
      "paragraphs": ["..."],
      "sentences": [
        {
          "id": "B-0",
          "article_ref": "B",
          "text": "...",
          "paragraph_index": 0,
          "sentence_index": 0,
          "char_start": 0,
          "char_end": 30
        }
      ]
    }
  ],
  "errors": [],
  "comparison": null
}
```

### 部分失败响应 `200`（一篇失败、一篇成功）

`/api/compare` **不会因单篇失败而返回 4xx**。失败信息在 `errors` 数组中，成功的文章仍在 `articles` 里。

```json
{
  "focus": "general",
  "articles": [
    {
      "article_ref": "B",
      "url": "https://outlet-b.com/story",
      "title": "...",
      "source_domain": "outlet-b.com",
      "paragraphs": ["..."],
      "sentences": []
    }
  ],
  "errors": [
    {
      "stage": "validation",
      "message": "URL must start with http:// or https://.",
      "article_ref": "A",
      "url": "not-a-valid-url"
    }
  ],
  "comparison": null
}
```

### 响应字段说明

#### 顶层

| 字段 | 类型 | 说明 |
|------|------|------|
| `focus` | string | 本次请求的对比焦点 |
| `articles` | array | 成功处理的文章列表（0–2 篇） |
| `errors` | array | 失败文章的错误列表（0–2 条） |
| `comparison` | object \| null | **Sprint 2** 对比结果，当前恒为 `null` |

#### `articles[]` 每篇文章

| 字段 | 类型 | 说明 |
|------|------|------|
| `article_ref` | string | `"A"` 或 `"B"`，用于区分左右栏 |
| `url` | string | 文章 URL |
| `title` | string \| null | 标题 |
| `source_domain` | string \| null | 来源域名 |
| `paragraphs` | string[] | 按段落切分后的正文 |
| `sentences` | object[] | 句子级结构（见下表） |

#### `sentences[]` 每个句子

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 稳定 ID，如 `"A-0"`、`"B-3"`，Sprint 2 高亮锚点 |
| `article_ref` | string | `"A"` 或 `"B"` |
| `text` | string | 句子文本 |
| `paragraph_index` | number | 所在段落索引（从 0 开始） |
| `sentence_index` | number | 全文句子序号（从 0 开始） |
| `char_start` | number | 在清洗后正文中的起始字符偏移 |
| `char_end` | number | 在清洗后正文中的结束字符偏移 |

#### `errors[]` 每条错误

| 字段 | 类型 | 说明 |
|------|------|------|
| `stage` | string | 失败阶段：`validation` / `fetch` / `extraction` |
| `message` | string | 可读错误信息 |
| `article_ref` | string \| null | 失败文章：`"A"` 或 `"B"` |
| `url` | string \| null | 出错的 URL |

---

## 6. 前端组件对接映射

| 前端组件（Proposal） | 使用的接口 / 字段 |
|---------------------|-------------------|
| URL Input Component | 调用 `POST /api/compare`，传 `article_a_url`、`article_b_url` |
| Comparison Focus Selector | 传 `focus`；Sprint 2 起影响对比结果 |
| Article Viewer (Side-by-Side) | 用 `articles` 中 `article_ref === "A"` / `"B"` 分别渲染左右栏；正文可用 `paragraphs` 或 `sentences` |
| Colour-Coded Difference Renderer | Sprint 2：根据 `comparison` 中的匹配结果，用 `sentences[].id` 做高亮 |
| Similarity Rationale Panel | Sprint 2：读取 `comparison` 中的解释文本 |

### Sprint 1 推荐渲染逻辑

```text
1. 用户提交两个 URL
2. POST /api/compare
3. 若 errors.length > 0 → 按 article_ref 显示对应错误，不阻断另一篇展示
4. articles 中 article_ref === "A" → 左栏
5. articles 中 article_ref === "B" → 右栏
6. comparison === null → 暂不渲染高亮/解释（Sprint 2 再接）
```

---

## 7. 前端调用示例

### 7.1 使用 `fetch`

```javascript
const API_BASE = "http://localhost:8000";

async function compareArticles(urlA, urlB, focus = "general") {
  const res = await fetch(`${API_BASE}/api/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      article_a_url: urlA,
      article_b_url: urlB,
      focus,
    }),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  return res.json();
}

// 使用
const data = await compareArticles(urlA, urlB, "political");
const articleA = data.articles.find((a) => a.article_ref === "A");
const articleB = data.articles.find((a) => a.article_ref === "B");

if (data.errors.length > 0) {
  data.errors.forEach((err) => {
    console.warn(`Article ${err.article_ref} failed at ${err.stage}:`, err.message);
  });
}
```

### 7.2 使用 axios

```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

const { data } = await api.post("/api/compare", {
  article_a_url: urlA,
  article_b_url: urlB,
  focus: "general",
});
```

### 7.3 单篇预览

```javascript
const { data } = await api.post("/api/fetch", {
  url: "https://www.bbc.com/news/articles/xxxx",
});
// data.title, data.source_domain, data.body_text
```

---

## 8. 前端校验建议（与后端一致）

在调用后端前，前端可先做一次本地校验，减少无效请求：

```javascript
function isValidHttpUrl(value) {
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
```

- 两个 URL 都合法后再启用「对比」按钮（对应 PROJ-1 AC 1.2）
- 非法 URL 可在前端直接提示，不必等后端返回

---

## 9. Sprint 2 预留：`comparison` 字段（草案）

当前 `comparison` 为 `null`。Sprint 2 实现语义对比后，预计结构类似：

```json
{
  "comparison": {
    "matches": [
      {
        "sentence_a_id": "A-0",
        "sentence_b_id": "B-1",
        "label": "aligned",
        "score": 0.87,
        "explanation": "Both sentences describe the same budget announcement."
      }
    ],
    "unique_a": ["A-5"],
    "unique_b": ["B-7"],
    "summary": {
      "similarities": ["..."],
      "differences": ["..."],
      "unique_to_a": ["..."],
      "unique_to_b": ["..."]
    }
  }
}
```

| `label` 值 | 含义 | 建议颜色 |
|------------|------|----------|
| `aligned` | 语义一致 | 绿色 |
| `partially_aligned` | 部分一致 | 黄色 |
| `divergent` | 明显分歧 | 红色 |

> 以上为 **预期结构草案**，Sprint 2 定稿后本文档会更新。前端可先用 `comparison === null` 做兼容判断。

---

## 10. 常见问题

**Q: 为什么 `/api/compare` 返回 200 但 `errors` 不为空？**  
A: 设计为「部分成功」——一篇失败不影响另一篇展示，前端应同时处理 `articles` 和 `errors`。

**Q: 为什么有些新闻站返回 `stage: "fetch"`？**  
A: 部分网站有反爬（403）或需要登录，属正常现象。

**Q: 前端端口不是 3000/5173 怎么办？**  
A: 让后端同学在 `backend/.env` 中设置：  
`CORS_ORIGINS=http://localhost:你的端口`

**Q: 如何判断后端是否启动？**  
A: 请求 `GET /health`，或打开 `http://localhost:8000/docs`。

---

## 11. 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-06-23 | Sprint 1 | 初版：fetch / compare / health；`comparison` 预留 |
