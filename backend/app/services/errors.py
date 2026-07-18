"""Structured pipeline errors with machine-readable codes and English messages."""

from __future__ import annotations

from enum import Enum


class PipelineStage(str, Enum):
    VALIDATION = "validation"
    FETCH = "fetch"
    EXTRACTION = "extraction"
    UPLOAD = "upload"
    PREPROCESSING = "preprocessing"
    SENTENCE_PREPARATION = "sentence_preparation"
    EMBEDDING = "embedding"


class ErrorCode(str, Enum):
    """Stable error codes for frontend branching and user-facing messages."""

    # Validation
    URL_MISSING = "url_missing"
    URL_INVALID_SCHEME = "url_invalid_scheme"
    URL_MISSING_HOST = "url_missing_host"
    INPUT_MISSING = "input_missing"
    TEXT_EMPTY = "text_empty"
    TEXT_TOO_SHORT = "text_too_short"

    # Fetch / network
    FETCH_TIMEOUT = "fetch_timeout"
    FETCH_CONNECTION_FAILED = "fetch_connection_failed"
    FETCH_HTTP_401 = "fetch_http_401"
    FETCH_HTTP_403 = "fetch_http_403"
    FETCH_HTTP_404 = "fetch_http_404"
    FETCH_HTTP_ERROR = "fetch_http_error"
    FETCH_PAGE_TOO_LARGE = "fetch_page_too_large"

    # Extraction
    EXTRACTION_EMPTY = "extraction_empty"
    EXTRACTION_PAYWALL = "extraction_paywall"
    EXTRACTION_LOGIN_REQUIRED = "extraction_login_required"
    EXTRACTION_NOT_NEWS_PAGE = "extraction_not_news_page"
    EXTRACTION_JS_RENDERED = "extraction_js_rendered"

    # Upload / documents
    UPLOAD_FILE_MISSING = "upload_file_missing"
    UPLOAD_UNSUPPORTED_TYPE = "upload_unsupported_type"
    UPLOAD_FILE_TOO_LARGE = "upload_file_too_large"
    UPLOAD_PARSE_FAILED = "upload_parse_failed"
    UPLOAD_EMPTY_DOCUMENT = "upload_empty_document"

    # OCR (scanned / image PDFs)
    OCR_UNAVAILABLE = "ocr_unavailable"
    OCR_FAILED = "ocr_failed"
    OCR_NO_TEXT_FOUND = "ocr_no_text_found"
    PDF_NOT_IMAGE_BASED = "pdf_not_image_based"

    # Generic
    UNKNOWN = "unknown"


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.URL_MISSING: (
        "The article URL is missing or empty. Please provide a valid http:// or https:// link."
    ),
    ErrorCode.URL_INVALID_SCHEME: (
        "The URL must start with http:// or https://. Other schemes such as ftp:// are not supported."
    ),
    ErrorCode.URL_MISSING_HOST: (
        "The URL is missing a host name. Example: https://www.example.com/article"
    ),
    ErrorCode.INPUT_MISSING: (
        "No article source was provided. Supply a URL, pasted text, or an uploaded PDF/Word file."
    ),
    ErrorCode.TEXT_EMPTY: (
        "The pasted article text is empty. Please paste the article content before comparing."
    ),
    ErrorCode.TEXT_TOO_SHORT: (
        "The pasted article text is too short to analyse. Please paste the full article content."
    ),
    ErrorCode.FETCH_TIMEOUT: (
        "The request timed out while downloading the article. The website may be slow or unreachable."
    ),
    ErrorCode.FETCH_CONNECTION_FAILED: (
        "Could not connect to the article URL. Check the link, your network connection, and try again."
    ),
    ErrorCode.FETCH_HTTP_401: (
        "Access to this article was denied (HTTP 401). The page may require sign-in credentials."
    ),
    ErrorCode.FETCH_HTTP_403: (
        "Access to this article was forbidden (HTTP 403). The site may block automated requests."
    ),
    ErrorCode.FETCH_HTTP_404: (
        "The article was not found (HTTP 404). The link may be broken or the page may have been removed."
    ),
    ErrorCode.FETCH_HTTP_ERROR: (
        "The website returned an error while downloading the article. Please try another link."
    ),
    ErrorCode.FETCH_PAGE_TOO_LARGE: (
        "The downloaded page is too large to process safely. Please use a direct article link."
    ),
    ErrorCode.EXTRACTION_EMPTY: (
        "No readable article text could be extracted from this page. It may not be a news article."
    ),
    ErrorCode.EXTRACTION_PAYWALL: (
        "This article appears to be behind a paywall or membership wall. "
        "Please upload a PDF/Word copy or use a publicly accessible link."
    ),
    ErrorCode.EXTRACTION_LOGIN_REQUIRED: (
        "This page requires login or subscription before the full article can be read. "
        "Please sign in on the publisher site and upload the article as PDF/Word instead."
    ),
    ErrorCode.EXTRACTION_NOT_NEWS_PAGE: (
        "The page does not look like a news article (for example, a home page, search page, or video page)."
    ),
    ErrorCode.EXTRACTION_JS_RENDERED: (
        "The article body may be loaded by JavaScript after the page opens. "
        "Try uploading a PDF/Word export of the article instead."
    ),
    ErrorCode.UPLOAD_FILE_MISSING: (
        "No file was uploaded. Please choose a PDF or Word (.docx) document."
    ),
    ErrorCode.UPLOAD_UNSUPPORTED_TYPE: (
        "Unsupported file type. Only PDF (.pdf) and Word (.docx) files are accepted."
    ),
    ErrorCode.UPLOAD_FILE_TOO_LARGE: (
        "The uploaded file is too large. Please use a smaller PDF or Word document."
    ),
    ErrorCode.UPLOAD_PARSE_FAILED: (
        "The uploaded document could not be read. The file may be corrupted or password-protected."
    ),
    ErrorCode.UPLOAD_EMPTY_DOCUMENT: (
        "The uploaded document contains no readable text. Please check the file and try again."
    ),
    ErrorCode.OCR_UNAVAILABLE: (
        "OCR is not available on the server. The Tesseract OCR engine is required to read "
        "image-based (scanned) PDFs. Please install Tesseract, or upload a text-based PDF/Word file."
    ),
    ErrorCode.OCR_FAILED: (
        "The scanned PDF could not be recognised by OCR. The scan quality may be too low. "
        "Please try a clearer scan or a text-based document."
    ),
    ErrorCode.OCR_NO_TEXT_FOUND: (
        "OCR ran but found no usable text in this image-based PDF. "
        "The pages may be blank, photos, or too low quality to read."
    ),
    ErrorCode.PDF_NOT_IMAGE_BASED: (
        "This PDF already contains selectable text, so image OCR is not needed. "
        "Use the standard upload to extract its text directly."
    ),
    ErrorCode.UNKNOWN: (
        "An unexpected error occurred while processing the article. Please try again."
    ),
}


class PipelineError(Exception):
    """Raised when a pipeline stage fails for a specific article."""

    def __init__(
        self,
        stage: PipelineStage,
        code: ErrorCode,
        *,
        article_ref: str | None = None,
        url: str | None = None,
        message: str | None = None,
    ) -> None:
        self.stage = stage
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, ERROR_MESSAGES[ErrorCode.UNKNOWN])
        self.article_ref = article_ref
        self.url = url
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "code": self.code.value,
            "message": self.message,
            "article_ref": self.article_ref,
            "url": self.url,
        }
