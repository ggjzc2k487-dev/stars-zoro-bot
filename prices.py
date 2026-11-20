"""Курсы монет через публичный API CoinGecko."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

from config import Config

log = logging.getLogger(__name__)

API_URL = "https://api.coingecko.com/api/v3/simple/price"


@dataclass
class CoinPrice:
    ticker: str
    prices: dict[str, float]  # {"usd": 1.23, "rub": 100.5}
    change_24h: float | None  # % к первой валюте из списка


async def fetch_prices(session: aiohttp.ClientSession, cfg: Config) -> list[CoinPrice]:
    """Возвращает цены тех монет, что удалось получить. Пустой список — если API недоступен."""
    if not cfg.coins:
        return []

    ids = ",".join(cfg.coins.values())
    vs = ",".join(cfg.vs_currencies)
    params = {"ids": ids, "vs_currencies": vs, "include_24hr_change": "true"}
    headers = {"accept": "application/json"}
    if cfg.coingecko_api_key:
        headers["x-cg-demo-api-key"] = cfg.coingecko_api_key

    try:
        async with session.get(
            API_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status != 200:
                log.warning("CoinGecko вернул %s", resp.status)
                return []
            data = await resp.json()
    except Exception:
        log.exception("Ошибка запроса к CoinGecko")
        return []

    first_vs = cfg.vs_currencies[0]
    result: list[CoinPrice] = []
    for ticker, cg_id in cfg.coins.items():
        item = data.get(cg_id)
        if not item:
            log.info("CoinGecko не знает монету %s (id=%s) — пропускаю", ticker, cg_id)
            continue
        prices = {c: float(item[c]) for c in cfg.vs_currencies if c in item}
        if not prices:
            continue
        change = item.get(f"{first_vs}_24h_change")
        result.append(CoinPrice(ticker, prices, float(change) if change is not None else None))
    return result
