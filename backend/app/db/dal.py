import json
from typing import Any, List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.engine import Connection

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

def insert_history_entry(conn: Connection, comparison_id: int) -> int:
    query = text("""
        INSERT INTO public.history (comparison_id)
        VALUES (:comparison_id)
        RETURNING id;
    """)
    return conn.execute(query, {"comparison_id": comparison_id}).scalar()

def get_history(conn: Connection) -> List[Dict[str, Any]]:
    query = text("""
        SELECT h.id as history_id, h.saved_at, r.* 
        FROM public.history h
        JOIN public.comparison_results r ON h.comparison_id = r.id
        ORDER BY h.saved_at DESC;
    """)
    return [dict(r) for r in conn.execute(query).mappings().all()]

def delete_history_item(conn: Connection, history_id: int) -> None:
    query = text("DELETE FROM public.history WHERE id = :id;")
    conn.execute(query, {"id": history_id})

def clear_history(conn: Connection) -> None:
    query = text("TRUNCATE TABLE public.history RESTART IDENTITY CASCADE;")
    conn.execute(query)

def insert_history(conn: Connection, comparison_id: int) -> None:
    query = text("""
        INSERT INTO public.history (comparison_id)
        VALUES (:comparison_id)
    """)
    conn.execute(query, {"comparison_id": comparison_id})