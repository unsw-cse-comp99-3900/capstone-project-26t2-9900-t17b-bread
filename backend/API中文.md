# Backend API 对接文档

本文档说明 **T17B BREAD** 后端当前对外暴露的 HTTP 接口，供前端（React）对接使用。

- **当前版本**：Sprint 1+
- **已实现**：URL 抓取、PDF/Word 上传、清洗、分句、英文进度提示、分场景错误码、双栏展示所需数据
- **尚未实现**：语义对比、高亮、解释（`comparison` 字段预留，Sprint 2 填充）
- **数据库**：可选；配置 `DATABASE_URL` 后，`/api/compare` 会持久化并返回 `session_token`（见 [DATABASE_INTEGRATION中文.md](DATABASE_INTEGRATION中文.md)）

### 1. 基本信息

| 项目 | 值 |
|------|-----|
| 本地 Base URL | `http://localhost:8000` |
| 交互式文档 | `http://localhost:8000/docs` |
| JSON 接口 Content-Type | `application/json` |
| 上传接口 Content-Type | `multipart/form-data` |
| 进度流式接口 | `text/event-stream`（SSE） |
| 已启用 CORS | 默认允许 `http://localhost:3000`、`http://localhost:5173` |

启动后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. 接口总览

| 方法 | 路径 | 用途 | Sprint |
|------|------|------|--------|
| `GET` | `/health` | 应用健康检查 | 1 |
| `GET` | `/health/db` | 数据库连接检查 | 1 |
| `POST` | `/api/fetch` | 抓取并清洗单篇 URL 文章（预览） | 1 |
| `POST` | `/api/fetch/stream` | 同上，带实时英文进度（SSE） | 1 |
| `POST` | `/api/upload` | 上传 PDF/Word 并提取正文（扫描件自动 OCR） | 1 |
| `POST` | `/api/upload/stream` | 同上，带实时英文进度（SSE） | 1 |
| `POST` | `/api/upload/pdf-type` | 判断 PDF 是文字型还是图片（扫描）型 | 1 |
| `POST` | `/api/upload/pdf-to-word` | 图片/扫描 PDF 做 OCR 并下载清洗后的 Word（.docx） | 1 |
| `POST` | `/api/compare` | 对比两篇 URL 文章 | 1 |
| `POST` | `/api/compare/stream` | 同上，带实时英文进度（SSE） | 1 |
| `POST` | `/api/compare/files` | 对比两篇文章（URL 和/或上传文件） | 1 |
| `POST` | `/api/compare/files/stream` | 同上，带实时英文进度（SSE） | 1 |

### 3. `GET /health`

检查后端是否在线。

**响应 `200`：**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### 4. `GET /health/db`

检查数据库是否已配置且可连接（给联调使用）。

**响应 `200`：**

| 返回值 | 含义 |
|--------|------|
| `{"database":"ok"}` | 已连接 |
| `{"database":"error"}` | 已配置但连接失败 |
| `{"database":"disabled"}` | 未配置 `DATABASE_URL` |

### 5. `POST /api/fetch`

抓取一篇新闻文章，返回清洗后的标题、来源域名和正文。适合「单篇 URL 预览」。

**请求体：**

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 必须以 `http://` 或 `https://` 开头 |

