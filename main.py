import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_config
import admin
from scheduler import run_scheduler
from publisher import Publisher
from storage import Storage
from logger import setup_logging

log = logging.getLogger("main")


async def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level, cfg.data_dir)

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = Storage(cfg.data_dir)
    publisher = Publisher(bot, cfg, storage)
    sched_state: dict = {"started": datetime.now(ZoneInfo(cfg.timezone))}

    dp = Dispatcher(cfg=cfg, publisher=publisher, sched_state=sched_state)
    dp["storage"] = storage
    dp.include_router(admin.router)

    scheduler_task = asyncio.create_task(run_scheduler(publisher, cfg, sched_state))
    try:
        me = await bot.get_me()
        log.info("Бот @%s запущен", me.username)
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлен")
