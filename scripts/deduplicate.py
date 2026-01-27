"""
Дедупликация products по критериям: название (нормализация + fuzzy), год выхода, пересечение платформ.
Склеивание: offers и attributes перепривязываются к продукту-«победителю», дубли продуктов удаляются.
"""

import os
import re
from collections import defaultdict

import psycopg2
from rapidfuzz import fuzz

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_DATABASE_URL = "postgresql://localhost:5432/games_db"
FUZZY_THRESHOLD = 88  # порог similarity для нечёткого совпадения названия


def _conn():
    return psycopg2.connect(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _platforms_overlap(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return True
    return bool(a & b)


def _get_platforms(cur) -> dict[int, set[str]]:
    cur.execute("SELECT product_id, attribute_value FROM attributes WHERE attribute_name='platform'")
    out: dict[int, set[str]] = defaultdict(set)
    for pid, v in cur.fetchall():
        if v and str(v).strip():
            out[pid].add(str(v).strip().lower())
    return dict(out)


def _get_offer_counts(cur) -> dict[int, int]:
    cur.execute("SELECT product_id, COUNT(*) FROM offers GROUP BY product_id")
    return dict(cur.fetchall())


def _find_clusters(products: list[tuple[int, str, int | None]], platforms: dict[int, set[str]]) -> list[list[int]]:
    """Кластеры по (год + пересечение платформ + название: точное или fuzzy). Бакеты по году для ускорения."""
    year_key = lambda y: y if y is not None else "NULL"
    buckets: dict[object, list[tuple[int, str, int | None]]] = defaultdict(list)
    for p in products:
        buckets[year_key(p[2])].append(p)

    all_clusters: list[list[int]] = []
    for _y, group in buckets.items():
        if len(group) <= 1:
            continue
        parent: dict[int, int] = {}

        def find(x: int) -> int:
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(a: int, b: int) -> None:
            parent[find(a)] = find(b)

        for i, (idi, namei, _) in enumerate(group):
            for j, (idj, namej, _) in enumerate(group):
                if i >= j:
                    continue
                if not _platforms_overlap(platforms.get(idi, set()), platforms.get(idj, set())):
                    continue
                ni, nj = _norm(namei), _norm(namej)
                if ni == nj or fuzz.ratio(ni, nj) >= FUZZY_THRESHOLD:
                    union(idi, idj)

        comp: dict[int, list[int]] = defaultdict(list)
        for p in group:
            comp[find(p[0])].append(p[0])
        for g in comp.values():
            if len(g) > 1:
                all_clusters.append(g)

    return all_clusters


def run():
    conn = _conn()
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT id, canonical_name, release_year FROM products")
    products = [(r[0], r[1] or "", r[2]) for r in cur.fetchall()]
    platforms = _get_platforms(cur)
    offer_counts = _get_offer_counts(cur)

    clusters = _find_clusters(products, platforms)
    print(f"Найдено кластеров дубликатов: {len(clusters)}")

    merged = 0
    for ids in clusters:
        # Победитель: больше всего offers, при равенстве — меньший id
        survivor = max(ids, key=lambda x: (offer_counts.get(x, 0), -x))
        others = [i for i in ids if i != survivor]
        for oid in others:
            cur.execute("UPDATE offers SET product_id = %s WHERE product_id = %s", (survivor, oid))
            cur.execute(
                """INSERT INTO attributes (product_id, attribute_name, attribute_value)
                   SELECT %s, attribute_name, attribute_value FROM attributes WHERE product_id = %s
                   AND NOT EXISTS (
                     SELECT 1 FROM attributes a2
                     WHERE a2.product_id = %s AND a2.attribute_name = attributes.attribute_name
                       AND a2.attribute_value = attributes.attribute_value
                   )""",
                (survivor, oid, survivor),
            )
            cur.execute("DELETE FROM attributes WHERE product_id = %s", (oid,))
            cur.execute("DELETE FROM products WHERE id = %s", (oid,))
            merged += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Объединено продуктов (удалено дубликатов): {merged}")


if __name__ == "__main__":
    run()
