"""Конфигурация бота: всё читается из .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

from dotenv import load_dotenv

VALID_TYPES = {"price", "news", "promo", "auto"}


@dataclass(frozen=True)
class Slot:
    at: time
    post_type: str


@dataclass(frozen=True)
class Config:
    bot_token: str
    channel_id: str
    admin_ids: frozenset[int]
    slots: tuple[Slot, ...]
    timezone: str
    coingecko_api_key: str
    coins: dict[str, str]
    vs_currencies: tuple[str, ...]
    news_queries: tuple[str, ...]
    news_lang: str
    news_country: str
    extra_rss: tuple[str, ...]
    news_max_age_hours: int
    news_keywords: tuple[str, ...]
    cta_text: str
    hashtags: str
    log_level: str
    data_dir: Path = field(default=Path("data"))


def _split(value: str, sep: str = ",") -> list[str]:
    return [p.strip() for p in value.split(sep) if p.strip()]


def _parse_slots(raw: str) -> tuple[Slot, ...]:
    slots: list[Slot] = []
    for item in _split(raw):
        parts = item.split(":")
        if len(parts) < 2:
            raise ValueError(f"Неверный слот расписания: {item!r} (нужно ЧЧ:ММ:тип)")
        hh, mm = int(parts[0]), int(parts[1])
        ptype = parts[2].strip().lower() if len(parts) > 2 else "auto"
        if ptype not in VALID_TYPES:
            raise ValueError(f"Неизвестный тип поста {ptype!r} в слоте {item!r}")
        slots.append(Slot(time(hh, mm), ptype))
    if not slots:
        raise ValueError("SCHEDULE пуст")
    return tuple(sorted(slots, key=lambda s: s.at))


def _parse_coins(raw: str) -> dict[str, str]:
    coins: dict[str, str] = {}
    for item in _split(raw):
        if "=" not in item:
            continue
        ticker, cg_id = item.split("=", 1)
        coins[ticker.strip().upper()] = cg_id.strip()
    return coins


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    channel = os.getenv("CHANNEL_ID", "").strip()
    if not token or not channel:
        raise RuntimeError("Заполните BOT_TOKEN и CHANNEL_ID в .env")

    admin_ids = frozenset(int(x) for x in _split(os.getenv("ADMIN_IDS", "")))

    return Config(
        bot_token=token,
        channel_id=channel,
        admin_ids=admin_ids,
        slots=_parse_slots(os.getenv("SCHEDULE", "10:00:price,13:00:news,17:00:promo,20:00:news")),
        timezone=os.getenv("TIMEZONE", "UTC"),
        coingecko_api_key=os.getenv("COINGECKO_API_KEY", "").strip(),
        coins=_parse_coins(os.getenv("COINS", "TON=the-open-network")),
        vs_currencies=tuple(_split(os.getenv("VS_CURRENCIES", "usd,rub"))),
        news_queries=tuple(_split(os.getenv("NEWS_QUERIES", "Telegram Stars"), ";")),
        news_lang=os.getenv("NEWS_LANG", "ru"),
        news_country=os.getenv("NEWS_COUNTRY", "RU"),
        extra_rss=tuple(_split(os.getenv("EXTRA_RSS", ""))),
        news_max_age_hours=int(os.getenv("NEWS_MAX_AGE_HOURS", "72")),
        news_keywords=tuple(k.lower() for k in _split(os.getenv("NEWS_KEYWORDS", ""))),
        cta_text=os.getenv("CTA_TEXT", "⭐ Покупайте звёзды!"),
        hashtags=os.getenv("HASHTAGS", "#Stars #GRAM #TelegramGifts"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
    )
