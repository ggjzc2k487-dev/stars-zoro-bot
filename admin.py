"""Команды администратора."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import Config
from publisher import Publisher
from storage import Storage
from formatting import esc

router = Router(name="admin")

HELP = (
    "<b>Команды администратора</b>\n\n"
    "/status — состояние бота и последние действия\n"
    "/post [price|news|promo|auto] — опубликовать пост сейчас\n"
    "/say &lt;текст&gt; — отправить в канал свой текст (HTML разрешён)\n"
    "/templates — список своих шаблонов\n"
    "/addtemplate &lt;текст&gt; — добавить шаблон (можно {cta} и {tags})\n"
    "/deltemplate &lt;номер&gt; — удалить шаблон"
)


def _is_admin(message: Message, cfg: Config) -> bool:
    return bool(message.from_user and message.from_user.id in cfg.admin_ids)


@router.message(Command("start", "help"))
async def cmd_start(message: Message, cfg: Config) -> None:
    if not _is_admin(message, cfg):
        await message.answer("👋 Привет! Это служебный бот канала. Заглядывайте в канал за звёздами и подарками ⭐")
        return
    await message.answer(HELP)


@router.message(Command("status"))
async def cmd_status(
    message: Message, cfg: Config, storage: Storage, sched_state: dict
) -> None:
    if not _is_admin(message, cfg):
        return
    tz = ZoneInfo(cfg.timezone)
    nxt = sched_state.get("next_run")
    nxt_txt = (
        f"{nxt.astimezone(tz):%d.%m %H:%M} ({sched_state.get('next_type')})" if nxt else "—"
    )
    started: datetime = sched_state["started"]
    uptime = datetime.now(tz) - started
    hours, rem = divmod(int(uptime.total_seconds()), 3600)

    logs = storage.last_logs(5)
    if logs:
        log_lines = "\n".join(
            f"{'✅' if e['ok'] else '❌'} {e['ts'][5:16].replace('T', ' ')} UTC — {esc(e['info'])}"
            for e in reversed(logs)
        )
    else:
        log_lines = "пока пусто"

    slots = ", ".join(f"{s.at:%H:%M}={s.post_type}" for s in cfg.slots)
    await message.answer(
        "🤖 <b>Бот работает</b>\n\n"
        f"⏱ Аптайм: {hours} ч {rem // 60} мин\n"
        f"📅 Расписание ({cfg.timezone}): {slots}\n"
        f"⏭ Следующий пост: {nxt_txt}\n"
        f"📢 Канал: {esc(cfg.channel_id)}\n\n"
        f"<b>Последние действия:</b>\n{log_lines}"
    )


@router.message(Command("post"))
async def cmd_post(
    message: Message, command: CommandObject, cfg: Config, publisher: Publisher
) -> None:
    if not _is_admin(message, cfg):
        return
    ptype = (command.args or "auto").strip().lower()
    if ptype not in {"price", "news", "promo", "auto"}:
        await message.answer("Тип: price, news, promo или auto")
        return
    await message.answer("⏳ Собираю пост…")
    await message.answer(await publisher.publish(ptype, manual=True))


@router.message(Command("say"))
async def cmd_say(
    message: Message, command: CommandObject, cfg: Config, publisher: Publisher
) -> None:
    if not _is_admin(message, cfg):
        return
    if not command.args:
        await message.answer("Использование: /say текст поста")
        return
    await message.answer(await publisher.send_raw(command.args))


@router.message(Command("templates"))
async def cmd_templates(message: Message, cfg: Config, storage: Storage) -> None:
    if not _is_admin(message, cfg):
        return
    items = storage.user_templates()
    if not items:
        await message.answer("Своих шаблонов пока нет. Добавьте: /addtemplate текст")
        return
    body = "\n\n".join(f"<b>{i}.</b> {esc(t)}" for i, t in enumerate(items, 1))
    await message.answer(body)


@router.message(Command("addtemplate"))
async def cmd_add_template(
    message: Message, command: CommandObject, cfg: Config, storage: Storage
) -> None:
    if not _is_admin(message, cfg):
        return
    if not command.args:
        await message.answer("Использование: /addtemplate 🧸 Текст шаблона... {cta} {tags}")
        return
    n = await storage.add_template(command.args)
    await message.answer(f"✅ Шаблон №{n} добавлен и войдёт в ротацию промо-постов")


@router.message(Command("deltemplate"))
async def cmd_del_template(
    message: Message, command: CommandObject, cfg: Config, storage: Storage
) -> None:
    if not _is_admin(message, cfg):
        return
    try:
        idx = int((command.args or "").strip()) - 1
    except ValueError:
        await message.answer("Использование: /deltemplate номер")
        return
    ok = await storage.remove_template(idx)
    await message.answer("🗑 Удалено" if ok else "Нет шаблона с таким номером")
