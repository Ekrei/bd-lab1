# Интеграционная БД видеоигр (Steam, GOG, Epic Games)

Курсовой проект: сбор данных с трёх площадок, единая БД, дедупликация, веб-интерфейс.

> **Как устроен проект:** связи между файлами, порядок работы и обоснование выбора технологий — в [ARCHITECTURE.md](ARCHITECTURE.md).

## Требования

- Python 3.10+
- PostgreSQL (для этапов 2–5)

## Установка

```bash
pip install -r requirements.txt
playwright install chromium   # для парсера Epic (запасной вариант)
```

## Этап 1: Парсинг

Сбор не менее 1000 записей с каждого источника в `data/raw/`:

```bash
python run_parsers.py
```

- **Steam** — до 15–40 мин (много запросов к API, пауза 0.25 с).
- **GOG** — несколько минут (каталог по 100 позиций на страницу).
- **Epic** — GraphQL; при нехватке данных — Playwright (нужен `playwright install chromium`).

Результат: `data/raw/steam_raw.json`, `data/raw/gog_raw.json`, `data/raw/epic_raw.json`.

Быстрая проверка (лимит 3–5): `python test_parsers.py`.

---

## Этап 2: База данных

1. Создать БД: `createdb games_db` (или через pgAdmin).
2. Применить схему:
   ```bash
   psql -d games_db -f sql/001_schema.sql
   ```
   либо: `psql $DATABASE_URL -f sql/001_schema.sql`
3. Загрузить сырые данные из `data/raw/`:
   ```bash
   # при необходимости: set DATABASE_URL=postgresql://user:pass@localhost:5432/games_db
   python scripts/load_raw_to_db.py
   ```

Таблицы: **products** (каноническое название, описание, год, картинка), **offers** (сайт, source_id, цена, url), **attributes** (platform, genre, developer, publisher и др.).

---

## Этап 3: Дедупликация

Критерии: **название** (нормализация + fuzzy, rapidfuzz ≥88%), **год выхода**, **пересечение платформ**. Повторный запуск после загрузки:

```bash
python scripts/deduplicate.py
```

---

## Этап 4: Веб-приложение

- **API:** `GET /api/search?q=...`, `GET /api/product/<id>`
- **Страницы:** `/` (поиск), `/product/<id>`

Запуск (из корня проекта, нужна переменная `DATABASE_URL`):

```bash
python run_app.py
# или: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Откройте http://localhost:8000

---

## Этап 5: Docker

Сборка и запуск (PostgreSQL + веб-приложение):

```bash
docker-compose up -d
```

При первом старте применяется `sql/001_schema.sql`. Данные в БД по умолчанию пустые. Чтобы их загрузить:

1. Соберите сырые данные на хосте: `python run_parsers.py` (появится `data/raw/`).
2. Загрузите в БД и выполните дедупликацию:

```bash
docker-compose run --rm -v "%cd%/data:/app/data" -e DATABASE_URL=postgresql://postgres:postgres@postgres:5432/games_db app python scripts/load_raw_to_db.py
docker-compose run --rm -e DATABASE_URL=postgresql://postgres:postgres@postgres:5432/games_db app python scripts/deduplicate.py
```

На Linux/macOS для монтирования тома используйте `$(pwd)/data:/app/data`.

После этого откройте http://localhost:8000
