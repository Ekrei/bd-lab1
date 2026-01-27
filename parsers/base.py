"""Базовый класс парсера и общая структура элемента каталога."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CatalogItem:
    """Унифицированная запись об игре для всех источников."""

    source: str  # steam, gog, epic
    source_id: str  # уникальный ID в источнике
    title: str
    url: str
    description: str = ""
    price: float | None = None
    price_currency: str = ""
    # Ключевые атрибуты для дедупликации
    release_year: int | None = None
    platforms: list[str] = field(default_factory=list)
    # Дополнительные характеристики
    developers: list[str] = field(default_factory=list)
    publishers: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    image_url: str = ""
    rating: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "description": self.description[:2000] if self.description else "",
            "price": self.price,
            "price_currency": self.price_currency,
            "release_year": self.release_year,
            "platforms": self.platforms,
            "developers": self.developers,
            "publishers": self.publishers,
            "genres": self.genres,
            "image_url": self.image_url,
            "rating": self.rating,
            "extra": self.extra,
        }


class BaseParser(ABC):
    """Базовый класс парсера."""

    source_name: str = ""

    @abstractmethod
    def fetch_all(self, limit: int = 1000) -> list[CatalogItem]:
        """Собрать не менее limit записей. Возвращает список CatalogItem."""
        ...
