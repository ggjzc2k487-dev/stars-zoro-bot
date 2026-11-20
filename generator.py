"""Сборка текстов постов в стиле канала «Stars Zoro»."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from config import Config
from news import NewsItem
from prices import CoinPrice
from storage import Storage
from formatting import esc, fmt_change, fmt_money

# Базовые шаблоны. Переменные: {cta}, {tags}. HTML разрешён.
# Свои шаблоны добавляются командой /addtemplate и хранятся в data/state.json.
DEFAULT_TEMPLATES: list[str] = [
    "🧸 <b>Милый мишка с сердечком уже ждёт!</b>\n\n"
    "Покупайте звёзды и дарите тёплые эмоции близким 💝\n\n{cta}\n\n{tags}",
    "✅ <b>Бот работает в штатном режиме!</b>\n\n"
    "Звёзды, подарки и всё для Telegram — быстро и без лишних вопросов ⚡\n\n{cta}\n\n{tags}",
    "🎁 <b>Хотите удивить друга?</b>\n\n"
    "Лимитированные подарки редеют с каждым днём. Успейте забрать свой 🐻❤️\n\n{cta}\n\n{tags}",
    "⭐ <b>Звёзды — это удобно</b>\n\n"
    "Оплачивайте подарки, ботов и подписки прямо в Telegram. Пополнить баланс — пара минут!\n\n{cta}\n\n{tags}",
    "💎 <b>Хороший день, чтобы пополнить звёзды</b>\n\n"
    "Дарите подарки, поддерживайте авторов и радуйте себя 🎉\n\n{cta}\n\n{tags}",
]


@dataclass
class Post:
    text: str
    kind: str
    dedup_key: str | None = None  # если задан — после отправки запоминаем


def build_price_post(cfg: Config, prices: list[CoinPrice]) -> Post | None:
    if not prices:
        return None

    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz).strftime("%d.%m %H:%M")
    lines = [f"📊 <b>Курс на {now}</b>", ""]
    for p in prices:
        parts = " · ".join(fmt_money(p.prices[c], c) for c in cfg.vs_currencies if c in p.prices)
        change = fmt_change(p.change_24h)
        lines.append(f"💎 <b>{esc(p.ticker)}</b>: {parts}")
        if change:
            lines.append(f"      {change}")
    lines += ["", cfg.cta_text, "", cfg.hashtags + " #TON"]
    return Post("\n".join(lines), "price")


NEWS_INTROS = [
    "🔥 <b>Новости Telegram</b>",
    "📰 <b>Свежо из экосистемы</b>",
    "⚡ <b>Коротко о главном</b>",
    "🚀 <b>Что нового</b>",
]


def build_news_post(cfg: Config, item: NewsItem) -> Post:
    text = (
        f"{random.choice(NEWS_INTROS)}\n\n"
        f"📌 {esc(item.title)}\n\n"
        f'👉 <a href="{esc(item.link)}">Читать подробнее</a>\n\n'
        f"{cfg.cta_text}\n\n{cfg.hashtags}"
    )
    return Post(text, "news", item.key)


async def build_promo_post(cfg: Config, storage: Storage) -> Post:
    templates = DEFAULT_TEMPLATES + storage.user_templates()
    idx = storage.next_promo_index(len(templates))
    await storage.set_promo_index(idx)
    text = templates[idx].format_map(_SafeDict(cta=cfg.cta_text, tags=cfg.hashtags))
    return Post(text, "promo")


class _SafeDict(dict):
    """Неизвестные {плейсхолдеры} в пользовательских шаблонах не роняют бота."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
