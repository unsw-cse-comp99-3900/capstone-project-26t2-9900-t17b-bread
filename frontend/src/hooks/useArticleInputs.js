import { useState } from 'react'
import {
  createFileFromDemoAsset,
  isAllowedUpload,
  isPdfFile,
  isValidHttpUrl,
  isValidText,
  isValidUpload,
  readTextDemoAsset,
} from '../utils/appHelpers'
import { clearFieldError } from '../utils/errors'
import { downloadPdfAsWord, fetchPdfType } from '../services/uploadService'

const initialInput = {
  mode: 'url',
  url: '',
  text: '',
  file: null,
  pdfInfo: null,
  wordStatus: null,
}

export function useArticleInputs({
  minTextChars,
  maxUploadSizeBytes,
  onFormErrorsChange,
}) {
  const [articleInputA, setArticleInputA] = useState(initialInput)
  const [articleInputB, setArticleInputB] = useState(initialInput)

  function updateInput(side, updater) {
    const setInput = side === 'A' ? setArticleInputA : setArticleInputB
    setInput((currentInput) => ({
      ...currentInput,
      ...(typeof updater === 'function' ? updater(currentInput) : updater),
    }))
  }

  function clearSideError(side) {
    onFormErrorsChange((currentErrors) =>
      clearFieldError(currentErrors, side === 'A' ? 'articleA' : 'articleB'),
    )
  }

  async function detectPdfType(file, side) {
    if (!isPdfFile(file)) {
      updateInput(side, { pdfInfo: null })
      return
    }

    updateInput(side, { pdfInfo: { detecting: true } })

    try {
      updateInput(side, { pdfInfo: await fetchPdfType(file) })
    } catch {
      updateInput(side, { pdfInfo: null })
    }
  }

  function handleModeChange(side, nextMode) {
    updateInput(side, { mode: nextMode })
    clearSideError(side)
  }

  function handleUrlChange(side, event) {
    updateInput(side, { url: event.target.value })
    clearSideError(side)
  }

  function handleTextChange(side, event) {
    updateInput(side, { text: event.target.value })
    clearSideError(side)
  }

  function handleFileChange(side, event) {
    const file = event.target.files?.[0] ?? null
    updateInput(side, {
      file,
      wordStatus: null,
      pdfInfo: null,
    })
    clearSideError(side)
    detectPdfType(file, side)
  }

  function clearInput(side) {
    updateInput(side, {
      url: '',
      text: '',
      file: null,
      pdfInfo: null,
      wordStatus: null,
    })
    clearSideError(side)
  }

  function resetInputs() {
    setArticleInputA(initialInput)
    setArticleInputB(initialInput)
  }

  async function loadDemoSampleInputs(sample) {
    setArticleInputA((currentInput) => ({
      ...initialInput,
      wordStatus: currentInput.wordStatus,
    }))
    setArticleInputB((currentInput) => ({
      ...initialInput,
      wordStatus: currentInput.wordStatus,
    }))

    if (sample.kind === 'url') {
      setArticleInputA({ ...initialInput, mode: 'url', url: sample.articleA.url })
      setArticleInputB({ ...initialInput, mode: 'url', url: sample.articleB.url })
      return
    }

    if (sample.kind === 'text') {
      const [articleAText, articleBText] = await Promise.all([
        readTextDemoAsset(sample.articleA),
        readTextDemoAsset(sample.articleB),
      ])

      setArticleInputA({ ...initialInput, mode: 'text', text: articleAText })
      setArticleInputB({ ...initialInput, mode: 'text', text: articleBText })
      return
    }

    const [articleAFile, articleBFile] = await Promise.all([
      createFileFromDemoAsset(sample.articleA),
      createFileFromDemoAsset(sample.articleB),
    ])

    setArticleInputA({ ...initialInput, mode: 'upload', file: articleAFile })
    setArticleInputB({ ...initialInput, mode: 'upload', file: articleBFile })
    detectPdfType(articleAFile, 'A')
    detectPdfType(articleBFile, 'B')
  }

  async function convertPdfToWord(side) {
    const input = side === 'A' ? articleInputA : articleInputB

    if (!isPdfFile(input.file)) {
      updateInput(side, {
        wordStatus: {
          state: 'error',
          message: 'Word conversion is only available for PDF files.',
        },
      })
      return
    }

    updateInput(side, { wordStatus: { state: 'loading' } })

    try {
      const filename = await downloadPdfAsWord(input.file)
      updateInput(side, {
        wordStatus: {
          state: 'success',
          message: `Saved "${filename}". Check your downloads folder.`,
        },
      })
    } catch (error) {
      updateInput(side, {
        wordStatus: {
          state: 'error',
          message: `The PDF could not be converted to Word. ${error.message}`,
        },
      })
    }
  }

  function isSideReady(input) {
    if (input.mode === 'url') {
      return isValidHttpUrl(input.url)
    }
    if (input.mode === 'text') {
      return isValidText(input.text)
    }
    return isValidUpload(input.file)
  }

  function validateArticleInput(input) {
    if (input.mode === 'url') {
      return isValidHttpUrl(input.url)
        ? ''
        : 'Paste a complete article link beginning with http:// or https://.'
    }

    if (input.mode === 'text') {
      return isValidText(input.text)
        ? ''
        : `Paste at least ${minTextChars} characters of article text.`
    }

    if (!input.file) {
      return 'Choose a PDF or Word document for this article.'
    }

    if (!isAllowedUpload(input.file)) {
      return 'Only .pdf and .docx files are supported.'
    }

    if (input.file.size > maxUploadSizeBytes) {
      return 'Use a file under 10MB.'
    }

    return ''
  }

  return {
    articleInputA,
    articleInputB,
    canCompare: isSideReady(articleInputA) && isSideReady(articleInputB),
    handleArticleAModeChange: (nextMode) => handleModeChange('A', nextMode),
    handleArticleBModeChange: (nextMode) => handleModeChange('B', nextMode),
    handleArticleAUrlChange: (event) => handleUrlChange('A', event),
    handleArticleBUrlChange: (event) => handleUrlChange('B', event),
    handleArticleATextChange: (event) => handleTextChange('A', event),
    handleArticleBTextChange: (event) => handleTextChange('B', event),
    handleArticleAFileChange: (event) => handleFileChange('A', event),
    handleArticleBFileChange: (event) => handleFileChange('B', event),
    clearArticleAInput: () => clearInput('A'),
    clearArticleBInput: () => clearInput('B'),
    resetInputs,
    loadDemoSampleInputs,
    convertArticleAToWord: () => convertPdfToWord('A'),
    convertArticleBToWord: () => convertPdfToWord('B'),
    validateInputs: () => ({
      articleA: validateArticleInput(articleInputA),
      articleB: validateArticleInput(articleInputB),
    }),
  }
}