**成功响应 `200`：**

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx",
  "title": "Budget passed by parliament",
  "source_domain": "www.bbc.com",
  "body_text": "The government announced a sweeping new national budget...",
  "source_type": "url",
  "processing": {
    "total_elapsed_seconds": 2.14,
    "message": "Processing completed in 2.14 seconds.",
    "steps": [
      {
        "step": "fetch",
        "label": "Download finished for article fetch.",
        "status": "completed",
        "elapsed_seconds": 1.2,
        "article_ref": "fetch"
      }
    ]
  }
}
```

**失败响应 `422`：**

```json
{
  "detail": {
    "stage": "extraction",
    "code": "extraction_paywall",
    "message": "This article appears to be behind a paywall or membership wall. Please upload a PDF/Word copy or use a publicly accessible link.",
    "article_ref": null,
    "url": "https://example.com/story"
  }
}
```

### 6. `POST /api/upload`

上传 PDF（`.pdf`）或 Word（`.docx`）文档，提取正文用于预览或对比。

**请求：** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | `.pdf` 或 `.docx`；最大 10MB |

**成功响应 `200`：**

```json
{
  "article": {
    "url": "upload://budget-report.docx",
    "title": "Budget Report",
    "source_domain": "upload",
    "body_text": "The government announced...",
    "source_type": "upload"
  },
  "processing": {
    "total_elapsed_seconds": 0.85,
    "message": "Processing completed in 0.85 seconds.",
    "steps": []
  }
}
```

**失败响应 `422`：** 结构与 `/api/fetch` 相同，`stage` 可能为 `upload`。

> 文字型 PDF 直接读取正文；图片/扫描型 PDF 会被自动识别并走 OCR（服务器需安装
> Tesseract 引擎）。若 OCR 不可用，错误 `code` 为 `ocr_unavailable`。

### 6a. `POST /api/upload/pdf-type`

判断上传的 PDF 是**文字型**（可选中文本）还是**图片型**（扫描件），供前端选择
不同处理流程。

**请求：** `multipart/form-data`，单个 `file` 字段（必须是 `.pdf`）。

**成功响应 `200`：**

```json
{
  "pdf_type": "image",
  "is_image_based": true,
  "page_count": 3,
  "chars_per_page": 4.0,
  "pages_with_images": 3,
  "ocr_available": true,
  "recommended_endpoint": "/api/upload/pdf-to-word"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `pdf_type` | string | `"text"`（文字型）或 `"image"`（图片型） |
| `is_image_based` | boolean | 为 `true` 时是扫描件，需要 OCR |
| `page_count` | number | 页数 |
| `chars_per_page` | number | 平均每页可直接提取的字符数 |
| `pages_with_images` | number | 含内嵌图片的页数 |
| `ocr_available` | boolean | 当前服务器是否可对图片 PDF 做 OCR |
| `recommended_endpoint` | string | `/api/upload`（文字型）或 `/api/upload/pdf-to-word`（扫描件） |

### 6b. `POST /api/upload/pdf-to-word`

将**图片/扫描 PDF** 转换成清洗后的、可下载的 **Word（.docx）** 文件。流程为：
逐页 OCR → 去除页码、重复页眉页脚、符号噪音 → 只保留关键正文（同样会送入后续
对比流程）。也接受文字型 PDF（直接导出其文本）。

**请求：** `multipart/form-data`，单个 `file` 字段（`.pdf`）。

**成功响应 `200`：** 响应体是 **`.docx` 二进制**（不是 JSON）。

| 响应头 | 说明 |
|--------|------|
| `Content-Type` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `Content-Disposition` | `attachment; filename*=UTF-8''<名称>.docx` |
| `X-Extracted-Chars` | 清洗后提取的字符数 |
| `X-Extracted-Text-Preview` | URL 编码的正文预览（前 ~180 字） |

**失败响应 `422`：** JSON `{ "detail": { stage, code, message, ... } }`。常见 `code`：
`ocr_unavailable`、`ocr_failed`、`ocr_no_text_found`、`upload_unsupported_type`。

**前端下载示例：**

```javascript
async function convertScanToWord(pdfFile) {
  const form = new FormData();
  form.append("file", pdfFile);

  const res = await fetch("http://localhost:8000/api/upload/pdf-to-word", {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const { detail } = await res.json();
    throw new Error(detail.message);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename\*=UTF-8''(.+)$/);
  const filename = match ? decodeURIComponent(match[1]) : "converted.docx";

  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}
```

### 7. `POST /api/compare`（URL 与/或直接粘贴文本接口）

当每篇文章以 **URL 或直接粘贴的纯文本**提交（不涉及文件上传）时使用此接口，两种方式可混用（例如 A 用 URL、B 用粘贴文本）。

**请求体（URL）：**

```json
{
  "article_a_url": "https://outlet-a.com/story",
  "article_b_url": "https://outlet-b.com/story",
  "focus": "general"
}
```

**请求体（粘贴文本）：**

```json
{
  "article_a_text": "用户直接粘贴的完整文章正文……",
  "article_b_text": "第二篇文章的完整正文……",
  "focus": "general"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `article_a_url` | string | 否* | 文章 A 的 URL |
| `article_b_url` | string | 否* | 文章 B 的 URL |
| `article_a_text` | string | 否* | 文章 A 的粘贴纯文本正文 |
| `article_b_text` | string | 否* | 文章 B 的粘贴纯文本正文 |
| `focus` | string | 否 | 对比焦点，默认 `"general"` |

\* 每一侧（A/B）必须提供 URL 或粘贴文本其一；若同时提供，则以粘贴文本为准；两者都缺失返回 `422`。粘贴文本的 `source_type` 为 `"text"`，`url` 形如 `pasted-text://article-a`；文本少于 20 个字符会返回该篇的 `text_too_short`（或 `text_empty`）校验错误。

**`focus` 可选值：**

| 值 | 含义 |
|----|------|
| `general` | 通用对比（默认） |
| `political` | 政治框架 |
| `sentiment` | 情感倾向 |
| `economic` | 经济视角 |
| `social` | 社会视角 |

> Sprint 1 仅记录 `focus` 并原样返回；Sprint 2 起该字段会影响对比权重。

**成功响应 `200`（两篇都成功）：**

```json
{
  "focus": "general",
  "articles": [
    {
      "article_ref": "A",
      "url": "https://outlet-a.com/story",
      "title": "Budget passed",
      "source_domain": "outlet-a.com",
      "source_type": "url",
      "paragraphs": ["The government announced a new budget today..."],
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
      ],
      "paragraph_chunks": []
    }
  ],
  "errors": [],
  "processing": {
    "total_elapsed_seconds": 5.32,
    "message": "Processing completed in 5.32 seconds.",
    "steps": []
  },
  "nlp_debug": [],
  "comparison": null,
  "session_token": "a1b2c3d4e5f6789..."
}
```

**部分失败响应 `200`（一篇失败、一篇成功）：**

`/api/compare` **不会因单篇失败而返回 4xx**。失败信息在 `errors` 数组中，成功的文章仍在 `articles` 里。

```json
{
  "focus": "general",
  "articles": [
    {
      "article_ref": "B",
      "url": "https://outlet-b.com/story",
      "source_type": "url",
      "paragraphs": ["..."],
      "sentences": []
    }
  ],
  "errors": [
    {
      "stage": "extraction",
      "code": "extraction_paywall",
      "message": "This article appears to be behind a paywall or membership wall...",
      "article_ref": "A",
      "url": "https://outlet-a.com/story"
    }
  ],
  "processing": {
    "total_elapsed_seconds": 3.1,
    "message": "Processing completed in 3.1 seconds.",
    "steps": []
  },
  "comparison": null,
  "session_token": null
}
```

### 8. `POST /api/compare/files`（URL + 文件混合对比）

当任意一篇文章来自 **PDF/Word 上传**时使用此接口。每篇文章只能选 **URL、粘贴文本或文件其一**，不能同时传。

**请求：** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `article_a_url` | string | 否* | 文章 A 的 URL |
| `article_a_text` | string | 否* | 文章 A 的粘贴纯文本正文 |
| `article_a_file` | file | 否* | 文章 A 的 PDF/Word 文件 |
| `article_b_url` | string | 否* | 文章 B 的 URL |
| `article_b_text` | string | 否* | 文章 B 的粘贴纯文本正文 |
| `article_b_file` | file | 否* | 文章 B 的 PDF/Word 文件 |
| `focus` | string | 否 | 对比焦点，默认 `general` |

\* 每侧（A/B）必须且仅能提供 URL、粘贴文本或文件其一；一侧提供多个会返回 `400`。

**示例：A 上传文件 + B 使用 URL**

```javascript
const form = new FormData();
form.append("article_a_file", pdfFile); // File object
form.append("article_b_url", "https://www.bbc.com/news/articles/xxxx");
form.append("focus", "general");

const res = await fetch("http://localhost:8000/api/compare/files", {
  method: "POST",
  body: form,
});
```

**响应结构**与 `POST /api/compare` 相同。上传文章的 `source_type` 为 `"upload"`，`url` 形如 `upload://filename.pdf`。

### 9. 进度提示（英文）

#### 9.1 响应中的 `processing` 字段

所有耗时接口（fetch / upload / compare）在完成后都会返回 `processing`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_elapsed_seconds` | number | 总耗时（秒） |
| `message` | string | 英文摘要，如 `"Processing completed in 5.32 seconds."` |
| `steps[]` | array | 各步骤英文标签、状态、耗时 |

`steps[]` 每项：

| 字段 | 类型 | 说明 |
|------|------|------|
| `step` | string | 步骤名，如 `fetch`、`extraction`、`preprocessing`、`embedding` |
| `label` | string | 英文进度文案（可直接显示在 UI） |
| `status` | string | `pending` / `running` / `completed` / `failed` / `skipped` |
| `elapsed_seconds` | number \| null | 该步骤耗时 |
| `article_ref` | string \| null | `"A"` / `"B"` / `"fetch"` / `"upload"` |

#### 9.2 SSE 实时进度（进度条推荐）

以下接口返回 **Server-Sent Events**，适合前端实时更新进度条：

| 接口 | 用途 |
|------|------|
| `POST /api/fetch/stream` | 单篇 URL 抓取进度 |
| `POST /api/upload/stream` | 单文件上传进度 |
| `POST /api/compare/stream` | 双 URL 对比进度 |
| `POST /api/compare/files/stream` | 混合 URL/文件对比进度 |

**事件格式：**

```
event: progress
data: {"percent": 35, "message": "Extracting main article text for article A...", "elapsed_seconds": 2.1, "step": "extraction", "article_ref": "A", "status": "running"}

event: result
data: { ...完整 JSON 响应... }
```

| 事件 | 说明 |
|------|------|
| `progress` | 进度更新；用 `percent`（0–100）驱动进度条，`message` 显示英文状态 |
| `result` | 最终结果；结构与对应非 stream 接口相同 |

**前端 SSE 示例（compare）：**

```javascript
async function compareWithProgress(urlA, urlB, onProgress) {
  const res = await fetch("http://localhost:8000/api/compare/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      article_a_url: urlA,
      article_b_url: urlB,
      focus: "general",
    }),
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      const eventLine = lines.find((l) => l.startsWith("event:"));
      const dataLine = lines.find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const event = eventLine.replace("event:", "").trim();
      const data = JSON.parse(dataLine.replace("data:", "").trim());

      if (event === "progress") onProgress(data);
      if (event === "result") return data;
    }
  }
}
```

### 10. 错误码参考

所有错误均包含 `stage`、`code`、`message`（英文）。前端应优先按 **`code`** 分支展示提示。

#### 10.1 校验阶段（`stage: validation`）

| `code` | 含义 | 前端建议 |
|--------|------|----------|
| `url_missing` | URL 为空 | 请输入文章链接 |
| `url_invalid_scheme` | 不是 http/https | 链接必须以 http:// 或 https:// 开头 |
| `url_missing_host` | URL 缺少域名 | 请输入完整链接 |
| `input_missing` | 未提供任何来源 | 请提供 URL、粘贴文本或上传 PDF/Word |
| `text_empty` | 粘贴文本为空 | 请先粘贴文章正文再对比 |
| `text_too_short` | 粘贴文本少于 20 字符 | 请粘贴完整正文，而不只是标题 |

#### 10.2 网络阶段（`stage: fetch`）

| `code` | 含义 | 前端建议 |
|--------|------|----------|
| `fetch_timeout` | 下载超时 | 网站响应太慢，请换一篇或稍后重试 |
| `fetch_connection_failed` | 无法连接 | 检查链接和网络 |
| `fetch_http_401` | HTTP 401 | 该文章需要登录 |
| `fetch_http_403` | HTTP 403 | 网站拒绝访问（可能反爬） |
| `fetch_http_404` | HTTP 404 | 链接不存在或已失效 |
| `fetch_http_error` | 其他 HTTP 错误 | 无法下载该页面 |
| `fetch_page_too_large` | 页面过大 | 请使用直接的文章链接 |

#### 10.3 正文提取阶段（`stage: extraction`）

| `code` | 含义 | 前端建议 |
|--------|------|----------|
| `extraction_paywall` | **付费墙/会员墙** | 请上传 PDF/Word，或换公开链接 |
| `extraction_login_required` | **需要登录** | 请登录后导出 PDF/Word 再上传 |
| `extraction_not_news_page` | 不是新闻正文页 | 请使用文章详情页链接 |
| `extraction_js_rendered` | JS 动态渲染 | 请上传 PDF/Word 代替 |
| `extraction_empty` | 提不出正文 | 该页面无法识别为新闻 |

#### 10.4 上传阶段（`stage: upload`）

| `code` | 含义 | 前端建议 |
|--------|------|----------|
| `upload_unsupported_type` | 文件类型不支持 | 仅支持 .pdf 和 .docx |
| `upload_file_too_large` | 文件过大 | 请使用小于 10MB 的文件 |
| `upload_parse_failed` | 解析失败 | 文件可能损坏或加密 |
| `upload_empty_document` | 文档无文字 | 请检查文件内容 |

#### 10.5 OCR / 扫描 PDF（`stage: upload`）

| `code` | 含义 | 前端建议 |
|--------|------|----------|
| `ocr_unavailable` | 服务器未安装 Tesseract | OCR 不可用，请上传文字 PDF/Word |
| `ocr_failed` | OCR 无法识别扫描件 | 扫描质量太低，请换更清晰文件 |
| `ocr_no_text_found` | OCR 运行但未找到文字 | 页面可能空白或无法识别 |
| `pdf_not_image_based` | PDF 本身就是文字型 | 请改用 `/api/upload` |

### 11. 响应字段说明

顶层（compare）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `focus` | string | 本次请求的对比焦点 |
| `articles` | array | 成功处理的文章（0–2 篇） |
| `errors` | array | 失败文章的错误（0–2 条） |
| `processing` | object | 英文耗时与步骤摘要 |
| `nlp_debug` | array | SBERT 分块/向量调试信息 |
| `comparison` | object \| null | Sprint 2 对比结果；当前恒为 `null` |
| `session_token` | string \| null | 持久化成功时返回 |

`articles[]` 每篇文章：

| 字段 | 类型 | 说明 |
|------|------|------|
| `article_ref` | string | `"A"` 或 `"B"` |
| `url` | string | 文章 URL 或 `upload://文件名` |
| `source_type` | string | `"url"` 或 `"upload"` |
| `title` | string \| null | 标题 |
| `source_domain` | string \| null | 来源域名；上传时为 `"upload"` |
| `paragraphs` | string[] | 段落列表 |
| `sentences` | object[] | 句子级结构 |

