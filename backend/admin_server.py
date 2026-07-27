import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from app.db.base import _normalize_url

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

engine = create_engine(_normalize_url(DATABASE_URL))
TABLE_NAME = "comparison_results"

app = FastAPI(title="Admin Portal Shadow Backend Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ReviewUpdateRequest(BaseModel):
    review_status: str
    admin_notes: str | None = None

def parse_and_flatten_matrix(row_dict):
    matrix_data = row_dict.get("alignment_matrix")
    
    if isinstance(matrix_data, str):
        try:
            matrix_data = json.loads(matrix_data)
        except Exception:
            matrix_data = {}

    inner_list = []
    score = None

    if isinstance(matrix_data, dict):
        score = matrix_data.get("similarity_score") or matrix_data.get("overall_similarity")
        inner_list = matrix_data.get("matches") or matrix_data.get("alignments") or matrix_data.get("chunks")
        if not isinstance(inner_list, list):
            lists = [v for v in matrix_data.values() if isinstance(v, list)]
            inner_list = lists[0] if lists else []
    elif isinstance(matrix_data, list):
        inner_list = matrix_data

    if score is None and inner_list:
        match_scores = [m.get("score") for m in inner_list if isinstance(m, dict) and m.get("score") is not None]
        if match_scores:
            score = round(sum(match_scores) / len(match_scores), 2)

    if score is not None:
        row_dict["similarity_score"] = score
        row_dict["similarity"] = score
    else:
        row_dict["similarity_score"] = 0.0
        row_dict["similarity"] = 0.0
        
    row_dict["alignment_matrix"] = inner_list
    return row_dict

@app.get("/api/comparisons", summary="Get all comparison records for the review queue")
def get_comparison_queue():
    query = text(f"SELECT id, 'general' AS focus, review_status, admin_notes, result_json AS alignment_matrix FROM {TABLE_NAME} ORDER BY id DESC")
    try:
        with engine.connect() as connection:
            result = connection.execute(query)
            columns = result.keys()
            data = []
            
            for row in result:
                row_dict = dict(zip(columns, row))
                row_dict = parse_and_flatten_matrix(row_dict)
                data.append(row_dict)
                
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database read error: {str(e)}")

@app.get("/api/comparisons/{task_id}", summary="Get details of a specific comparison task")
def get_comparison_detail(task_id: int):
    query = text(f"SELECT id, 'general' AS focus, review_status, admin_notes, result_json AS alignment_matrix FROM {TABLE_NAME} WHERE id = :id")
    try:
        with engine.connect() as connection:
            result = connection.execute(query, {"id": task_id})
            columns = result.keys()
            row = result.first()
            
            if not row:
                raise HTTPException(status_code=404, detail="Comparison task record not found")
                
            row_dict = dict(zip(columns, row))
            row_dict = parse_and_flatten_matrix(row_dict)
            return row_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database read error: {str(e)}")

@app.post("/api/comparisons/{task_id}/review", summary="Update the review status of a specific task")
def update_review_status(task_id: int, payload: ReviewUpdateRequest):
    query = text(f"""
        UPDATE {TABLE_NAME} 
        SET review_status = :status, admin_notes = :notes 
        WHERE id = :id
    """)
    try:
        with engine.begin() as connection:
            result = connection.execute(query, {
                "status": payload.review_status,
                "notes": payload.admin_notes,
                "id": task_id
            })
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Comparison task record not found")
            return {"status": "success", "message": f"Review status updated for task {task_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database write error: {str(e)}")

@app.delete("/api/comparisons/{task_id}", summary="Delete a specific comparison task record permanently")
def delete_comparison_task(task_id: int):
    query = text(f"DELETE FROM {TABLE_NAME} WHERE id = :id")
    try:
        with engine.begin() as connection:
            result = connection.execute(query, {"id": task_id})
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Comparison task record not found")
            return {"status": "success", "message": f"Task {task_id} successfully deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database delete error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin_server:app", host="127.0.0.1", port=8001, reload=True)