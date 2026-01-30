"""Парсер магазина GOG.com (catalog.gog.com)."""

from parsers.base import BaseParser, CatalogItem
import requests

GOG_CATALOG = "https://catalog.gog.com/v1/catalog"
GOG_STORE = "https://www.gog.com"
PRODUCT_TYPE_GAME = "game"


def _os_to_platforms(op_sys: list[str] | None) -> list[str]:
    if not op_sys:
        return ["PC"]
    platforms = []
    for os_name in op_sys:
        os_lower = os_name.lower()
        if "win" in os_lower:
            platforms.append("Windows")
        elif "mac" in os_lower or "osx" in os_lower:
            platforms.append("macOS")
        elif "linux" in os_lower:
            platforms.append("Linux")
    return platforms if platforms else ["PC"]


def _parse_year(release_date: str | None) -> int | None:
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


class GOGParser(BaseParser):
    source_name = "gog"

    def fetch_all(self, limit: int = 1000) -> list[CatalogItem]:
        items: list[CatalogItem] = []
        page = 1
        while len(items) < limit:
            chunk = self._fetch_page(page)
            if not chunk:
                break
            for p in chunk:
                if p.get("productType") != PRODUCT_TYPE_GAME:
                    continue
                item = self._to_catalog_item(p)
                if item:
                    items.append(item)
                if len(items) >= limit:
                    break
            page += 1
        return items[:limit]

    def _fetch_page(self, page: int) -> list[dict]:
        r = requests.get(
            GOG_CATALOG,
            params={
                "locale": "en-US",
                "marketCode": "en",
                "page": page,
                "perPage": 100,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("products", [])

    def _to_catalog_item(self, p: dict) -> CatalogItem | None:
        pid = p.get("id")
        title = p.get("title")
        if not pid or not title:
            return None
        slug = p.get("slug", "")
        store_link = p.get("storeLink") or f"/en/game/{slug}" if slug else ""
        url = f"{GOG_STORE}{store_link}" if store_link.startswith("/") else store_link or f"{GOG_STORE}/en/game/{slug}"

        price_info = p.get("price", {}) or {}
        final = price_info.get("final")
        price = None
        if final is not None:
            if isinstance(final, str):
                try:
                    price = float(final.replace("$", "").replace("€", "").replace(",", "."))
                except ValueError:
                    price = None
            else:
                price = float(final) / 100.0
        currency = (price_info.get("finalMoney") or {}).get("currency", "USD")

        release = p.get("releaseDate") or p.get("storeReleaseDate") or ""

        return CatalogItem(
            source=self.source_name,
            source_id=str(pid),
            title=title,
            url=url,
            description="",
            price=price,
            price_currency=currency,
            release_year=_parse_year(str(release)[:10] if release else None),
            platforms=_os_to_platforms(p.get("operatingSystems")),
            developers=p.get("developers") or [],
            publishers=p.get("publishers") or [],
            genres=[g.get("name", "") for g in (p.get("genres") or []) if g.get("name")],
            image_url=p.get("coverHorizontal") or p.get("coverVertical") or p.get("logo") or "",
            rating=p.get("reviewsRating"),
            extra={
                "reviewsCount": p.get("reviewsCount"),
                "tags": p.get("tags") or [],
            },
        )
