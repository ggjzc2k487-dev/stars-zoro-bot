"""Новости: Google News RSS (по запросам) + любые свои RSS-ленты."""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import aiohttp

from config import Config
from formatting import make_key, normalize_title

log = logging.getLogger(__name__)

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl={lang}&gl={country}&ceid={country}:{lang}"
USER_AGENT = "StarsZoroBot/1.0 (+RSS reader; respects publisher terms)"


@dataclass
class NewsItem:
    title: str
    link: str
    published: datetime
    key: str


def _parse_rss(xml_text: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        log.warning("RSS не удалось распарсить")
        return items

    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub_raw = node.findtext("pubDate")
        if not title or not link:
            continue
        try:
            published = parsedate_to_datetime(pub_raw) if pub_raw else datetime.now(timezone.utc)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published = datetime.now(timezone.utc)
        items.append(NewsItem(title, link, published, make_key("news", normalize_title(title))))
    return items


async def _fetch_feed(session: aiohttp.ClientSession, url: str) -> list[NewsItem]:
    try:
        async with session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                log.warning("RSS %s -> %s", url[:80], resp.status)
                return []
            return _parse_rss(await resp.text())
    except Exception:
        log.exception("Ошибка загрузки RSS %s", url[:80])
        return []


async def fetch_news(session: aiohttp.ClientSession, cfg: Config) -> list[NewsItem]:
    """Все подходящие новости, свежие первыми. Фильтр по возрасту и ключевым словам."""
    urls = [
        GOOGLE_NEWS.format(q=quote_plus(q), lang=cfg.news_lang, country=cfg.news_country)
        for q in cfg.news_queries
    ]
    urls += list(cfg.extra_rss)

    results = await asyncio.gather(*(_fetch_feed(session, u) for u in urls))

    min_date = datetime.now(timezone.utc) - timedelta(hours=cfg.news_max_age_hours)
    seen: set[str] = set()
    out: list[NewsItem] = []
    for items in results:
        for it in items:
            if it.key in seen or it.published < min_date:
                continue
            if cfg.news_keywords and not any(k in it.title.lower() for k in cfg.news_keywords):
                continue
            seen.add(it.key)
            out.append(it)
    out.sort(key=lambda i: i.published, reverse=True)
    return out
