import json
from typing import Any, List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.engine import Connection

def create_user(
    conn: Connection,
    username: str,
    password_hash: str,
    display_name: str | None = None,
    email: str | None = None,
) -> int:
    query = text("""
        INSERT INTO public.users (username, email, password_hash, display_name)
        VALUES (:username, :email, :password_hash, :display_name)
        RETURNING id;
    """)
    return conn.execute(query, {
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "display_name": display_name,
    }).scalar()


def get_user_by_username(conn: Connection, username: str) -> Optional[Dict[str, Any]]:
    query = text("SELECT * FROM public.users WHERE username = :username;")
    row = conn.execute(query, {"username": username}).mappings().first()
    return dict(row) if row else None


def get_user_by_email(conn: Connection, email: str) -> Optional[Dict[str, Any]]:
    query = text("SELECT * FROM public.users WHERE lower(email) = lower(:email);")
    row = conn.execute(query, {"email": email}).mappings().first()
    return dict(row) if row else None


def get_user(conn: Connection, user_id: int) -> Optional[Dict[str, Any]]:
    query = text("SELECT id, username, email, display_name, created_at FROM public.users WHERE id = :id;")
    row = conn.execute(query, {"id": user_id}).mappings().first()
    return dict(row) if row else None


def update_user_password(conn: Connection, user_id: int, password_hash: str) -> None:
    query = text("UPDATE public.users SET password_hash = :password_hash WHERE id = :id;")
    conn.execute(query, {"id": user_id, "password_hash": password_hash})


def insert_auth_token(conn: Connection, user_id: int, token: str, expires_at=None) -> int:
    query = text("""
        INSERT INTO public.auth_tokens (user_id, token, expires_at)
        VALUES (:user_id, :token, :expires_at)
        RETURNING id;
    """)
    return conn.execute(query, {
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
    }).scalar()

def get_user_by_token(conn: Connection, token: str) -> Optional[Dict[str, Any]]:
    query = text("""
        SELECT u.id, u.username, u.email, u.display_name, u.created_at
        FROM public.auth_tokens t
        JOIN public.users u ON u.id = t.user_id
        WHERE t.token = :token
          AND (t.expires_at IS NULL OR t.expires_at > CURRENT_TIMESTAMP);
    """)
    row = conn.execute(query, {"token": token}).mappings().first()
    return dict(row) if row else None


def delete_auth_token(conn: Connection, token: str) -> None:
    query = text("DELETE FROM public.auth_tokens WHERE token = :token;")
    conn.execute(query, {"token": token})


def delete_expired_auth_tokens(conn: Connection) -> None:
    query = text("DELETE FROM public.auth_tokens WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP;")
    conn.execute(query)


def delete_auth_tokens_for_user(conn: Connection, user_id: int) -> None:
    query = text("DELETE FROM public.auth_tokens WHERE user_id = :user_id;")
    conn.execute(query, {"user_id": user_id})


def insert_email_verification_code(
    conn: Connection,
    email: str,
    code_hash: str,
    purpose: str,
    expires_at,
) -> int:
    query = text("""
        INSERT INTO public.email_verification_codes (email, code_hash, purpose, expires_at)
        VALUES (:email, :code_hash, :purpose, :expires_at)
        RETURNING id;
    """)
    return conn.execute(query, {
        "email": email,
        "code_hash": code_hash,
        "purpose": purpose,
        "expires_at": expires_at,
    }).scalar()


def get_latest_email_verification_code(
    conn: Connection,
    email: str,
    purpose: str,
) -> Optional[Dict[str, Any]]:
    query = text("""
        SELECT *
        FROM public.email_verification_codes
        WHERE lower(email) = lower(:email)
          AND purpose = :purpose
          AND used_at IS NULL
        ORDER BY created_at DESC, id DESC
        LIMIT 1;
    """)
    row = conn.execute(query, {"email": email, "purpose": purpose}).mappings().first()
    return dict(row) if row else None


def get_latest_email_verification_request(
    conn: Connection,
    email: str,
    purpose: str,
) -> Optional[Dict[str, Any]]:
    query = text("""
        SELECT *
        FROM public.email_verification_codes
        WHERE lower(email) = lower(:email)
          AND purpose = :purpose
        ORDER BY created_at DESC, id DESC
        LIMIT 1;
    """)
    row = conn.execute(query, {"email": email, "purpose": purpose}).mappings().first()
    return dict(row) if row else None


def mark_email_verification_code_used(conn: Connection, code_id: int) -> None:
    query = text("""
        UPDATE public.email_verification_codes
        SET used_at = CURRENT_TIMESTAMP
        WHERE id = :id;
    """)
    conn.execute(query, {"id": code_id})


def delete_stale_email_verification_codes(conn: Connection) -> None:
    query = text("""
        DELETE FROM public.email_verification_codes
        WHERE used_at IS NOT NULL
           OR expires_at <= CURRENT_TIMESTAMP;
    """)
    conn.execute(query)

def insert_article(conn: Connection, url: str, title: str, source_domain: str, main_body: str) -> int:
    query = text("""
        INSERT INTO public.articles (url, title, source_domain, main_body)
        VALUES (:url, :title, :source_domain, :main_body)
        ON CONFLICT (url) DO UPDATE SET 
            title = EXCLUDED.title,
            main_body = EXCLUDED.main_body
        RETURNING id;
    """)
    return conn.execute(query, {
        "url": url, "title": title, "source_domain": source_domain, "main_body": main_body
    }).scalar()

