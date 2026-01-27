# Быстрая проверка парсеров (малый лимит)
from parsers.gog import GOGParser
from parsers.steam import SteamParser

def test_gog():
    p = GOGParser()
    items = p.fetch_all(limit=5)
    print("GOG:", len(items), items[0].title if items else "none")
    return len(items) > 0

def test_steam():
    p = SteamParser()
    items = p.fetch_all(limit=3)
    print("Steam:", len(items), items[0].title if items else "none")
    return len(items) > 0

if __name__ == "__main__":
    test_gog()
    test_steam()
