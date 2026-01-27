FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app sql scripts run_app.py ./

# Схема при старте; затем uvicorn (данные загружаются отдельно: load_raw_to_db, deduplicate)
CMD python scripts/run_schema.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
