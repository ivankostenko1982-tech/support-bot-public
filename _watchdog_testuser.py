from __future__ import annotations
import asyncio
from contextlib import suppress

def _normalize_status(status_obj) -> str:
    if status_obj is None:
        return "unknown"
    val = getattr(status_obj, "value", None)
    if isinstance(val, str):
        return val.lower()
    if isinstance(status_obj, str):
        return status_obj.lower()
    return str(status_obj).lower()

async def _get_member_status_safe(bot, chat_id: int, user_id: int, log) -> str:
    try:
        cm = await bot.get_chat_member(chat_id, user_id)
        return _normalize_status(getattr(cm, "status", None))
    except Exception as e:
        log.debug("TESTUSER watchdog: get_chat_member failed: %r", e)
        return "unknown"

def _register_probe(cmd_router, bot, log, chat_id: int, user_id: int):
    from aiogram.filters import Command
    from aiogram.types import Message

    @cmd_router.message(Command("probe_testuser"))
    async def _cmd_probe_testuser(message: 'Message'):
        if not (chat_id and user_id):
            await message.reply("TEST_CHAT_ID/TEST_USER_ID не заданы.")
            return
        status = await _get_member_status_safe(bot, chat_id, user_id, log)
        await message.reply(f"TESTUSER status in chat {chat_id}: <b>{status}</b>")
        log.info("TESTUSER PROBE: chat=%s uid=%s status=%s", chat_id, user_id, status)

async def _loop(bot, log, db_get_setting, db_set_setting, chat_id: int, user_id: int):
    key = f"testuser:{chat_id}:{user_id}:status"
    prev = (db_get_setting(key) or "")
    if not prev:
        cur = await _get_member_status_safe(bot, chat_id, user_id, log)
        with suppress(Exception):
            db_set_setting(key, cur)
        log.info("TESTUSER WD init: chat=%s uid=%s status=%s", chat_id, user_id, cur)
        prev = cur

    interval = 30
    while True:
        cur = await _get_member_status_safe(bot, chat_id, user_id, log)
        if cur != prev and cur in {"left","kicked","restricted","member","administrator","creator"}:
            log.info("TESTUSER STATUS CHANGE: chat=%s uid=%s %s->%s", chat_id, user_id, prev, cur)
            with suppress(Exception):
                db_set_setting(key, cur)
            prev = cur
        await asyncio.sleep(interval)

async def start(bot, dp, log, cmd_router, TEST_CHAT_ID: int, TEST_USER_ID: int):
    if not (log and cmd_router) or not (TEST_CHAT_ID and TEST_USER_ID):
        return
    try:
        import app as _app
        db_get_setting = getattr(_app, "db_get_setting", lambda k: None)
        db_set_setting = getattr(_app, "db_set_setting", lambda k, v: None)
    except Exception:
        db_get_setting = lambda k: None
        db_set_setting = lambda k, v: None
    _register_probe(cmd_router, bot, log, TEST_CHAT_ID, TEST_USER_ID)
    asyncio.create_task(_loop(bot, log, db_get_setting, db_set_setting, TEST_CHAT_ID, TEST_USER_ID))
    log.info("TESTUSER WD started for chat=%s uid=%s", TEST_CHAT_ID, TEST_USER_ID)
