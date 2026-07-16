-- Database Initialisation Script (Sprint 1)
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    source_domain VARCHAR(255),
    main_body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(255) NOT NULL,
    article_a_url TEXT NOT NULL,
    article_b_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token);

CREATE TABLE IF NOT EXISTS article_embeddings (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES articles(id) ON DELETE CASCADE,
    embedding REAL[] NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_embeddings_article_id ON article_embeddings(article_id);

CREATE TABLE IF NOT EXISTS public.embeddings_collection (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES public.articles(id) ON DELETE CASCADE,
    sentence_index INT NOT NULL,
    text_content TEXT NOT NULL,
    embedding FLOAT8[] NOT NULL
);

CREATE TABLE IF NOT EXISTS public.comparison_results (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    article_a_id INT REFERENCES public.articles(id),
    article_b_id INT REFERENCES public.articles(id),
    alignment_matrix JSONB NOT NULL,
    similarity_score NUMERIC(4, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);