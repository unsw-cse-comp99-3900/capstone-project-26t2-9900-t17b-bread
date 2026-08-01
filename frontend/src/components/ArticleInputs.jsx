import { articleInputModes } from '../config/appConfig'
import { isPdfFile } from '../utils/appHelpers'
import { getUrlHost } from '../utils/article'

function PdfToolbox({ file, pdfInfo, wordStatus, onConvertWord, isLoading }) {
  if (!isPdfFile(file)) {
    return null
  }

  const isImagePdf = pdfInfo?.is_image_based
  const typeLabel =
    pdfInfo == null
      ? null
      : isImagePdf
        ? 'Scanned / image PDF detected - OCR will be used.'
        : 'Text PDF detected - text can be read directly.'

  return (
    <div className="pdf-toolbox">
      {pdfInfo?.detecting && (
        <p className="input-hint">Checking whether this PDF is scanned...</p>
      )}
      {typeLabel && (
        <p className={`pdf-type-badge${isImagePdf ? ' pdf-type-badge--image' : ''}`}>
          {typeLabel}
        </p>
      )}
      {pdfInfo && !pdfInfo.ocr_available && isImagePdf && (
        <p className="input-hint input-hint--warn">
          OCR is not available on the server, so this scan may not be readable.
        </p>
      )}

      <button
        className="word-download-button"
        type="button"
        onClick={onConvertWord}
        disabled={isLoading || wordStatus?.state === 'loading'}
      >
        {wordStatus?.state === 'loading'
          ? 'Converting to Word...'
          : 'Download as Word (.docx)'}
      </button>

      {wordStatus?.state === 'success' && (
        <p className="input-hint input-hint--success">{wordStatus.message}</p>
      )}
      {wordStatus?.state === 'error' && (
        <p className="field-error">{wordStatus.message}</p>
      )}
    </div>
  )
}

export function ArticleSourceField({
  side,
  title,
  mode,
  url,
  text,
  file,
  pdfInfo,
  wordStatus,
  error,
  isLoading,
  onModeChange,
  onUrlChange,
  onTextChange,
  onFileChange,
  onConvertWord,
  onClear,
}) {
  const inputId = `article-${side.toLowerCase()}-url`
  const textId = `article-${side.toLowerCase()}-text`
  const fileId = `article-${side.toLowerCase()}-file`
  const errorId = `article-${side.toLowerCase()}-error`
  const urlHost = getUrlHost(url)
  const labelTarget =
    mode === 'url' ? inputId : mode === 'text' ? textId : fileId

  return (
    <div className="field-group">
      <div className="field-header">
        <label htmlFor={labelTarget}>
          <span className={`field-number${side === 'B' ? ' field-number--b' : ''}`}>
            {side}
          </span>
          {title}
        </label>

        <div className="source-toggle" aria-label={`${title} source type`}>
          {articleInputModes.map((option) => (
            <button
              className={
                mode === option.value
                  ? 'source-toggle__button active'
                  : 'source-toggle__button'
              }
              type="button"
              key={option.value}
              onClick={() => onModeChange(option.value)}
              disabled={isLoading}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {mode === 'url' && (
        <>
          <div className="input-with-action">
            <input
              className="url-input"
              id={inputId}
              type="url"
              value={url}
              onChange={onUrlChange}
              placeholder="https://news-outlet.com/article"
              aria-describedby={error ? errorId : undefined}
              aria-invalid={Boolean(error)}
              disabled={isLoading}
            />
            {url && (
              <button type="button" onClick={onClear} disabled={isLoading}>
                Clear
              </button>
            )}
          </div>
          {urlHost && <p className="input-hint">Source: {urlHost}</p>}
        </>
      )}

      {mode === 'text' && (
        <>
          <div className="input-with-action input-with-action--textarea">
            <textarea
              className="text-input"
              id={textId}
              value={text}
              onChange={onTextChange}
              rows={6}
              placeholder="Paste the full article text here..."
              aria-describedby={error ? errorId : undefined}
              aria-invalid={Boolean(error)}
              disabled={isLoading}
            />
            {text && (
              <button type="button" onClick={onClear} disabled={isLoading}>
                Clear
              </button>
            )}
          </div>
          <p className="input-hint">
            {text.trim().length} characters. Paste the article body directly -
            no link needed.
          </p>
        </>
      )}

      {mode === 'upload' && (
        <>
          <label
            className={`file-picker${file ? ' file-picker--selected' : ''}`}
            htmlFor={fileId}
          >
            <input
              id={fileId}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={onFileChange}
              aria-describedby={error ? errorId : undefined}
              aria-invalid={Boolean(error)}
              disabled={isLoading}
            />
            <span>{file ? file.name : 'Choose a PDF or Word file'}</span>
          </label>
          {file && (
            <button
              className="clear-input-button"
              type="button"
              onClick={onClear}
              disabled={isLoading}
            >
              Clear file
            </button>
          )}
          <p className="input-hint">
            Works with text PDFs, scanned/image PDFs (auto OCR), Word files,
            paywalled pages, or subscription content.
          </p>
          <PdfToolbox
            file={file}
            pdfInfo={pdfInfo}
            wordStatus={wordStatus}
            onConvertWord={onConvertWord}
            isLoading={isLoading}
          />
        </>
      )}

      {error && (
        <p className="field-error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  )
}
