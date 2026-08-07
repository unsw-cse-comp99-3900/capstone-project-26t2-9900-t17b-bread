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
    selected_factor: 'political',
    summary: {
      match_count: 3,
      aligned_count: 1,
      partially_aligned_count: 1,
      divergent_count: 1,
      average_match_strength: 13.7,
      average_factor_relevance: 13,
      average_stance_discrepancy: 7.3,
      statement:
        'The two reports align on the eruption, but differ in emphasis and detail.',
    },
    score_guides: {
      match_strength: {
        title: 'Match Strength',
        question: 'How strongly do these two paragraph chunks correspond?',
        scale_min: 0,
        scale_max: 20,
        bands: [
          { min: 17, max: 20, level: 'Very strong', interpretation: 'Highly corresponding content.' },
        ],
      },
      factor_relevance: {
        title: 'Political Relevance',
        factor: 'political',
        question:
          'How strongly is this matched pair related to the automatically selected political factor?',
        scale_min: 0,
        scale_max: 20,
        disclaimer:
          'Political was selected once for the complete article pair and is applied consistently to every matched pair.',
        bands: [
          { min: 0, max: 4, level: 'very_low', interpretation: 'Political content is largely absent.' },
          { min: 5, max: 8, level: 'low', interpretation: 'Political content is mentioned only briefly.' },
          { min: 9, max: 12, level: 'moderate', interpretation: 'Political content is meaningful but not central.' },
          { min: 13, max: 16, level: 'strong', interpretation: 'Political content is an important part of the pair.' },
          { min: 17, max: 20, level: 'very_strong', interpretation: 'Political content is central to the pair.' },
        ],
      },
      stance_discrepancy: {
        title: 'Stance Discrepancy',
        question: 'How different are the stance or framing signals?',
        scale_min: 0,
        scale_max: 20,
        disclaimer: 'This is not a factuality score.',
        bands: [
          { min: 9, max: 12, level: 'Moderate', interpretation: 'Noticeable framing difference.' },
        ],
      },
    },
    sorting: {
      default: 'best_match',
      options: [
        {
          key: 'best_match',
          label: 'Best Match',
          score_path: 'match_strength.score',
          direction: 'descending',
          description: 'Show strongest corresponding paragraph pairs first.',
        },
        {
          key: 'selected_factor',
          label: 'Most Relevant to Political',
          score_path: 'factor_relevance.score',
          secondary_score_path: 'match_strength.score',
          direction: 'descending',
          description:
            'Show pairs most relevant to the political factor first. Match Strength is used as the tie-breaker.',
        },
        {
          key: 'most_divergent',
          label: 'Most Divergent',
          score_path: 'stance_discrepancy.score',
          secondary_score_path: 'match_strength.score',
          direction: 'descending',
          description: 'Show strongest stance or framing discrepancies first.',
        },
        {
          key: 'article_order',
          label: 'Article Order',
          score_path: 'a_chunk_index',
          secondary_score_path: 'b_chunk_index',
          direction: 'ascending',
          description: 'Show matched pairs in article order.',
        },
      ],
    },
    matches: [
      {
        id: 'pair-1',
        pair_number: 1,
        a_paragraph_index: 0,
        b_paragraph_index: 0,
        a_chunk_index: 0,
        b_chunk_index: 0,
        a_text_preview:
          'A volcano erupted near the Icelandic town after weeks of earthquakes and warnings from officials.',
        b_text_preview:
          'An eruption near Reykjavik forced Icelandic authorities to evacuate residents after weeks of warnings.',
        label: 'aligned',
        reason_code: 'semantic_match_with_lexical_difference',
        match_strength: {
          score: 18,
          level: 'Very strong',
          interpretation: 'The paragraphs describe the same event context.',
        },
        factor_relevance: {
          factor: 'political',
          score: 12,
          level: 'moderate',
          interpretation:
            'Political content is meaningful but not central to this matched pair.',
        },
        stance_discrepancy: {
          score: 3,
          level: 'Low',
          interpretation: 'Little stance difference is visible.',
          disclaimer: 'This is not a factuality score.',
        },
        explanation:
          'Both paragraphs describe the same eruption and evacuation context.',
      },
      {
        id: 'pair-2',
        pair_number: 2,
        a_paragraph_index: 1,
        b_paragraph_index: 1,
        a_chunk_index: 1,
        b_chunk_index: 1,
        a_text_preview:
          'Residents were evacuated before lava reached the most dangerous areas around nearby roads.',
        b_text_preview:
          'The eruption created dramatic scenes as lava flowed across dark volcanic ground.',
        label: 'partially_aligned',
        match_strength: {
          score: 14,
          level: 'Strong',
          interpretation: 'The paragraphs discuss related impacts.',
        },
        factor_relevance: {
          factor: 'political',
          score: 18,
          level: 'very_strong',
          interpretation: 'Political content is central to this matched pair.',
        },
        stance_discrepancy: {
          score: 10,
          level: 'Moderate',
          interpretation: 'The framing differs in emphasis.',
          disclaimer: 'This is not a factuality score.',
        },
        explanation:
          'The paragraphs discuss related impacts but place emphasis on different details.',
      },
      {
        id: 'pair-3',
        pair_number: 3,
        a_paragraph_index: 2,
        b_paragraph_index: 2,
        a_chunk_index: 2,
        b_chunk_index: 2,
        a_text_preview:
          'Emergency teams built defensive barriers to redirect lava and protect infrastructure.',
        b_text_preview:
          'Civil protection teams monitored fissures and damage risks around local infrastructure.',
        label: 'divergent',
        match_strength: {
          score: 9,
          level: 'Moderate',
          interpretation: 'The paragraphs have limited content overlap.',
        },
        factor_relevance: {
          factor: 'political',
          score: 9,
          level: 'moderate',
          interpretation:
            'Political content is meaningful but not central to this matched pair.',
        },
        stance_discrepancy: {
          score: 9,
          level: 'Moderate',
          interpretation: 'The response details and risk framing differ.',
          disclaimer: 'This is not a factuality score.',
        },
        explanation:
          'The paragraphs focus on different response details and risk framing.',
      },
    ],
  },
}

export const irrelevantComparisonPayload = {
  focus: 'general',
  comparison_id: null,
  relevant: false,
  relevance_score: 0.42,
  cosine_relevance_score: 0.48,
  bm25_relevance_score: 0.28,
  relevance_threshold: 0.6,
  message: 'The articles are not relevant enough for detailed comparison.',
  processing: {
    message: 'The articles are not relevant enough for detailed comparison.',
  },
  errors: [],
  articles: comparisonPayload.articles,
  comparison: null,
}
