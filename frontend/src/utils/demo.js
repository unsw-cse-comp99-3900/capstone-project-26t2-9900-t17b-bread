export function groupDemoSamples(demoSamples) {
  return [
    {
      label: 'URL',
      samples: demoSamples.filter((sample) => sample.kind === 'url'),
    },
    {
      label: 'PDF',
      samples: demoSamples.filter(
        (sample) =>
          sample.kind === 'upload' &&
          sample.articleA?.fileName?.toLowerCase().endsWith('.pdf'),
      ),
    },
    {
      label: 'Word',
      samples: demoSamples.filter(
        (sample) =>
          sample.kind === 'upload' &&
          sample.articleA?.fileName?.toLowerCase().endsWith('.docx'),
      ),
    },
    {
      label: 'Text',
      samples: demoSamples.filter((sample) => sample.kind === 'text'),
    },
  ]
}
