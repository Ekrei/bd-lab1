"""Выполнение sql/001_schema.sql. Используется при старте в Docker и при ручном применении схемы."""
import os
from pathlib import Path

import psycopg2

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "sql" / "001_schema.sql"
DEFAULT_URL = "postgresql://localhost:5432/games_db"


def run():
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    for stmt in content.split(";"):
        s = stmt.strip()
        if not s or s.startswith("--"):
            continue
        try:
            cur.execute(s)
        except Exception as e:
            print(f"Предупреждение при выполнении: {e}")
    conn.commit()
    cur.close()
    conn.close()
    print("Схема применена.")


if __name__ == "__main__":
    run()
