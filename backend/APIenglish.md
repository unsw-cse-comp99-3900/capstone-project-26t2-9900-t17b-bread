# Frontend Integration Guide

This document describes the HTTP endpoints exposed by the **T17B BREAD** backend for frontend (React) integration.

- **Version:** Sprint 1+
- **Implemented:** URL fetch, PDF/Word upload, cleaning, sentence segmentation, English progress reporting, structured error codes, side-by-side display data
- **Not yet implemented:** Semantic comparison, highlighting, explanations (`comparison` reserved for Sprint 2)
- **Database:** Optional; when `DATABASE_URL` is set, `POST /api/compare` persists results and may return `session_token` (see `DATABASE_INTEGRATION.md`)

### 1. Basic information

| Item | Value |
|------|-------|
| Local base URL | `http://localhost:8000` |
| Interactive docs | `http://localhost:8000/docs` |
| JSON endpoints Content-Type | `application/json` |
| Upload endpoints Content-Type | `multipart/form-data` |
| Progress streaming | `text/event-stream` (SSE) |
| CORS enabled | Default: `http://localhost:3000`, `http://localhost:5173` |

Start the backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. Endpoint overview

| Method | Path | Purpose | Sprint |
|--------|------|---------|--------|
| `GET` | `/health` | Application health check | 1 |
| `GET` | `/health/db` | Database connectivity check | 1 |
| `POST` | `/api/fetch` | Fetch and clean a single URL article (preview) | 1 |
| `POST` | `/api/fetch/stream` | Same as above with live English progress (SSE) | 1 |
| `POST` | `/api/upload` | Upload PDF/Word and extract body text (auto-OCR for scans) | 1 |
| `POST` | `/api/upload/stream` | Same as above with live English progress (SSE) | 1 |
| `POST` | `/api/upload/pdf-type` | Detect if a PDF is text-based or a scanned image PDF | 1 |
| `POST` | `/api/upload/pdf-to-word` | OCR a scanned/image PDF and download a cleaned Word (.docx) | 1 |
| `POST` | `/api/compare` | Compare two URL articles | 1 |
| `POST` | `/api/compare/stream` | Same as above with live English progress (SSE) | 1 |
| `POST` | `/api/compare/files` | Compare two articles (URLs and/or uploaded files) | 1 |
| `POST` | `/api/compare/files/stream` | Same as above with live English progress (SSE) | 1 |

### 3. `GET /health`

Check whether the backend is running.

**Response `200`:**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### 4. `GET /health/db`

Check whether a database is configured and reachable.

**Response `200`:**

| Response | Meaning |
|----------|---------|
| `{"database":"ok"}` | Connected |
| `{"database":"error"}` | Configured but connection failed |
| `{"database":"disabled"}` | `DATABASE_URL` not set |

### 5. `POST /api/fetch`

Fetches one news article from a URL and returns cleaned title, source domain, and body.

**Request body:**

```json
{
  "url": "https://www.bbc.com/news/articles/xxxx"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Must start with `http://` or `https://` |

**Success `200`:**

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

**Error `422`:**

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

Upload a PDF (`.pdf`) or Word (`.docx`) document and extract readable article text.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | `.pdf` or `.docx`; max 10MB |

**Success `200`:**

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

**Error `422`:** Same shape as `/api/fetch`; `stage` may be `upload`.

> Text PDFs are read directly. Scanned/image PDFs are detected automatically
> and read with OCR (requires the Tesseract engine on the server). If OCR is
> unavailable, the error `code` is `ocr_unavailable`.

### 6a. `POST /api/upload/pdf-type`

Detect whether a PDF is **text-based** (selectable text) or an **image-based**
(scanned) PDF, so the frontend can choose the right flow.

**Request:** `multipart/form-data` with a single `file` field (must be `.pdf`).

**Success `200`:**

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

| Field | Type | Description |
|-------|------|-------------|
| `pdf_type` | string | `"text"` or `"image"` |
| `is_image_based` | boolean | `true` when the PDF is scanned and needs OCR |
| `page_count` | number | Number of pages |
| `chars_per_page` | number | Average directly-extractable characters per page |
| `pages_with_images` | number | Pages that contain embedded images |
| `ocr_available` | boolean | Whether the server can OCR image PDFs right now |
| `recommended_endpoint` | string | `/api/upload` (text) or `/api/upload/pdf-to-word` (scan) |

