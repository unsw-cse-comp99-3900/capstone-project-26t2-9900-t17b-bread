# Frontend Integration Guide

This document describes the HTTP endpoints exposed by the **T17B BREAD** backend for frontend (React) integration.

- **Version:** Sprint 1
- **Implemented:** Article fetch, cleaning, sentence segmentation, data for side-by-side display
- **Not yet implemented:** Semantic comparison, highlighting, explanations (`comparison` reserved for Sprint 2)
- **Database:** Optional; when `DATABASE_URL` is set, `POST /api/compare` persists results and may return `session_token` (see `DATABASE_INTEGRATION.md`)

### 1. Basic information

| Item | Value |
|------|-------|
| Local base URL | `http://localhost:8000` |
| Interactive docs | `http://localhost:8000/docs` |
| Content-Type | `application/json` |
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
| `POST` | `/api/fetch` | Fetch and clean a single article (preview) | 1 |
| `POST` | `/api/compare` | Process two articles; comparison-ready structure | 1 (comparison in Sprint 2) |

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

Check whether a database is configured and reachable (for integration testing).

**Response `200`:**

| Response | Meaning |
|----------|---------|
| `{"database":"ok"}` | Connected |
| `{"database":"error"}` | Configured but connection failed |
| `{"database":"disabled"}` | `DATABASE_URL` not set |

### 5. `POST /api/fetch`

Fetches one news article and returns cleaned title, source domain, and body. Use for single-article preview; use `/api/compare` for full comparison.

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
  "body_text": "The government announced a sweeping new national budget..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Requested URL |
| `title` | string \| null | Article title |
| `source_domain` | string \| null | Source domain |
| `body_text` | string | Cleaned body (nav, ads, footers removed) |

**Error `422`:**

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

**Error stages:**

| `stage` | Meaning | Suggested UI message |
|---------|---------|----------------------|
| `validation` | Invalid URL format | Please enter a valid http/https URL |
| `fetch` | Network failure (timeout, 403, 404, etc.) | Could not reach this article; try another URL |
| `extraction` | Page loaded but no article body extracted | This page does not look like a news article |

### 6. `POST /api/compare` (main endpoint)

The frontend Compare action should call this endpoint. Both articles are processed concurrently; structured paragraphs and sentences are returned for side-by-side display.

**Request body:**

```json
{
  "article_a_url": "https://outlet-a.com/story",
  "article_b_url": "https://outlet-b.com/story",
  "focus": "general"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `article_a_url` | string | Yes | URL for article A |
| `article_b_url` | string | Yes | URL for article B |
| `focus` | string | No | Comparison focus; default `"general"` |

**Allowed `focus` values:**

| Value | Meaning |
|-------|---------|
| `general` | General comparison (default) |
| `political` | Political framing |
| `sentiment` | Sentiment |
| `economic` | Economic emphasis |
| `social` | Social implications |

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
  "comparison": null,
  "session_token": "a1b2c3d4e5f6789..."
}
```

**Partial success `200` (one failed, one OK):**

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
  "comparison": null,
  "session_token": null
}
```

**Response fields:**

Top level:

| Field | Type | Description |
|-------|------|-------------|
| `focus` | string | Requested comparison focus |
| `articles` | array | Successfully processed articles (0–2) |
| `errors` | array | Per-article errors (0–2) |
| `comparison` | object \| null | Sprint 2 comparison results; currently always `null` |
| `session_token` | string \| null | Returned when persistence succeeds; `null` if DB disabled or write failed |

Each item in `articles[]`:

| Field | Type | Description |
|-------|------|-------------|
| `article_ref` | string | `"A"` or `"B"` for left/right column |
| `url` | string | Article URL |
| `title` | string \| null | Title |
| `source_domain` | string \| null | Source domain |
| `paragraphs` | string[] | Body split into paragraphs |
| `sentences` | object[] | Sentence-level structure |

Each item in `sentences[]`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable id, e.g. `"A-0"`; highlight anchor in Sprint 2 |
| `article_ref` | string | `"A"` or `"B"` |
| `text` | string | Sentence text |
| `paragraph_index` | number | Paragraph index (0-based) |
| `sentence_index` | number | Global sentence index (0-based) |
| `char_start` | number | Start offset in cleaned body |
| `char_end` | number | End offset in cleaned body |

Each item in `errors[]`:

| Field | Type | Description |
|-------|------|-------------|
| `stage` | string | `validation` / `fetch` / `extraction` |
| `message` | string | Human-readable message |
| `article_ref` | string \| null | Failed article ref |
| `url` | string \| null | URL that failed |

### 7. Frontend component mapping

| Frontend component | API / fields |
|--------------------|--------------|
| URL Input Component | `POST /api/compare` → `article_a_url`, `article_b_url` |
| Comparison Focus Selector | `focus` (affects results from Sprint 2) |
| Article Viewer (Side-by-Side) | `articles` where `article_ref === "A"` / `"B"`; body from `paragraphs` or `sentences` |
| Colour-Coded Difference Renderer | Sprint 2: `comparison` + `sentences[].id` for highlights |
| Similarity Rationale Panel | Sprint 2: explanations in `comparison` |

**Recommended render flow (Sprint 1):**

```text
1. User submits two URLs
2. POST /api/compare
3. If errors.length > 0 → show errors by article_ref; still render the other article
4. article_ref === "A" → left column
5. article_ref === "B" → right column
6. comparison === null → no highlights or explanations yet (Sprint 2)
```

### 8. Frontend examples

**Using `fetch`:**

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

**Using axios:**

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

**Single-article preview:**

```javascript
const { data } = await api.post("/api/fetch", {
  url: "https://www.bbc.com/news/articles/xxxx",
});
// data.title, data.source_domain, data.body_text
```

### 9. Client-side validation

Validate URLs before calling the backend (aligned with backend PROJ-1):

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

- Enable Compare only when both URLs are valid (PROJ-1 AC 1.2)
- Show inline validation errors without waiting for the API

### 10. Sprint 2: `comparison` field (draft)

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

| `label` | Meaning | Suggested colour |
|---------|---------|------------------|
| `aligned` | Semantically aligned | Green |
| `partially_aligned` | Partially aligned | Yellow |
| `divergent` | Divergent | Red |

> Draft only; will be updated when Sprint 2 is finalised. Guard with `comparison === null` for now.

### 11. FAQ

**Q: Why does `/api/compare` return 200 when `errors` is non-empty?**  
A: Partial success by design — one failed article does not block the other; handle both `articles` and `errors`.

**Q: Why do some sites return `stage: "fetch"`?**  
A: Some publishers block bots (403) or require login; this is expected.

**Q: What if the frontend runs on a different port?**  
A: Set in `backend/.env`: `CORS_ORIGINS=http://localhost:YOUR_PORT`

**Q: How do I check if the backend is up?**  
A: Call `GET /health` or open `http://localhost:8000/docs`.

**Q: What is `session_token`?**  
A: A session identifier returned when database persistence succeeds; `null` when the database is disabled or the write failed. Frontend can ignore it in Sprint 1.

### 12. Changelog

| Date | Version | Notes |
|------|---------|-------|
| 2026-06-23 | Sprint 1 | Initial: fetch, compare, health |
| 2026-06-25 | Sprint 1 | Split ZH/EN sections; added `/health/db`, `session_token` |