`errors[]` 每条错误：

| 字段 | 类型 | 说明 |
|------|------|------|
| `stage` | string | 失败阶段 |
| `code` | string | 机器可读错误码（见第 10 节） |
| `message` | string | 英文可读说明 |
| `article_ref` | string \| null | `"A"` 或 `"B"` |
| `url` | string \| null | 出错的 URL 或 upload 路径 |

### 12. 前端组件对接映射

| 前端组件 | 使用的接口 / 字段 |
|----------|-------------------|
| URL Input Component | `POST /api/compare` 或 `/api/compare/files` |
| File Upload Component | `POST /api/upload`（预览）或 `/api/compare/files`（对比） |
| Progress Bar | `/stream` 接口的 `progress` 事件，或响应中的 `processing` |
| Error Banner | `errors[].code` + `errors[].message` |
| Comparison Focus Selector | `focus` |
| Article Viewer (Side-by-Side) | `articles` 中 `article_ref === "A"` / `"B"` |
| Paywall Hint | `code === "extraction_paywall"` 或 `"extraction_login_required"` → 引导上传 PDF/Word |

**推荐渲染逻辑：**

```text
1. 用户为每篇文章选择 URL 或上传 PDF/Word
2. 有任意文件 → POST /api/compare/files（或 /files/stream 显示进度条）
   纯 URL   → POST /api/compare（或 /stream）
3. 处理 errors[]：按 code 显示不同英文/中文提示
4. 遇到 paywall/login → 提示用户上传 PDF/Word
5. article_ref === "A" → 左栏；article_ref === "B" → 右栏
```

