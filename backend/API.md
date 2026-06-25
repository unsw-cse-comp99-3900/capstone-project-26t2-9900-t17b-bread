# Backend API 对接文档 / Frontend Integration Guide

本文档说明 **T17B BREAD** 后端当前对外暴露的 HTTP 接口，供前端（React）对接使用。  
This document describes the HTTP endpoints exposed by the **T17B BREAD** backend for frontend (React) integration.

- **当前版本 / Version**：Sprint 1
- **已实现 / Implemented**：文章抓取、清洗、分句、双栏展示所需的数据 / Article fetch, cleaning, sentence segmentation, data for side-by-side display
- **尚未实现 / Not yet implemented**：语义对比、高亮、解释（`comparison` 字段预留，Sprint 2 填充）/ Semantic comparison, highlighting, explanations (`comparison` reserved for Sprint 2)

---

## 1. 基本信息 / Basic Information

| 项目 / Item | 值 / Value |
|-------------|------------|
| 本地 Base URL / Local Base URL | `http://localhost:8000` |
| 交互式文档 / Interactive docs | `http://localhost:8000/docs` |
| Content-Type | `application/json` |
| 已启用 CORS / CORS enabled | 默认允许 / Default: `http://localhost:3000`, `http://localhost:5173` |

**启动后端 / Start the backend：**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

---

## 2. 接口总览 / Endpoint Overview

| 方法 / Method | 路径 / Path | 用途 / Purpose | Sprint |
|---------------|-------------|----------------|--------|
| `GET` | `/health` | 健康检查 / Health check | 1 |
| `POST` | `/api/fetch` | 抓取并清洗单篇文章（预览）/ Fetch and clean a single article (preview) | 1 |
| `POST` | `/api/compare` | 处理两篇文章，返回对比就绪结构 / Process two articles; comparison-ready structure | 1（对比结果 / comparison in Sprint 2） |

---

## 3. `GET /health`

检查后端是否在线。/ Check whether the backend is running.

### 响应 / Response `200`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 4. `POST /api/fetch`

抓取一篇新闻文章，返回清洗后的标题、来源域名和正文。适合「单篇预览」；完整对比请用 `/api/compare`。  
Fetches one news article and returns cleaned title, source domain, and body. Use for single-article preview; use `/api/compare` for full comparison.

### 请求体 / Request body

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx"
}
```

| 字段 / Field | 类型 / Type | 必填 / Required | 说明 / Description |
|--------------|-------------|-----------------|---------------------|
| `url` | string | 是 / Yes | 必须以 `http://` 或 `https://` 开头 / Must start with `http://` or `https://` |

### 成功响应 / Success `200`

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx",
  "title": "Budget passed by parliament",
  "source_domain": "www.bbc.com",
  "body_text": "The government announced a sweeping new national budget..."
}
```

| 字段 / Field | 类型 / Type | 说明 / Description |
|--------------|-------------|---------------------|
| `url` | string | 实际请求的 URL / Requested URL |
| `title` | string \| null | 文章标题 / Article title |
| `source_domain` | string \| null | 来源域名 / Source domain |
| `body_text` | string | 清洗后的正文（已去除导航、广告、页脚等）/ Cleaned body (nav, ads, footers removed) |

### 失败响应 / Error `422`

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

### `stage` 错误阶段说明 / Error stages

| `stage` | 含义 / Meaning | 前端建议提示 / Suggested UI message |
|---------|----------------|-------------------------------------|
| `validation` | URL 格式不合法 / Invalid URL format | 请输入有效的 http/https 链接 / Please enter a valid http/https URL |
| `fetch` | 网络请求失败（超时、403、404 等）/ Network failure (timeout, 403, 404, etc.) | 无法访问该文章，请换一篇试试 / Could not reach this article; try another URL |
| `extraction` | 页面能打开但提取不出正文 / Page loaded but no article body extracted | 该页面无法识别为新闻正文 / This page does not look like a news article |

---

## 5. `POST /api/compare`（主接口 / Main endpoint）

前端「提交对比」按钮应调用此接口。后端并发处理 Article A 和 Article B，返回结构化段落与句子，供左右双栏展示。  
The frontend “Compare” action should call this endpoint. Both articles are processed concurrently; structured paragraphs and sentences are returned for side-by-side display.

### 请求体 / Request body

```json
{
  "article_a_url": "https://outlet-a.com/story",
  "article_b_url": "https://outlet-b.com/story",
  "focus": "general"
}
```

| 字段 / Field | 类型 / Type | 必填 / Required | 说明 / Description |
|--------------|-------------|-----------------|---------------------|
| `article_a_url` | string | 是 / Yes | 文章 A 的 URL / URL for article A |
| `article_b_url` | string | 是 / Yes | 文章 B 的 URL / URL for article B |
| `focus` | string | 否 / No | 对比焦点，默认 `"general"` / Comparison focus; default `"general"` |

### `focus` 可选值 / Allowed values

| 值 / Value | 含义 / Meaning |
|------------|----------------|
| `general` | 通用对比（默认）/ General comparison (default) |
| `political` | 政治框架 / Political framing |
| `sentiment` | 情感倾向 / Sentiment |
| `economic` | 经济视角 / Economic emphasis |
| `social` | 社会视角 / Social implications |

> Sprint 1 仅记录 `focus` 并原样返回；Sprint 2 起该字段会影响对比权重。  
> Sprint 1 only echoes `focus`; from Sprint 2 it will affect comparison weighting.

### 成功响应 / Success `200`（两篇都成功 / both articles OK）

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
        }
      ]
    },
    {
      "article_ref": "B",
      "url": "https://outlet-b.com/story",
      "title": "...",
      "source_domain": "outlet-b.com",
      "paragraphs": ["..."],
      "sentences": []
    }
  ],
  "errors": [],
  "comparison": null
}
```

