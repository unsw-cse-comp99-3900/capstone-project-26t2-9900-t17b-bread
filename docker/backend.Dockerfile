FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/opt/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/opt/sentence-transformers
ENV HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); CrossEncoder('cross-encoder/nli-deberta-v3-base', activation_fn=None)"

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/admin_server.py ./
COPY backend/pytest.ini ./
COPY database/database/init_db.sql /database/database/init_db.sql

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
