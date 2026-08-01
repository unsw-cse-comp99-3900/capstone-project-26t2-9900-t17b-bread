import { getDownloadFilename } from '../utils/appHelpers'
import { getFriendlyError } from '../utils/errors'

export async function fetchPdfType(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/upload/pdf-type', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    return null
  }

  return response.json()
}

export async function downloadPdfAsWord(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/upload/pdf-to-word', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let message = 'The PDF could not be converted to Word.'
    try {
      const errorPayload = await response.json()
      const friendly = getFriendlyError(errorPayload?.detail ?? errorPayload)
      message = `${friendly.title}: ${friendly.message}`
    } catch {
      // keep default message
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  const filename = getDownloadFilename(
    response.headers.get('Content-Disposition'),
    `${file.name.replace(/\.pdf$/i, '')}.docx`,
  )

  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)

  return filename
}
