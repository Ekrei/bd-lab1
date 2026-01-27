"""
FastAPI: GET /api/search?q=..., GET /api/product/<id>, GET / (главная), GET /product/<id> (страница товара).
"""

import os
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.db import get_conn

app = FastAPI(title="Каталог игр")

BASE = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

if os.path.isdir(os.path.join(BASE, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")


def _search(q: str, limit: int = 50) -> list[dict]:
    if not (q or "").strip():
        return []
    conn = get_conn()
    cur = conn.cursor()
    pat = f"%{(q or '').strip()}%"
    cur.execute("""
        SELECT p.id, p.canonical_name, p.image_url, p.release_year,
               (SELECT MIN(o.price) FROM offers o WHERE o.product_id = p.id AND o.price IS NOT NULL) AS min_price,
               (SELECT o2.price_currency FROM offers o2 WHERE o2.product_id = p.id AND o2.price IS NOT NULL
                ORDER BY o2.price ASC LIMIT 1) AS min_currency
        FROM products p
        WHERE p.canonical_name ILIKE %s OR (p.description IS NOT NULL AND p.description ILIKE %s)
        ORDER BY p.canonical_name
        LIMIT %s
    """, (pat, pat, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def _product(product_id: int) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, canonical_name, description, image_url, release_year FROM products WHERE id = %s", (product_id,))
    p = cur.fetchone()
    if not p:
        cur.close()
        conn.close()
        return None
    cur.execute(
        "SELECT website_name, source_id, price, price_currency, url, date_parsed FROM offers WHERE product_id = %s ORDER BY price ASC NULLS LAST",
        (product_id,),
    )
    offers = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT attribute_name, attribute_value FROM attributes WHERE product_id = %s ORDER BY attribute_name, attribute_value", (product_id,))
    attrs = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"product": dict(p), "offers": offers, "attributes": attrs}


@app.get("/api/search", response_model=dict)
def api_search(q: str = Query("", min_length=0)):
    return {"results": _search(q)}


@app.get("/api/product/{product_id}", response_model=dict)
def api_product(product_id: int):
    data = _product(product_id)
    if not data:
        raise HTTPException(status_code=404, detail="Product not found")
    return data


@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = Query("", min_length=0)):
    results = _search(q) if (q or "").strip() else []
    return templates.TemplateResponse("index.html", {"request": request, "q": q or "", "results": results})


@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_page(request: Request, product_id: int):
    data = _product(product_id)
    if not data:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse("product.html", {"request": request, **data})
