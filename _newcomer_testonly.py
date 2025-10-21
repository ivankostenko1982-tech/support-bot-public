@"
from __future__ import annotations
"""
Test-only sidecar: одноразовое уведомление админам (из ADMIN_IDS)
о ПЕРВОМ сообщении тестового новичка в тестовом чате во время окна новичка.
Не вмешивается в основную логику удаления (её делает _watchdog_testpurge.py).
"""
import os
import time
import logging
from typing import Optional, Iterable, Set

try:
    from aiogram import Router, F  # type: ignore
    from aiogram.types import Message  # type: ignore
except Exception:
    Router = object  # type: ignore
    F = None         # type: ignore
    Message = object # type: ignore

_log = logging.getLogger("support-join-guard")
_NEWCOMER_WIN = 24 * 60 * 60

def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except Exception:
        return default

# --- безопасное подключение логики окна новичка из app.py ---
try:
    from app import newcomer_until as app_newcomer_until  # type: ignore
    from app import NEWCOMER_WINDOW_SECONDS as APP_WIN    # type: ignore
    _NEWCOMER_WIN = int(APP_WIN) if isinstance(APP_WIN, int) else _get_int_env("NEWCOMER_WINDOW_SECONDS", _NEWCOMER_WIN)
    def _newcomer_until(uid: int, cid: int) -> Optional[int]:
        return app_newcomer_until(uid, cid)
except Exception:
    _NEWCOMER_WIN = _get_int_env("NEWCOMER_WINDOW_SECONDS", _NEWCOMER_WIN)
    def _newcomer_until(uid: int, cid: int) -> Optional[int]:
        # Фолбэк: считаем, что окно активно на ближайшее время
        now = int(time.time())
        return now + _NEWCOMER_WIN

def _flag(name: str) -> bool:
    return os.getenv(name, "0").lower() in {"1", "true", "yes", "on"}

TEST_MODE   = _flag("NEWCOMER_TEST_ONLY")
TEST_CHAT_ID = int(os.getenv("TEST_CHAT_ID", "0") or "0")
TEST_USER_ID = int(os.getenv("TEST_USER_ID", "0") or "0")

def _parse_ids(val: Optional[str]) -> Iterable[int]:
    if not val:
        return []
    raw = val.replace(",", " ").split()
    out = []
    for x in raw:
        try:
            out.append(int(x))
        except Exception:
            continue
    return out

ADMIN_IDS = list(_parse_ids(os.getenv("ADMIN_IDS", "")))

# Кого уже уведомили (на процесс): {(chat_id, user_id)}
_notified: Set[tuple[int, int]] = set()

async def _notify_admins_once(message: Message, until_ts: int) -> None:
    if not ADMIN_IDS:
        _log.info("TESTONLY: no ADMIN_IDS in ENV — skip admin notify")
        return
    bot = getattr(message, "bot", None)
    if bot is None:
        _log.warning("TESTONLY: message.bot is None — cannot DM admins")
        return

    chat_id = int(message.chat.id)
    user_id = int(message.from_user.id) if message.from_user else 0
    key = (chat_id, user_id)
    if key in _notified:
        _log.info("TESTONLY: already-notified key=%s — skip", key)
        return

    text = (message.text or message.caption or "").strip() or "<без текста>"
    preview = text if len(text) <= 300 else (text[:297] + "…")
    until_hh = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(until_ts))
    body = (
        "⚠️ Новичок в тестовом чате\n"
        f"• chat_id: {chat_id}\n"
        f"• user_id: {user_id}\n"
        f"• окно до: {until_hh} (ts={until_ts})\n"
        "• первое сообщение (удалено):\n"
        f"———\n{preview}\n———"
    )

    ok = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, body)
            ok += 1
        except Exception as e:
            _log.warning("TESTONLY: admin DM failed admin_id=%s err=%r", admin_id, e)
    if ok > 0:
        _notified.add(key)
        _log.info("TESTONLY: notified %s admin(s) for key=%s", ok, key)

async def _on_message(message: Message) -> None:
    try:
        if not TEST_MODE:
            return
        if not getattr(message, "chat", None) or not getattr(message, "from_user", None):
            return
        if int(message.chat.id) != TEST_CHAT_ID:
            return
        uid = int(message.from_user.id)
        if uid != TEST_USER_ID:
            return

        until_ts = _newcomer_until(uid, TEST_CHAT_ID)
        if until_ts is None:
            _log.info("TESTONLY: newcomer_until=None — not approved yet, skip")
            return
        now = int(time.time())
        if now >= int(until_ts):
            _log.info("TESTONLY: window expired now=%s until=%s — skip", now, until_ts)
            return

        await _notify_admins_once(message, int(until_ts))
    except Exception as e:
        _log.exception("TESTONLY: handler error: %r", e)

def setup_newcomer_testonly(router: Router, log: Optional[logging.Logger] = None) -> None:
    if log is not None:
        global _log
        _log = log
    if hasattr(router, "message") and hasattr(router.message, "register"):
        router.message.register(_on_message)
        _log.info("NEWCOMER_TESTONLY: handler registered via router.message.register")
    else:
        _log.warning("NEWCOMER_TESTONLY: router.message.register not available; handler NOT registered")

# совместимый алиас на всякий случай
def setup_newcomer_testonly_compat(*args, **kwargs):
    try:
        router = args[0] if args else kwargs.get("router")
        log = kwargs.get("log")
        return setup_newcomer_testonly(router, log)
    except Exception as e:
        _log.warning("NEWCOMER_TESTONLY: compat wrapper failed: %r", e)
"@ | Set-Content -NoNewline -Encoding UTF8 _newcomer_testonly.py