### 部分失败响应 / Partial success `200`（一篇失败、一篇成功 / one failed, one OK）

`/api/compare` **不会因单篇失败而返回 4xx**。失败信息在 `errors` 中，成功的文章仍在 `articles` 里。  
`/api/compare` does **not** return 4xx when only one article fails. Failures appear in `errors`; successful articles remain in `articles`.

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

### 响应字段说明 / Response fields

#### 顶层 / Top level

| 字段 / Field | 类型 / Type | 说明 / Description |
|--------------|-------------|---------------------|
| `focus` | string | 本次请求的对比焦点 / Requested comparison focus |
| `articles` | array | 成功处理的文章（0–2 篇）/ Successfully processed articles (0–2) |
| `errors` | array | 失败文章的错误（0–2 条）/ Per-article errors (0–2) |
| `comparison` | object \| null | **Sprint 2** 对比结果；当前恒为 `null` / Comparison results; currently always `null` |

#### `articles[]` 每篇文章 / Each article

| 字段 / Field | 类型 / Type | 说明 / Description |
|--------------|-------------|---------------------|
| `article_ref` | string | `"A"` 或 `"B"`，区分左右栏 / `"A"` or `"B"` for left/right column |
| `url` | string | 文章 URL / Article URL |
| `title` | string \| null | 标题 / Title |
| `source_domain` | string \| null | 来源域名 / Source domain |
| `paragraphs` | string[] | 按段落切分的正文 / Body split into paragraphs |
| `sentences` | object[] | 句子级结构 / Sentence-level structure (see below) |

#### `sentences[]` 每个句子 / Each sentence

| 字段 / Field | 类型 / Type | 说明 / Description |
|--------------|-------------|---------------------|
| `id` | string | 稳定 ID（如 `"A-0"`）；Sprint 2 高亮锚点 / Stable id; highlight anchor in Sprint 2 |
| `article_ref` | string | `"A"` 或 `"B"` / `"A"` or `"B"` |
| `text` | string | 句子文本 / Sentence text |
| `paragraph_index` | number | 段落索引（从 0 开始）/ Paragraph index (0-based) |
| `sentence_index` | number | 全文句子序号（从 0 开始）/ Global sentence index (0-based) |
| `char_start` | number | 在清洗后正文中的起始偏移 / Start offset in cleaned body |
| `char_end` | number | 在清洗后正文中的结束偏移 / End offset in cleaned body |

#### `errors[]` 每条错误 / Each error

| 字段 / Field | 类型 / Type | 说明 / Description |
|--------------|-------------|---------------------|
| `stage` | string | `validation` / `fetch` / `extraction` |
| `message` | string | 可读错误信息 / Human-readable message |
| `article_ref` | string \| null | 失败文章 `"A"` 或 `"B"` / Failed article ref |
| `url` | string \| null | 出错的 URL / URL that failed |

---

## 6. 前端组件对接映射 / Frontend component mapping

| 前端组件 / Frontend component | 使用的接口 / 字段 / API / fields |
|-----------------------------|----------------------------------|
| URL Input Component | `POST /api/compare` → `article_a_url`, `article_b_url` |
| Comparison Focus Selector | `focus`（Sprint 2 起影响对比结果 / affects results from Sprint 2） |
| Article Viewer (Side-by-Side) | `articles` 中 `article_ref === "A"` / `"B"`；正文用 `paragraphs` 或 `sentences` |
| Colour-Coded Difference Renderer | Sprint 2：`comparison` + `sentences[].id` 高亮 |
| Similarity Rationale Panel | Sprint 2：`comparison` 中的解释文本 / explanations in `comparison` |

