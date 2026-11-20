"""Публикация постов в канал: выбор типа, фолбэки, ретраи, антидубли."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from config import Config
import generator
from news import fetch_news
from prices import fetch_prices
from storage import Storage

log = logging.getLogger(__name__)


class Publisher:
    def __init__(self, bot: Bot, cfg: Config, storage: Storage) -> None:
        self.bot = bot
        self.cfg = cfg
        self.storage = storage
        self._lock = asyncio.Lock()  # два поста одновременно не публикуем

    async def _build(self, post_type: str, session: aiohttp.ClientSession) -> generator.Post | None:
        if post_type == "price":
            return generator.build_price_post(self.cfg, await fetch_prices(session, self.cfg))

        if post_type == "news":
            for item in await fetch_news(session, self.cfg):
                if not self.storage.is_sent(item.key):
                    return generator.build_news_post(self.cfg, item)
            return None

        if post_type == "promo":
            return await generator.build_promo_post(self.cfg, self.storage)

        return None

    async def publish(self, post_type: str, manual: bool = False) -> str:
        """Собирает и публикует пост. Возвращает короткий отчёт (для /post и логов)."""
        async with self._lock:
            order = {
                "price": ["price", "promo"],
                "news": ["news", "promo"],
                "promo": ["promo"],
                "auto": ["news", "promo"],
            }[post_type]

            async with aiohttp.ClientSession() as session:
                post = None
                for candidate in order:
                    try:
                        post = await self._build(candidate, session)
                    except Exception:
                        log.exception("Ошибка сборки поста %s", candidate)
                        post = None
                    if post:
                        if candidate != post_type and post_type != "auto":
                            log.info("Тип %s недоступен, использован %s", post_type, candidate)
                        break

            if not post:
                msg = f"Не удалось собрать пост типа {post_type}"
                await self.storage.add_log(post_type, False, msg)
                return msg

            return await self._send(post, manual)

    async def send_raw(self, text: str) -> str:
        return await self._send(generator.Post(text, "manual"), manual=True)

    async def _send(self, post: generator.Post, manual: bool) -> str:
        for attempt in range(1, 4):
            try:
                await self.bot.send_message(
                    self.cfg.channel_id,
                    post.text,
                    disable_web_page_preview=True,
                )
                if post.dedup_key:
                    await self.storage.mark_sent(post.dedup_key)
                label = f"{post.kind}{' (вручную)' if manual else ''}"
                await self.storage.add_log(post.kind, True, f"опубликован: {label}")
                log.info("Опубликован пост: %s", label)
                return f"✅ Опубликован пост: {label}"
            except TelegramRetryAfter as e:
                log.warning("Flood control, жду %s с", e.retry_after)
                await asyncio.sleep(e.retry_after + 1)
            except TelegramAPIError as e:
                log.error("Ошибка Telegram (попытка %s): %s", attempt, e)
                await self.storage.add_log(post.kind, False, f"Telegram: {e}")
                if attempt == 3:
                    return f"❌ Ошибка Telegram: {e}"
                await asyncio.sleep(3 * attempt)
            except Exception as e:
                log.exception("Неожиданная ошибка при отправке")
                await self.storage.add_log(post.kind, False, f"Ошибка: {e}")
                return f"❌ Ошибка: {e}"
        return "❌ Не удалось отправить пост"
