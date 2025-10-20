from __future__ import annotations
import os, time, sqlite3, logging
from typing import Optional
log = logging.getLogger("support-join-guard")

def _env_flag(v: str) -> bool:
    return (os.getenv(v, "0").lower() in {"1","true","yes","on"})

def _get_int(name: str, default: int = 0) -> int:
    s = os.getenv(name, "")
    try:
        return int(s)
    except Exception:
        return default

def _newcomer_until_from_db(uid: int, cid: int) -> Optional[int]:
    db = os.getenv("SQLITE_PATH", "/opt/tgbots/bots/support/join_guard_state.db")
    win = _get_int("NEWCOMER_WINDOW_SECONDS", 86400)
    try:
        with sqlite3.connect(db, timeout=3.0) as conn:
            row = conn.execute(
                "SELECT approved_at FROM approvals WHERE user_id=? AND chat_id=?",
                (int(uid), int(cid)),
            ).fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0]) + int(win)
    except Exception:
        log.exception("TESTPURGE: DB read failed uid=%s cid=%s", uid, cid)
        return None

async def start(bot, dp, log, cmd_router, TEST_CHAT_ID: int, TEST_USER_ID: int) -> None:
    """Delete ALL messages from TEST_USER in TEST_CHAT while newcomer window is active.
       Works only when NEWCOMER_TEST_ONLY=1 (safety)."""
    try:
        try:
            # aiogram v3
            from aiogram import Router, types
            router = Router(name="test_purge_router")
            @router.message()
            async def _purge(m: "types.Message"):
                if not (m and m.chat and m.from_user):
                    return
                if not _env_flag("NEWCOMER_TEST_ONLY"):
                    return
                if int(m.chat.id) != int(TEST_CHAT_ID) or int(m.from_user.id) != int(TEST_USER_ID):
                    return
                nu = _newcomer_until_from_db(TEST_USER_ID, TEST_CHAT_ID)
                now = int(time.time())
                if nu is not None and now < int(nu):
                    try:
                        await bot.delete_message(m.chat.id, m.message_id)
                        log.info("TESTPURGE: deleted msg chat=%s uid=%s mid=%s until=%s now=%s",
                                 m.chat.id, m.from_user.id, m.message_id, nu, now)
                    except Exception as e:
                        log.warning("TESTPURGE: delete failed chat=%s uid=%s mid=%s err=%r",
                                    m.chat.id, m.from_user.id, m.message_id, e)
            dp.include_router(router)
            log.info("TESTPURGE: router registered (v3)")
            return
        except Exception:
            # aiogram v2
            from aiogram import types
            @dp.message_handler()
            async def _purge_v2(m: "types.Message"):
                if not (m and m.chat and m.from_user):
                    return
                if not _env_flag("NEWCOMER_TEST_ONLY"):
                    return
                if int(m.chat.id) != int(TEST_CHAT_ID) or int(m.from_user.id) != int(TEST_USER_ID):
                    return
                nu = _newcomer_until_from_db(TEST_USER_ID, TEST_CHAT_ID)
                now = int(time.time())
                if nu is not None and now < int(nu):
                    try:
                        await bot.delete_message(m.chat.id, m.message_id)
                        log.info("TESTPURGE(v2): deleted msg chat=%s uid=%s mid=%s until=%s now=%s",
                                 m.chat.id, m.from_user.id, m.message_id, nu, now)
                    except Exception as e:
                        log.warning("TESTPURGE(v2): delete failed chat=%s uid=%s mid=%s err=%r",
                                    m.chat.id, m.from_user.id, m.message_id, e)
            log.info("TESTPURGE: handler registered (v2)")
    except Exception:
        log.exception("TESTPURGE: registration failed")