### 6b. `POST /api/upload/pdf-to-word`

Convert a **scanned/image PDF** into a cleaned, downloadable **Word (.docx)**
file. Pages are OCR'd, then page numbers, repeated headers/footers, and symbol
noise are removed so only the key text remains (also fed to the comparison
pipeline). Text-based PDFs are also accepted (their text is exported directly).

**Request:** `multipart/form-data` with a single `file` field (`.pdf`).

**Success `200`:** the response body is the **`.docx` binary** (not JSON).

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `Content-Disposition` | `attachment; filename*=UTF-8''<name>.docx` |
| `X-Extracted-Chars` | Number of cleaned characters extracted |
| `X-Extracted-Text-Preview` | URL-encoded preview (first ~180 chars) |

**Error `422`:** JSON `{ "detail": { stage, code, message, ... } }`. Common `code` values:
`ocr_unavailable`, `ocr_failed`, `ocr_no_text_found`, `upload_unsupported_type`.

**Frontend download example:**

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

### 7. `POST /api/compare` (URL and/or pasted-text endpoint)

Use this when each article is supplied as **a URL or as pasted plain text** (no file upload). You can mix the two (e.g. URL for A, pasted text for B).

**Request body (URLs):**

```json
{
  "article_a_url": "https://outlet-a.com/story",
  "article_b_url": "https://outlet-b.com/story",
  "focus": "general"
}
```

**Request body (pasted text):**

```json
{
  "article_a_text": "Full article body pasted by the user...",
  "article_b_text": "Full article body of the second story...",
  "focus": "general"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `article_a_url` | string | No* | URL for article A |
| `article_b_url` | string | No* | URL for article B |
| `article_a_text` | string | No* | Pasted plain-text body for article A |
| `article_b_text` | string | No* | Pasted plain-text body for article B |
| `focus` | string | No | Comparison focus; default `"general"` |

\* Each side (A/B) must supply **either** a URL or pasted text. If both are given for one side, the pasted text wins. Missing both for a side returns `422`. Pasted text has `source_type: "text"` and `url` like `pasted-text://article-a`. Text under 20 characters returns a per-article `text_too_short` (or `text_empty`) validation error.

**Allowed `focus` values:** `general`, `political`, `sentiment`, `economic`, `social`

> Sprint 1 only echoes `focus`; from Sprint 2 it will affect comparison weighting.

**Success `200` (both articles OK):**

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

**Partial success `200` (one failed, one OK):**

`/api/compare` does **not** return 4xx when only one article fails.

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

### 8. `POST /api/compare/files` (mixed URL + file compare)

Use when **either article** comes from an uploaded PDF/Word file. Each side must provide **either a URL or a file**, not both.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `article_a_url` | string | No* | URL for article A |
| `article_a_text` | string | No* | Pasted plain-text body for article A |
| `article_a_file` | file | No* | PDF/Word file for article A |
| `article_b_url` | string | No* | URL for article B |
| `article_b_text` | string | No* | Pasted plain-text body for article B |
| `article_b_file` | file | No* | PDF/Word file for article B |
| `focus` | string | No | Comparison focus; default `general` |

\* Each side (A/B) must supply exactly one of URL, pasted text, or file. Providing more than one for a side returns `400`.

**Example: file A + URL B**

```javascript
const form = new FormData();
form.append("article_a_file", pdfFile);
form.append("article_b_url", "https://www.bbc.com/news/articles/xxxx");
form.append("focus", "general");

const res = await fetch("http://localhost:8000/api/compare/files", {
  method: "POST",
  body: form,
});
```

**Response shape** matches `POST /api/compare`. Uploaded articles have `source_type: "upload"` and `url` like `upload://filename.pdf`.

### 9. Progress reporting (English)

#### 9.1 `processing` field in responses

All long-running endpoints return a `processing` summary when complete:

| Field | Type | Description |
|-------|------|-------------|
| `total_elapsed_seconds` | number | Total elapsed time in seconds |
| `message` | string | English summary, e.g. `"Processing completed in 5.32 seconds."` |
| `steps[]` | array | Per-step English labels, status, and timing |

Each item in `steps[]`:

| Field | Type | Description |
|-------|------|-------------|
| `step` | string | e.g. `fetch`, `extraction`, `preprocessing`, `embedding` |
| `label` | string | English progress text (safe to show in UI) |
| `status` | string | `pending` / `running` / `completed` / `failed` / `skipped` |
| `elapsed_seconds` | number \| null | Step duration |
| `article_ref` | string \| null | `"A"`, `"B"`, `"fetch"`, or `"upload"` |

