"""
Загрузка сырых JSON из data/raw/ в БД (products, offers, attributes).
Перед запуском: создана БД и выполнена sql/001_schema.sql.
Переменная окружения: DATABASE_URL (по умолчанию postgresql://localhost:5432/games_db).
"""

import json
import os
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_DATABASE_URL = "postgresql://localhost:5432/games_db"


def _conn():
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return psycopg2.connect(url)


def _attrs(rec: dict, key: str) -> list[str]:
    v = rec.get(key)
    if isinstance(v, list):
        return [str(x).strip() for x in v if x is not None and str(x).strip()]
    if v is not None and str(v).strip():
        return [str(v).strip()]
    return []


def load_file(path: Path, source: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    for r in data:
        r["_source"] = source
    return data


def run():
    conn = _conn()
    conn.autocommit = False
    cur = conn.cursor()

    files = [
        (RAW_DIR / "steam_raw.json", "steam"),
        (RAW_DIR / "gog_raw.json", "gog"),
        (RAW_DIR / "epic_raw.json", "epic"),
    ]

    for path, source in files:
        if not path.exists():
            print(f"Пропуск (нет файла): {path}")
            continue
        print(f"Загрузка {source} из {path.name}...")
        rows = load_file(path, source)
        parsed_at = datetime.utcnow()

        for rec in rows:
            title = (rec.get("title") or "").strip()
            if not title:
                continue
            sid = str(rec.get("source_id") or "")
            cur.execute("SELECT 1 FROM offers WHERE website_name=%s AND source_id=%s", (source, sid))
            if cur.fetchone():
                continue

            desc = (rec.get("description") or "")[:10000]
            img = (rec.get("image_url") or "")[:2048]
            year = rec.get("release_year")
            if year is not None:
                try:
                    year = int(year)
                except (TypeError, ValueError):
                    year = None

            cur.execute(
                """INSERT INTO products (canonical_name, description, image_url, release_year)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (title, desc or None, img or None, year),
            )
            (pid,) = cur.fetchone()

            url = (rec.get("url") or "").strip()
            if not url:
                url = "#"
            price = rec.get("price")
            if price is not None:
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    price = None
            currency = (rec.get("price_currency") or "")[:10]

            cur.execute(
                """INSERT INTO offers (product_id, website_name, source_id, price, price_currency, url, date_parsed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (pid, source, sid, price, currency or None, url, parsed_at),
            )

            # Атрибуты: platform, genre, developer, publisher
            attrs = []
            for p in _attrs(rec, "platforms"):
                attrs.append((pid, "platform", p))
            for g in _attrs(rec, "genres"):
                attrs.append((pid, "genre", g))
            for d in _attrs(rec, "developers"):
                attrs.append((pid, "developer", d))
            for p in _attrs(rec, "publishers"):
                attrs.append((pid, "publisher", p))
            if rec.get("rating") is not None:
                attrs.append((pid, "rating", str(rec.get("rating"))))

            if attrs:
                execute_values(
                    cur,
                    "INSERT INTO attributes (product_id, attribute_name, attribute_value) VALUES %s",
                    attrs,
                )

        print(f"  Загружено записей: {len(rows)}")

    conn.commit()
    cur.close()
    conn.close()
    print("Готово.")


if __name__ == "__main__":
    run()
