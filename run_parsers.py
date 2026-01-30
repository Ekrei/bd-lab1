"""
Запуск всех парсеров и сохранение сырых данных в data/raw/.
Не менее 1000 записей с каждого источника (Steam, GOG, Epic).
"""

import json
from pathlib import Path

from parsers.steam import SteamParser
from parsers.gog import GOGParser
from parsers.epic import EpicParser

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"
LIMIT = 1100  # с запасом для отсева при дедупликации


def run():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for name, parser_cls in [
        # ("steam", SteamParser),
        ("gog", GOGParser),
        ("epic", EpicParser),
    ]:
        print(f"[{name}] Запуск парсера (лимит {LIMIT})...")
        parser = parser_cls()
        try:
            items = parser.fetch_all(limit=LIMIT)
            out = [x.to_dict() for x in items]
            path = RAW_DIR / f"{name}_raw.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"[{name}] Собрано {len(out)} записей, сохранено в {path}")
        except Exception as e:
            print(f"[{name}] Ошибка: {e}")
            raise

    print("Готово.")


if __name__ == "__main__":
    run()