#### 9.2 SSE live progress (recommended for progress bars)

These endpoints stream **Server-Sent Events** for real-time UI updates:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/fetch/stream` | Single URL fetch progress |
| `POST /api/upload/stream` | Single file upload progress |
| `POST /api/compare/stream` | Two-URL compare progress |
| `POST /api/compare/files/stream` | Mixed URL/file compare progress |

**Event format:**

```
event: progress
data: {"percent": 35, "message": "Extracting main article text for article A...", "elapsed_seconds": 2.1, "step": "extraction", "article_ref": "A", "status": "running"}

event: result
data: { ...full JSON response... }
```

| Event | Description |
|-------|-------------|
| `progress` | Progress update; use `percent` (0–100) for the bar and `message` for status text |
| `result` | Final payload; same shape as the non-stream endpoint |

**Frontend SSE example (compare):**

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

### 10. Error code reference

All errors include `stage`, `code`, and `message` (English). Branch on **`code`** in the frontend.

#### 10.1 Validation (`stage: validation`)

| `code` | Meaning | Suggested UI |
|--------|---------|--------------|
| `url_missing` | URL is empty | Please enter an article URL |
| `url_invalid_scheme` | Not http/https | URL must start with http:// or https:// |
| `url_missing_host` | Missing host | Please enter a complete URL |
| `input_missing` | No source provided | Provide a URL, pasted text, or upload PDF/Word |
| `text_empty` | Pasted text is empty | Paste the article content before comparing |
| `text_too_short` | Pasted text under 20 chars | Paste the full article body, not just the headline |

#### 10.2 Network (`stage: fetch`)

| `code` | Meaning | Suggested UI |
|--------|---------|--------------|
| `fetch_timeout` | Download timed out | Site is slow; try another link |
| `fetch_connection_failed` | Cannot connect | Check the URL and network |
| `fetch_http_401` | HTTP 401 | This article requires sign-in |
| `fetch_http_403` | HTTP 403 | Access forbidden (possible bot blocking) |
| `fetch_http_404` | HTTP 404 | Page not found |
| `fetch_http_error` | Other HTTP error | Could not download the page |
| `fetch_page_too_large` | Response too large | Use a direct article link |

#### 10.3 Extraction (`stage: extraction`)

| `code` | Meaning | Suggested UI |
|--------|---------|--------------|
| `extraction_paywall` | **Paywall / membership wall** | Upload PDF/Word or use a public link |
| `extraction_login_required` | **Login required** | Sign in and export PDF/Word, then upload |
| `extraction_not_news_page` | Not an article page | Use an article detail URL |
| `extraction_js_rendered` | JS-rendered content | Upload PDF/Word instead |
| `extraction_empty` | No readable body | Page does not look like a news article |

#### 10.4 Upload (`stage: upload`)

| `code` | Meaning | Suggested UI |
|--------|---------|--------------|
| `upload_unsupported_type` | Unsupported file type | Only .pdf and .docx are accepted |
| `upload_file_too_large` | File too large | Use a file under 10MB |
| `upload_parse_failed` | Parse failed | File may be corrupted or password-protected |
| `upload_empty_document` | No readable text | Check the document contents |

#### 10.5 OCR / scanned PDFs (`stage: upload`)

| `code` | Meaning | Suggested UI |
|--------|---------|--------------|
| `ocr_unavailable` | Tesseract not installed on server | OCR unavailable; upload a text PDF/Word |
| `ocr_failed` | OCR could not read the scan | Scan quality too low; try a clearer file |
| `ocr_no_text_found` | OCR ran but found no text | Pages may be blank or unreadable |
| `pdf_not_image_based` | PDF already has selectable text | Use `/api/upload` instead |

### 11. Response field reference

Top level (compare):

| Field | Type | Description |
|-------|------|-------------|
| `focus` | string | Requested comparison focus |
| `articles` | array | Successfully processed articles (0–2) |
| `errors` | array | Per-article errors (0–2) |
| `processing` | object | English timing and step summary |
| `nlp_debug` | array | SBERT chunk/embedding debug info |
| `comparison` | object \| null | Sprint 2 results; currently always `null` |
| `session_token` | string \| null | Returned when persistence succeeds |

Each item in `articles[]`:

| Field | Type | Description |
|-------|------|-------------|
| `article_ref` | string | `"A"` or `"B"` |
| `url` | string | Article URL or `upload://filename` |
| `source_type` | string | `"url"` or `"upload"` |
| `title` | string \| null | Title |
| `source_domain` | string \| null | Source domain; `"upload"` for files |
| `paragraphs` | string[] | Paragraph list |
| `sentences` | object[] | Sentence-level structure |