### Sprint 1 推荐渲染逻辑 / Recommended render flow (Sprint 1)

```text
1. 用户提交两个 URL / User submits two URLs
2. POST /api/compare
3. 若 errors.length > 0 → 按 article_ref 显示错误，不阻断另一篇 / Show errors by article_ref; still render the other article
4. article_ref === "A" → 左栏 / left column
5. article_ref === "B" → 右栏 / right column
6. comparison === null → 暂不渲染高亮/解释 / No highlights or explanations yet (Sprint 2)
```

---

## 7. 前端调用示例 / Frontend examples

### 7.1 使用 `fetch` / Using `fetch`

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

const data = await compareArticles(urlA, urlB, "political");
const articleA = data.articles.find((a) => a.article_ref === "A");
const articleB = data.articles.find((a) => a.article_ref === "B");

if (data.errors.length > 0) {
  data.errors.forEach((err) => {
    console.warn(`Article ${err.article_ref} failed at ${err.stage}:`, err.message);
  });
}
```

### 7.2 使用 axios / Using axios

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

### 7.3 单篇预览 / Single-article preview

```javascript
const { data } = await api.post("/api/fetch", {
  url: "https://www.bbc.com/news/articles/xxxx",
});
// data.title, data.source_domain, data.body_text
```

---

## 8. 前端校验建议 / Client-side validation

在调用后端前，前端可先校验 URL，减少无效请求（与后端 PROJ-1 一致）。  
Validate URLs before calling the backend (aligned with backend PROJ-1).

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

- 两个 URL 都合法后再启用「对比」按钮（PROJ-1 AC 1.2）/ Enable Compare only when both URLs are valid
- 非法 URL 可在前端直接提示 / Show inline validation errors without waiting for the API

---

## 9. Sprint 2 预留：`comparison` 字段（草案）/ Sprint 2: `comparison` (draft)

当前 `comparison` 为 `null`。Sprint 2 语义对比完成后，预计结构类似：  
`comparison` is currently `null`. Expected shape after Sprint 2:

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

| `label` 值 / Value | 含义 / Meaning | 建议颜色 / Suggested colour |
|--------------------|----------------|----------------------------|
| `aligned` | 语义一致 / Semantically aligned | 绿色 / Green |
| `partially_aligned` | 部分一致 / Partially aligned | 黄色 / Yellow |
| `divergent` | 明显分歧 / Divergent | 红色 / Red |

> 以上为预期结构草案，Sprint 2 定稿后更新。前端可先用 `comparison === null` 做兼容。  
> Draft only; will be updated when Sprint 2 is finalised. Guard with `comparison === null` for now.

---

## 10. 常见问题 / FAQ

**Q: 为什么 `/api/compare` 返回 200 但 `errors` 不为空？**  
**Q: Why does `/api/compare` return 200 when `errors` is non-empty?**

A: 设计为「部分成功」——一篇失败不影响另一篇展示；前端应同时处理 `articles` 和 `errors`。  
A: Partial success by design — one failed article does not block the other; handle both `articles` and `errors`.

**Q: 为什么有些新闻站返回 `stage: "fetch"`？**  
**Q: Why do some sites return `stage: "fetch"`?**

A: 部分网站有反爬（403）或需要登录，属正常现象。  
A: Some publishers block bots (403) or require login; this is expected.

**Q: 前端端口不是 3000/5173 怎么办？**  
**Q: What if the frontend runs on a different port?**

A: 在 `backend/.env` 设置：`CORS_ORIGINS=http://localhost:你的端口`  
A: Set in `backend/.env`: `CORS_ORIGINS=http://localhost:YOUR_PORT`

**Q: 如何判断后端是否启动？**  
**Q: How do I check if the backend is up?**

A: 请求 `GET /health`，或打开 `http://localhost:8000/docs`。  
A: Call `GET /health` or open `http://localhost:8000/docs`.

---

## 11. 变更记录 / Changelog

| 日期 / Date | 版本 / Version | 说明 / Notes |
|-------------|----------------|--------------|
| 2026-06-23 | Sprint 1 | 初版：fetch / compare / health；`comparison` 预留 / Initial: fetch, compare, health; `comparison` reserved |
| 2026-06-23 | Sprint 1 | 中英双语版 / Bilingual (ZH/EN) edition |
