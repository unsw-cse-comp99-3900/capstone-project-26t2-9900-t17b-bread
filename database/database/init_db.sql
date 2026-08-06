-- Database Initialisation Script (Sprint 2 Updated)
CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE public.users ALTER COLUMN email DROP NOT NULL;
UPDATE public.users
SET username = 'user_' || id
WHERE username IS NULL OR username = '';
ALTER TABLE public.users ALTER COLUMN username SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON public.users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON public.users(email) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.auth_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES public.users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE public.auth_tokens ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON public.auth_tokens(token);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_expires_at ON public.auth_tokens(expires_at);

CREATE TABLE IF NOT EXISTS public.email_verification_codes (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_email_verification_lookup ON public.email_verification_codes(email, purpose, created_at DESC);

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
    review_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE public.comparison_results ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) NOT NULL DEFAULT 'pending';
ALTER TABLE public.comparison_results ADD COLUMN IF NOT EXISTS admin_notes TEXT;
CREATE INDEX IF NOT EXISTS idx_comparison_articles ON public.comparison_results(article_a_id, article_b_id);

CREATE TABLE IF NOT EXISTS public.history (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES public.users(id) ON DELETE CASCADE,
    comparison_id INT REFERENCES public.comparison_results(id) ON DELETE CASCADE,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE public.history ADD COLUMN IF NOT EXISTS user_id INT REFERENCES public.users(id) ON DELETE CASCADE;
CREATE UNIQUE INDEX IF NOT EXISTS idx_history_user_comparison ON public.history(user_id, comparison_id);

CREATE INDEX IF NOT EXISTS idx_articles_url ON public.articles(url);
CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON public.paragraph_chunks(article_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON public.embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_comparison_results_pairs ON public.comparison_results(article_a_id, article_b_id);
CREATE INDEX IF NOT EXISTS idx_history_user_id ON public.history(user_id);