def get_article_by_url(conn: Connection, url: str) -> Optional[Dict[str, Any]]:
    query = text("SELECT * FROM public.articles WHERE url = :url;")
    row = conn.execute(query, {"url": url}).mappings().first()
    return dict(row) if row else None

def get_article(conn: Connection, article_id: int) -> Optional[Dict[str, Any]]:
    query = text("SELECT * FROM public.articles WHERE id = :id;")
    row = conn.execute(query, {"id": article_id}).mappings().first()
    return dict(row) if row else None

def insert_chunk(conn: Connection, article_id: int, paragraph_index: int, text_content: str) -> int:
    query = text("""
        INSERT INTO public.paragraph_chunks (article_id, paragraph_index, text_content)
        VALUES (:article_id, :paragraph_index, :text_content)
        RETURNING id;
    """)
    return conn.execute(query, {
        "article_id": article_id, "paragraph_index": paragraph_index, "text_content": text_content
    }).scalar()

def get_chunks(conn: Connection, article_id: int) -> List[Dict[str, Any]]:
    query = text("SELECT * FROM public.paragraph_chunks WHERE article_id = :article_id ORDER BY paragraph_index ASC;")
    return [dict(r) for r in conn.execute(query, {"article_id": article_id}).mappings().all()]

def insert_embedding(conn: Connection, chunk_id: int, vector: List[float], model_name: str) -> int:
    query = text("""
        INSERT INTO public.embeddings (chunk_id, vector, model_name)
        VALUES (:chunk_id, :vector, :model_name)
        RETURNING id;
    """)
    return conn.execute(query, {
        "chunk_id": chunk_id, "vector": vector, "model_name": model_name
    }).scalar()

def get_embedding(conn: Connection, chunk_id: int) -> Optional[Dict[str, Any]]:
    query = text("SELECT * FROM public.embeddings WHERE chunk_id = :chunk_id;")
    row = conn.execute(query, {"chunk_id": chunk_id}).mappings().first()
    return dict(row) if row else None

def get_embeddings_for_article(conn: Connection, article_id: int) -> List[Dict[str, Any]]:
    query = text("""
        SELECT e.* FROM public.embeddings e
        JOIN public.paragraph_chunks c ON e.chunk_id = c.id
        WHERE c.article_id = :article_id
        ORDER BY c.paragraph_index ASC;
    """)
    return [dict(r) for r in conn.execute(query, {"article_id": article_id}).mappings().all()]

def insert_comparison_result(conn: Connection, article_a_id: int, article_b_id: int, result_json: Any) -> int:
    if not isinstance(result_json, str):
        result_json = json.dumps(result_json)
    query = text("""
        INSERT INTO public.comparison_results (article_a_id, article_b_id, result_json)
        VALUES (:article_a_id, :article_b_id, :result_json)
        RETURNING id;
    """)
    return conn.execute(query, {
        "article_a_id": article_a_id, "article_b_id": article_b_id, "result_json": result_json
    }).scalar()

def get_comparison_result(conn: Connection, comparison_id: int) -> Optional[Dict[str, Any]]:
    query = text("SELECT * FROM public.comparison_results WHERE id = :id;")
    row = conn.execute(query, {"id": comparison_id}).mappings().first()
    return dict(row) if row else None

def insert_history_entry(conn: Connection, comparison_id: int, user_id: int | None = None) -> int:
    query = text("""
        INSERT INTO public.history (comparison_id, user_id)
        VALUES (:comparison_id, :user_id)
        ON CONFLICT (user_id, comparison_id) DO UPDATE SET saved_at = CURRENT_TIMESTAMP
        RETURNING id;
    """)
    return conn.execute(query, {"comparison_id": comparison_id, "user_id": user_id}).scalar()

def get_history(conn: Connection, user_id: int | None = None) -> List[Dict[str, Any]]:
    if user_id is None:
        query = text("""
            SELECT h.id as history_id, h.saved_at, r.*
            FROM public.history h
            JOIN public.comparison_results r ON h.comparison_id = r.id
            WHERE h.user_id IS NULL
            ORDER BY h.saved_at DESC;
        """)
        return [dict(r) for r in conn.execute(query).mappings().all()]

    query = text("""
        SELECT h.id as history_id, h.saved_at, r.*
        FROM public.history h
        JOIN public.comparison_results r ON h.comparison_id = r.id
        WHERE h.user_id = :user_id
        ORDER BY h.saved_at DESC;
    """)
    return [dict(r) for r in conn.execute(query, {"user_id": user_id}).mappings().all()]

def delete_history_item(conn: Connection, history_id: int, user_id: int | None = None) -> None:
    if user_id is None:
        query = text("DELETE FROM public.history WHERE id = :id AND user_id IS NULL;")
        conn.execute(query, {"id": history_id})
        return
    query = text("DELETE FROM public.history WHERE id = :id AND user_id = :user_id;")
    conn.execute(query, {"id": history_id, "user_id": user_id})

def clear_history(conn: Connection, user_id: int | None = None) -> None:
    if user_id is None:
        query = text("DELETE FROM public.history WHERE user_id IS NULL;")
        conn.execute(query)
        return
    query = text("DELETE FROM public.history WHERE user_id = :user_id;")
    conn.execute(query, {"user_id": user_id})

def insert_history(conn: Connection, comparison_id: int, user_id: int | None = None) -> int:
    query = text("""
        INSERT INTO public.history (comparison_id, user_id)
        VALUES (:comparison_id, :user_id)
        ON CONFLICT (user_id, comparison_id) DO UPDATE SET saved_at = CURRENT_TIMESTAMP
        RETURNING id;
    """)
    return conn.execute(query, {"comparison_id": comparison_id, "user_id": user_id}).scalar()
