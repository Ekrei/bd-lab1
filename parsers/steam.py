"""Парсер магазина Steam (store.steampowered.com)."""

import re
import time
from parsers.base import BaseParser, CatalogItem
import requests

STEAM_APP_LIST = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
STEAM_APP_DETAILS = "https://store.steampowered.com/api/appdetails"
STORE_URL = "https://store.steampowered.com/app/"


def _parse_year(release_date: str | None) -> int | None:
    if not release_date:
        return None
    # "1 Dec, 2015", "Oct 2024", "2012", "Coming soon"
    m = re.search(r"20\d{2}|19\d{2}", release_date)
    return int(m.group()) if m else None


class SteamParser(BaseParser):
    source_name = "steam"

    def fetch_all(self, limit: int = 1000) -> list[CatalogItem]:
        items: list[CatalogItem] = []
        app_list = self._get_app_list()
        for app in app_list:
            if len(items) >= limit:
                break
            item = self._fetch_app_details(app["appid"], app.get("name"))
            if item:
                items.append(item)
            time.sleep(0.25)
        return items

    def _get_app_list(self) -> list[dict]:
        r = requests.get(STEAM_APP_LIST, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("applist", {}).get("apps", [])

    def _fetch_app_details(self, appid: int, fallback_name: str | None) -> CatalogItem | None:
        r = requests.get(
            STEAM_APP_DETAILS,
            params={"appids": appid, "cc": "ru", "l": "english"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        body = data.get(str(appid))
        if not body or not body.get("success") or not body.get("data"):
            return None
        d = body["data"]
        if d.get("type") != "game":
            return None
        desc = d.get("short_description") or d.get("detailed_description") or ""
        if desc and len(desc) > 20:
            from html import unescape
            desc = re.sub(r"<[^>]+>", "", unescape(desc))[:3000]

        price = None
        currency = ""
        po = d.get("price_overview")
        if po:
            price = po.get("final", 0) / 100.0
            currency = po.get("currency", "")
        if d.get("is_free") and price is None:
            price = 0.0
            currency = "USD"

        platforms = []
        pf = d.get("platforms", {})
        if pf.get("windows"):
            platforms.append("Windows")
        if pf.get("mac"):
            platforms.append("macOS")
        if pf.get("linux"):
            platforms.append("Linux")

        genres = [g.get("description", "") for g in (d.get("genres") or []) if g.get("description")]

        return CatalogItem(
            source=self.source_name,
            source_id=str(appid),
            title=d.get("name") or fallback_name or str(appid),
            url=f"{STORE_URL}{appid}/",
            description=desc,
            price=price,
            price_currency=currency or "USD",
            release_year=_parse_year(d.get("release_date")),
            platforms=platforms if platforms else ["PC"],
            developers=d.get("developers") or [],
            publishers=d.get("publishers") or [],
            genres=genres,
            image_url=d.get("header_image") or d.get("background") or "",
            extra={"categories": [c.get("description") for c in (d.get("categories") or [])]},
        )
