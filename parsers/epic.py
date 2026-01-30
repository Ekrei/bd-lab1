"""Парсер Epic Games Store. GraphQL (www.epicgames.com/graphql) с запасным вариантом Playwright."""

import json
import re
from parsers.base import BaseParser, CatalogItem
import requests

EPIC_GRAPHQL = "https://www.epicgames.com/graphql"
EPIC_STORE_BROWSE = "https://store.epicgames.com/en-US/browse"
STORE_PREFIX = "https://store.epicgames.com/en-US/p/"

# Persisted query (фиксированный набор полей на стороне Epic)
SEARCH_STORE_OP = "searchStoreQuery"
SEARCH_STORE_HASH = "6e7c4dd0177150eb9a47d624be221929582df8648e7ec271c821838ff4ee148e"


def _parse_year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    m = re.search(r"20\d{2}|19\d{2}", str(date_str))
    return int(m.group()) if m else None


class EpicParser(BaseParser):
    source_name = "epic"

    def fetch_all(self, limit: int = 1000) -> list[CatalogItem]:
        # items = self._fetch_via_graphql(limit)
        items = []
        if len(items) >= limit:
            return items[:limit]
        # Добираем или подменяем через Playwright при необходимости
        extra = self._fetch_via_playwright(limit - len(items))
        items.extend(extra)
        return items[:limit]

    def _fetch_via_graphql(self, limit: int) -> list[CatalogItem]:
        items: list[CatalogItem] = []
        start = 0
        count = 100
        while len(items) < limit:
            r = requests.get(
                EPIC_GRAPHQL,
                params={
                    "operationName": SEARCH_STORE_OP,
                    "variables": _json_vars(start=start, count=count, country="US"),
                    "extensions": _json_extensions(SEARCH_STORE_HASH),
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            if r.status_code != 200:
                break
            data = r.json()
            els = _elements_from_response(data)
            if not els:
                break
            for el in els:
                item = _element_to_item(el, self.source_name)
                if item and _is_game(el):
                    items.append(item)
                if len(items) >= limit:
                    break
            start += count
            if start >= _total_from_response(data):
                break
        return items

    def _fetch_via_playwright(self, need: int) -> list[CatalogItem]:
        if need <= 0:
            return []
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []
        items: list[CatalogItem] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            page.goto(EPIC_STORE_BROWSE, wait_until="domcontentloaded")
            seen = set()
            for _ in range(50):
                if len(items) >= need:
                    break
                cards = page.query_selector_all('a')
                print(f"Found {len(cards)} cards")
                for card in cards:
                    if len(items) >= need:
                        break
                    href = card.get_attribute("href") or ""
                    print(f"href: {href}")
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    slug = href.split("/p/")[-1].strip("/").split("?")[0]
                    print(f"slug: {slug}")
                    if not slug or len(slug) < 2:
                        continue
                    title_el = card.query_selector("span, [class*='title'], [class*='Title']")
                    title = (title_el.inner_text() if title_el else "").strip() or slug
                    print(f"title: {title}")
                    img = card.query_selector("img[src]")
                    img_url = (img.get_attribute("src") or "") if img else ""
                    url = f"{STORE_PREFIX}{slug}" if not href.startswith("http") else href
                    if not url.startswith("http"):
                        url = f"{STORE_PREFIX}{slug}"
                    items.append(
                        CatalogItem(
                            source=self.source_name,
                            source_id=slug,
                            title=title,
                            url=url,
                            description="",
                            price=None,
                            price_currency="",
                            release_year=None,
                            platforms=["PC"],
                            developers=[],
                            publishers=[],
                            genres=[],
                            image_url=img_url,
                            extra={"slug": slug},
                        )
                    )
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
            browser.close()
        return items


def _json_vars(start: int, count: int, country: str) -> str:
    return json.dumps({"start": start, "count": count, "country": country})


def _json_extensions(hash: str) -> str:
    return json.dumps({"persistedQuery": {"version": 1, "sha256Hash": hash}})


def _elements_from_response(data: dict) -> list[dict]:
    try:
        c = data.get("data", {}).get("Catalog", {}) or {}
        sr = c.get("searchStore") or {}
        return sr.get("elements") or []
    except Exception:
        return []


def _total_from_response(data: dict) -> int:
    try:
        sr = (data.get("data", {}).get("Catalog", {}) or {}).get("searchStore") or {}
        p = sr.get("paging") or {}
        return int(p.get("total") or 0)
    except Exception:
        return 0


def _is_game(el: dict) -> bool:
    """Отфильтровать не-игры (DLC, add-ons и т.п.) по возможности."""
    cat = (el.get("catalogNs") or {}).get("mappings") or []
    for m in cat:
        if isinstance(m, dict):
            page_slug = (m.get("pageSlug") or "").lower()
            if "add-on" in page_slug or "dlc" in page_slug or "edition" in page_slug:
                return False
    categories = (el.get("categories") or []) if isinstance(el.get("categories"), list) else []
    for c in categories:
        if isinstance(c, dict) and (c.get("path") or "").lower().startswith("add-ons"):
            return False
    # По умолчанию считаем игрой, если есть title
    return bool(el.get("title"))


def _element_to_item(el: dict, source: str) -> CatalogItem | None:
    title = (el.get("title") or "").strip()
    if not title:
        return None
    pid = el.get("id") or el.get("productSlug") or ""
    ms = ((el.get("catalogNs") or {}).get("mappings")) or []
    slug = el.get("productSlug") or (ms[0].get("pageSlug") if ms and isinstance(ms[0], dict) else None) or ""
    slug = slug or str(pid) if pid else ""
    url = f"{STORE_PREFIX}{slug}" if slug else ""

    desc = (el.get("description") or "").strip()[:3000]

    price = None
    currency = "USD"
    price_info = el.get("price") or {}
    if isinstance(price_info, dict):
        total = price_info.get("totalPrice", {}) or {}
        if isinstance(total, dict):
            try:
                price = int(total.get("originalPrice") or 0) / 100.0
                if price == 0 and (total.get("discountPrice") is not None):
                    price = int(total.get("discountPrice") or 0) / 100.0
            except (TypeError, ValueError):
                pass
            currency = (total.get("currencyCode") or "USD") or "USD"

    key_images = el.get("keyImages") or []
    img = ""
    for k in key_images:
        if isinstance(k, dict) and (k.get("type") == "OfferImageWide" or k.get("type") == "Thumbnail"):
            img = k.get("url") or img
    if not img and key_images and isinstance(key_images[0], dict):
        img = key_images[0].get("url") or ""

    release = el.get("releaseInfo") or []
    year = None
    if isinstance(release, list):
        for r in release:
            if isinstance(r, dict) and r.get("date"):
                year = _parse_year(r.get("date"))
                break
    if year is None:
        year = _parse_year(el.get("effectiveDate") or el.get("creationDate"))

    return CatalogItem(
        source=source,
        source_id=str(pid) if pid else slug,
        title=title,
        url=url,
        description=desc,
        price=price,
        price_currency=currency,
        release_year=year,
        platforms=["PC"],
        developers=[],
        publishers=[],
        genres=[],
        image_url=img or "",
        extra={},
    )
