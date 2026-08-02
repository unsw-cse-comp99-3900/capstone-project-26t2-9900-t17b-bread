export const focusOptions = [
  { value: 'general', label: 'General comparison' },
  { value: 'political', label: 'Political framing' },
  { value: 'sentiment', label: 'Sentiment' },
  { value: 'economic', label: 'Economic focus' },
  { value: 'social', label: 'Social impact' },
]

export const relationshipOptions = [
  { value: 'aligned', label: 'Similar' },
  { value: 'partially_aligned', label: 'Partially similar' },
  { value: 'divergent', label: 'Divergent' },
]

export const articleInputModes = [
  { value: 'url', label: 'URL' },
  { value: 'text', label: 'Paste text' },
  { value: 'upload', label: 'PDF / Word' },
]

export const maxUploadSizeBytes = 10 * 1024 * 1024
export const minTextChars = 20

export const demoIndexPath = '/demo-files/index.json'
export const authSessionKey = 'narrative-diff-auth'

export const friendlyErrorMessages = {
  url_missing: {
    title: 'Missing article link',
    message: 'Please paste a complete article URL before comparing.',
    action: 'Use a link that starts with http:// or https://.',
  },
  url_invalid_scheme: {
    title: 'Link format is not supported',
    message: 'The article link needs to be a normal web link.',
    action: 'Check that it starts with http:// or https://.',
  },
  url_missing_host: {
    title: 'Incomplete article link',
    message: 'This link is missing the website name.',
    action: 'Paste the full article URL from your browser address bar.',
  },
  fetch_timeout: {
    title: 'The website took too long to respond',
    message: 'The article site may be slow or temporarily unavailable.',
    action: 'Try again later, or use a different article link.',
  },
  fetch_connection_failed: {
    title: 'Could not connect to the website',
    message: 'The link may be wrong, blocked, or unavailable from this server.',
    action: 'Open the link in your browser to check it, then try again.',
  },
  fetch_http_401: {
    title: 'This article requires sign-in',
    message: 'The news site did not allow access without an account.',
    action: 'Use a public article link, or upload a saved PDF/Word copy when file upload is available.',
  },
  fetch_http_403: {
    title: 'The website blocked access',
    message: 'Some news sites block automated article fetching.',
    action: 'Try another source, or upload a saved PDF/Word copy when file upload is available.',
  },
  fetch_http_404: {
    title: 'Article page was not found',
    message: 'The URL may be old, mistyped, or no longer available.',
    action: 'Check the link and paste the article URL again.',
  },
  fetch_http_error: {
    title: 'The website returned an error',
    message: 'The article page could not be downloaded from the news site.',
    action: 'Try again later or use another article link.',
  },
  fetch_page_too_large: {
    title: 'The page is too large to process',
    message: 'This link may point to a feed, homepage, or very large page instead of one article.',
    action: 'Use the direct URL for a single news article.',
  },
  extraction_paywall: {
    title: 'This article may be behind a paywall',
    message: 'The news site appears to require a subscription or membership to read the full article.',
    action: 'Use a publicly accessible article, or upload a saved PDF/Word copy when file upload is available.',
  },
  extraction_login_required: {
    title: 'This article requires login',
    message: 'The article text is not visible until a reader signs in.',
    action: 'Sign in on the news site and save the article as PDF/Word, or use another public link.',
  },
  extraction_not_news_page: {
    title: 'This does not look like a news article',
    message: 'The page may be a homepage, live feed, topic page, or search result.',
    action: 'Paste the URL for a specific article page.',
  },
  extraction_js_rendered: {
    title: 'The article text could not be read',
    message: 'This site loads the story in a way the backend cannot extract automatically.',
    action: 'Try another source, or upload a saved PDF/Word copy when file upload is available.',
  },
  extraction_empty: {
    title: 'No readable article text found',
    message: 'The backend reached the page, but could not find enough article content.',
    action: 'Check that the link opens a full article, not a video page or listing page.',
  },
  upload_unsupported_type: {
    title: 'File type is not supported',
    message: 'Only PDF and Word documents can be processed.',
    action: 'Upload a .pdf or .docx file.',
  },
  upload_file_too_large: {
    title: 'File is too large',
    message: 'The uploaded document is bigger than the current limit.',
    action: 'Use a file under 10MB.',
  },
  upload_parse_failed: {
    title: 'File could not be read',
    message: 'The document may be corrupted, password-protected, or not text-based.',
    action: 'Try exporting the article again as PDF or Word.',
  },
  upload_empty_document: {
    title: 'No readable text found in the file',
    message: 'The uploaded document does not contain enough extractable article text.',
    action: 'Check the file contents and upload a readable copy.',
  },
  text_empty: {
    title: 'No text was pasted',
    message: 'The article text box is empty.',
    action: 'Paste the article content into the text box before comparing.',
  },
  text_too_short: {
    title: 'Pasted text is too short',
    message: 'There is not enough text to analyse this article.',
    action: 'Paste the full article body, not just the headline.',
  },
  ocr_unavailable: {
    title: 'Scanned PDF reading is unavailable',
    message: 'The server cannot run OCR right now, so this scanned PDF cannot be read.',
    action: 'Upload a text-based PDF/Word file, or paste the article text instead.',
  },
  ocr_failed: {
    title: 'Scanned PDF could not be read',
    message: 'OCR was unable to recognise text in this scanned document.',
    action: 'Try a clearer scan, a text-based PDF, or paste the article text.',
  },
  ocr_no_text_found: {
    title: 'No text found in the scanned PDF',
    message: 'OCR completed but did not find readable article text.',
    action: 'Check that the PDF contains article pages, then try again.',
  },
  pdf_not_image_based: {
    title: 'This PDF already has selectable text',
    message: 'This looks like a text PDF, so OCR conversion was not needed.',
    action: 'Use it directly for comparison, or download it as Word if you like.',
  },
}