### 13. 前端调用示例

**纯 URL 对比：**

```javascript
const API_BASE = "http://localhost:8000";

async function compareArticles(urlA, urlB, focus = "general") {
  const res = await fetch(`${API_BASE}/api/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ article_a_url: urlA, article_b_url: urlB, focus }),
  });
  return res.json();
}
```

**混合 URL + 文件对比：**

```javascript
async function compareMixed(fileA, urlB) {
  const form = new FormData();
  form.append("article_a_file", fileA);
  form.append("article_b_url", urlB);
  form.append("focus", "general");

  const res = await fetch(`${API_BASE}/api/compare/files`, {
    method: "POST",
    body: form,
  });
  return res.json();
}
```

**按错误码展示提示：**

```javascript
const PAYWALL_CODES = new Set([
  "extraction_paywall",
  "extraction_login_required",
]);

function renderError(err) {
  if (PAYWALL_CODES.has(err.code)) {
    return "该文章需要会员/登录。请上传 PDF 或 Word 文件。";
  }
  return err.message; // 后端已返回英文说明，可直接显示或翻译
}
```

### 14. 前端校验建议

- URL 模式：两个 URL 都合法后再启用对比按钮
- 文件模式：仅允许 `.pdf`、`.docx`，单文件 ≤ 10MB
- 每篇文章：URL 和文件二选一，不能同时填

```javascript
function isValidHttpUrl(value) {
  try {
    const url = new URL(value.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function isAllowedUpload(file) {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx");
}
```

### 15. Sprint 2 预留：`comparison` 字段（草案）

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
    "summary": { "similarities": ["..."], "differences": ["..."] }
  }
}
```

### 16. 常见问题

**Q: 为什么 `/api/compare` 返回 200 但 `errors` 不为空？**  
A: 设计为「部分成功」——一篇失败不影响另一篇展示。

**Q: 遇到会员墙怎么办？**  
A: 后端返回 `code: "extraction_paywall"` 或 `"extraction_login_required"`。请引导用户上传 PDF/Word，使用 `POST /api/compare/files`。

**Q: 进度条用哪个接口？**  
A: 推荐使用 `/stream` 系列接口，监听 `progress` 事件的 `percent` 和 `message`（英文）。

**Q: 支持 .doc 吗？**  
A: 仅支持 `.docx`，不支持旧版 `.doc`。

**Q: 前端端口不是 3000/5173 怎么办？**  
A: 在 `backend/.env` 中设置：`CORS_ORIGINS=http://localhost:你的端口`

### 17. 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-06-23 | Sprint 1 | 初版：fetch / compare / health |
| 2026-06-25 | Sprint 1 | 分段中英版；新增 `/health/db`、`session_token` |
| 2026-06-29 | Sprint 1+ | 新增 PDF/Word 上传、SSE 英文进度、分场景错误码 `code` |
| 2026-07-16 | Sprint 1+ | 新增图片/扫描 PDF 识别、OCR + 噪音清洗、`pdf-to-word` 下载 |
| 2026-07-16 | Sprint 1+ | 新增直接粘贴文本对比（`article_a_text`/`article_b_text`） |

---
