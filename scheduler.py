"""Автопостинг по расписанию из конфига (SCHEDULE) без сторонних зависимостей."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import Config, Slot
from publisher import Publisher

log = logging.getLogger(__name__)


def next_slot(now: datetime, slots: tuple[Slot, ...]) -> tuple[datetime, Slot]:
    """Ближайший слот строго после now (в той же таймзоне)."""
    for day_offset in (0, 1):
        day = (now + timedelta(days=day_offset)).date()
        for slot in slots:
            candidate = datetime.combine(day, slot.at, tzinfo=now.tzinfo)
            if candidate > now:
                return candidate, slot
    raise RuntimeError("unreachable")


async def run_scheduler(publisher: Publisher, cfg: Config, state: dict) -> None:
    tz = ZoneInfo(cfg.timezone)
    log.info("Планировщик запущен: %s", ", ".join(f"{s.at:%H:%M}={s.post_type}" for s in cfg.slots))

    while True:
        try:
            now = datetime.now(tz)
            when, slot = next_slot(now, cfg.slots)
            state["next_run"] = when
            state["next_type"] = slot.post_type
            delay = (when - now).total_seconds()
            log.info("Следующий пост (%s) в %s", slot.post_type, when.strftime("%d.%m %H:%M"))
            await asyncio.sleep(max(delay, 0))
            await publisher.publish(slot.post_type)
        except asyncio.CancelledError:
            raise
        except Exception:
            # планировщик не должен падать никогда
            log.exception("Ошибка в цикле планировщика, продолжаю через 30 с")
            await asyncio.sleep(30)
