-- Схема единой БД для интеграции данных Steam, GOG, Epic Games
-- products: уникальные игры после дедупликации
-- offers: предложения с каждого сайта (связь с product до/после дедупликации)
-- attributes: дополнительные характеристики (жанр, платформа, разработчик и т.п.)

-- Удаление при пересоздании (для чистого старта)
-- DROP TABLE IF EXISTS attributes;
-- DROP TABLE IF EXISTS offers;
-- DROP TABLE IF EXISTS products;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    description TEXT,
    image_url TEXT,
    release_year INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offers (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    website_name TEXT NOT NULL,
    source_id TEXT NOT NULL,
    price DECIMAL(12,2),
    price_currency VARCHAR(10),
    url TEXT NOT NULL,
    date_parsed TIMESTAMPTZ DEFAULT now(),
    UNIQUE(website_name, source_id)
);

CREATE TABLE IF NOT EXISTS attributes (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL,
    attribute_value TEXT NOT NULL
);

-- Индексы для поиска и дедупликации
CREATE INDEX IF NOT EXISTS idx_products_canonical_name ON products(canonical_name);
CREATE INDEX IF NOT EXISTS idx_products_release_year ON products(release_year);
CREATE INDEX IF NOT EXISTS idx_products_name_year ON products(canonical_name, release_year);

CREATE INDEX IF NOT EXISTS idx_offers_product_id ON offers(product_id);
CREATE INDEX IF NOT EXISTS idx_offers_website ON offers(website_name);

CREATE INDEX IF NOT EXISTS idx_attributes_product_id ON attributes(product_id);
CREATE INDEX IF NOT EXISTS idx_attributes_name ON attributes(product_id, attribute_name);

-- Полнотекстовый поиск по products (опционально)
-- CREATE INDEX IF NOT EXISTS idx_products_fts ON products USING GIN(to_tsvector('simple', coalesce(canonical_name,'') || ' ' || coalesce(description,'')));
