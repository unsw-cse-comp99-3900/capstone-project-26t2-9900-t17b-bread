export const longArticleAText = [
  'Article A opening paragraph describes a major volcanic eruption near a town and the emergency response around damaged roads.',
  'Residents were moved before the most dangerous lava flow, while officials stressed that evacuation reduced immediate risk.',
  'Emergency teams built barriers and monitored fissures as volcanic activity changed direction during the incident.',
].join('\n\n')

export const longArticleBText = [
  'Article B opening paragraph describes the same volcanic eruption near the town and explains how authorities ordered an evacuation.',
  'The report focuses on dramatic lava scenes, destroyed ground, and anxiety among residents who had already left the area.',
  'Civil protection teams worked with scientists and local officials to monitor fissures and reduce infrastructure damage.',
].join('\n\n')

export const demoIndexResponse = ['/demo-files/volcano-text/demo.json']

export const demoMetadata = {
  id: 'volcano-text',
  label: 'Volcano text',
  shortLabel: 'Volcano',
  description: 'Iceland volcano pasted text demo',
  kind: 'text',
  focus: 'general',
  articleA: {
    filePath: '/demo-files/volcano-text/1a.txt',
  },
  articleB: {
    filePath: '/demo-files/volcano-text/1b.txt',
  },
}

export const comparisonPayload = {
  focus: 'general',
  comparison_id: 42,
  processing: {
    message: 'Comparison finished.',
  },
  errors: [],
  articles: [
    {
      article_ref: 'A',
      title: 'Volcano eruption forces evacuations',
      source_domain: 'demo-a.test',
      source_type: 'text',
      paragraphs: [
        'A volcano erupted near the Icelandic town after weeks of earthquakes and warnings from officials.',
        'Residents were evacuated before lava reached the most dangerous areas around nearby roads.',
        'Emergency teams built defensive barriers to redirect lava and protect infrastructure.',
      ],
      sentences: [],
    },
    {
      article_ref: 'B',
      title: 'Reykjavik region faces lava disruption',
      source_domain: 'demo-b.test',
      source_type: 'text',
      paragraphs: [
        'An eruption near Reykjavik forced Icelandic authorities to evacuate residents after weeks of warnings.',
        'The eruption created dramatic scenes as lava flowed across dark volcanic ground.',
        'Civil protection teams monitored fissures and damage risks around local infrastructure.',
      ],
      sentences: [],
    },
  ],
  comparison: {
    focus: 'general',
    summary: {
      statement:
        'The two reports align on the eruption, but differ in emphasis and detail.',
    },
    matches: [
      {
        id: 'pair-1',
        pair_number: 1,
        a_paragraph_index: 0,
        b_paragraph_index: 0,
        label: 'aligned',
        score: 0.89,
        confidence: 'high',
        explanation:
          'Both paragraphs describe the same eruption and evacuation context.',
      },
      {
        id: 'pair-2',
        pair_number: 2,
        a_paragraph_index: 1,
        b_paragraph_index: 1,
        label: 'partially_aligned',
        score: 0.74,
        confidence: 'medium',
        explanation:
          'The paragraphs discuss related impacts but place emphasis on different details.',
      },
      {
        id: 'pair-3',
        pair_number: 3,
        a_paragraph_index: 2,
        b_paragraph_index: 2,
        label: 'divergent',
        score: 0.42,
        confidence: 'medium',
        explanation:
          'The paragraphs focus on different response details and risk framing.',
      },
    ],
  },
}
