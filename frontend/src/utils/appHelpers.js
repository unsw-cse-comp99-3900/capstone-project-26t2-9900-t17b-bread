import { maxUploadSizeBytes, minTextChars } from '../config/appConfig'

export function isValidHttpUrl(value) {
  try {
    const url = new URL(value.trim())
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function isAllowedUpload(file) {
  if (!file) {
    return false
  }

  const fileName = file.name.toLowerCase()
  return fileName.endsWith('.pdf') || fileName.endsWith('.docx')
}

export function isValidUpload(file) {
  return Boolean(file) && isAllowedUpload(file) && file.size <= maxUploadSizeBytes
}

export function isValidText(text) {
  return typeof text === 'string' && text.trim().length >= minTextChars
}

export function isPdfFile(file) {
  return Boolean(file) && file.name.toLowerCase().endsWith('.pdf')
}

export function getDownloadFilename(contentDisposition, fallback) {
  if (!contentDisposition) {
    return fallback
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return fallback
    }
  }

  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  return plainMatch ? plainMatch[1] : fallback
}

export function downloadJsonFile(payload, filename) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  })
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}

export async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.append(textarea)
  textarea.select()
  document.execCommand('copy')
  textarea.remove()
}

export async function createFileFromDemoAsset({ filePath, fileName, mimeType }) {
  const response = await fetch(filePath)

  if (!response.ok) {
    throw new Error(`Could not load ${fileName}.`)
  }

  const blob = await response.blob()
  return new File([blob], fileName, { type: mimeType })
}

export async function readTextDemoAsset({ filePath }) {
  const response = await fetch(filePath)

  if (!response.ok) {
    throw new Error(`Could not load ${filePath}.`)
  }

  return response.text()
}
