import os
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_URL = "postgresql://localhost:5432/games_db"


def get_conn():
    return psycopg2.connect(
        os.environ.get("DATABASE_URL", DEFAULT_URL),
        cursor_factory=RealDictCursor,
    )