Each item in `errors[]`:

| Field | Type | Description |
|-------|------|-------------|
| `stage` | string | Failure stage |
| `code` | string | Machine-readable code (see section 10) |
| `message` | string | English human-readable message |
| `article_ref` | string \| null | `"A"` or `"B"` |
| `url` | string \| null | Failed URL or upload path |

### 12. Frontend component mapping

| Frontend component | API / fields |
|--------------------|--------------|
| URL Input Component | `POST /api/compare` or `/api/compare/files` |
| File Upload Component | `POST /api/upload` (preview) or `/api/compare/files` (compare) |
| Progress Bar | `/stream` endpoints → `progress` events, or `processing` in response |
| Error Banner | `errors[].code` + `errors[].message` |
| Comparison Focus Selector | `focus` |
| Article Viewer (Side-by-Side) | `articles` where `article_ref === "A"` / `"B"` |
| Paywall Hint | `code === "extraction_paywall"` or `"extraction_login_required"` → prompt PDF/Word upload |

**Recommended render flow:**

```text
1. User picks URL or PDF/Word for each article
2. Any file involved → POST /api/compare/files (or /files/stream for progress bar)
   URLs only    → POST /api/compare (or /stream)
3. Handle errors[] by code with distinct UI messages
4. On paywall/login → prompt PDF/Word upload
5. article_ref === "A" → left column; article_ref === "B" → right column
```

### 13. Frontend examples

**URL-only compare:**

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

**Mixed file + URL compare:**

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

**Render errors by code:**

```javascript
const PAYWALL_CODES = new Set([
  "extraction_paywall",
  "extraction_login_required",
]);

function renderError(err) {
  if (PAYWALL_CODES.has(err.code)) {
    return "This article requires membership or sign-in. Please upload a PDF or Word file.";
  }
  return err.message;
}
```

### 14. Client-side validation

- URL mode: enable Compare only when both URLs are valid
- File mode: allow only `.pdf` and `.docx`, max 10MB per file
- Per article: URL **or** file, never both

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

### 15. Sprint 2 – Semantic Comparison Output

Starting from Sprint 2, the backend now generates **semantic comparison results** using the paragraph embeddings produced by the NLP pipeline.

This affects the following endpoints:

- `POST /api/compare`
- `POST /api/compare/stream`
- `POST /api/compare/files`
- `POST /api/compare/files/stream`

When **both articles are successfully processed**, the backend returns:

```json
{
  "comparison": {
    "alignments": [...],
    "relationships": [...],
    "explanations": [...]
  }
}

```

### 16. FAQ

**Q: Why does `/api/compare` return 200 when `errors` is non-empty?**  
A: Partial success by design — one failed article does not block the other.

**Q: What should we do when a site has a paywall?**  
A: The backend returns `code: "extraction_paywall"` or `"extraction_login_required"`. Prompt the user to upload PDF/Word via `POST /api/compare/files`.

**Q: Which endpoint should power the progress bar?**  
A: Use the `/stream` variants and listen for `progress` events (`percent`, `message` in English).

**Q: Is `.doc` supported?**  
A: Only `.docx` is supported, not legacy `.doc`.

**Q: What if the frontend runs on a different port?**  
A: Set in `backend/.env`: `CORS_ORIGINS=http://localhost:YOUR_PORT`

### 17. Changelog

| Date | Version | Notes |
|------|---------|-------|
| 2026-06-23 | Sprint 1 | Initial: fetch, compare, health |
| 2026-06-25 | Sprint 1 | Split ZH/EN docs; added `/health/db`, `session_token` |
| 2026-06-29 | Sprint 1+ | PDF/Word upload, SSE English progress, structured error `code` |
| 2026-07-16 | Sprint 1+ | Image/scanned PDF detection, OCR + noise cleaning, `pdf-to-word` download |
| 2026-07-16 | Sprint 1+ | Pasted-text article input (`article_a_text`/`article_b_text`) on compare endpoints |

---
