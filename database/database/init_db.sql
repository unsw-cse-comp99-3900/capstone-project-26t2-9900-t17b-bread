-- Database Initialisation Script (Sprint 2 Updated)
CREATE TABLE IF NOT EXISTS public.articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    source_domain VARCHAR(255),
    main_body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_articles_url ON public.articles(url);

CREATE TABLE IF NOT EXISTS public.paragraph_chunks (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES public.articles(id) ON DELETE CASCADE,
    paragraph_index INT NOT NULL,
    text_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON public.paragraph_chunks(article_id);

CREATE TABLE IF NOT EXISTS public.embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INT REFERENCES public.paragraph_chunks(id) ON DELETE CASCADE,
    vector FLOAT8[] NOT NULL,
    model_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON public.embeddings(chunk_id);

CREATE TABLE IF NOT EXISTS public.comparison_results (
    id SERIAL PRIMARY KEY,
    article_a_id INT REFERENCES public.articles(id),
    article_b_id INT REFERENCES public.articles(id),
    result_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_comparison_articles ON public.comparison_results(article_a_id, article_b_id);

CREATE TABLE IF NOT EXISTS public.history (
    id SERIAL PRIMARY KEY,
    comparison_id INT REFERENCES public.comparison_results(id) ON DELETE CASCADE,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_articles_url ON public.articles(url);
CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON public.paragraph_chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON public.embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_comparison_results_pairs ON public.comparison_results(article_a_id, article_b_id);