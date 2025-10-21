from __future__ import annotations
"""
Test-only: одноразовое DM-уведомление ADMIN_IDS о ПЕРВОМ сообщении
тестового новичка (TEST_USER_ID) в TEST_CHAT_ID пока активно окно новичка.
Не вмешивается в удаление (этим занимается _watchdog_testpurge.py).
"""
import os, time, logging
from typing import Optional, Set

_LOG = logging.getLogger("support-join-guard")
_LOG.info("NEWCOMER_TESTONLY: module imported")

# --- безопасный импорт aiogram ---
try:
    from aiogram import Router, F  # type: ignore
    from aiogram.types import Message  # type: ignore
except Exception as e:
    Router = object  # type: ignore
    F = None         # type: ignore
    Message = object # type: ignore
    _LOG.warning("NEWCOMER_TESTONLY: aiogram import failed: %r", e)

def _flag(name: str) -> bool:
    return os.getenv(name, "0").lower() in {"1","true","yes","on"}

def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except Exception:
        return default

def _parse_ids(val: str | None) -> list[int]:
    if not val: return []
    out = []
    for tok in val.replace(",", " ").split():
        try: out.append(int(tok))
        except: pass
    return out

TEST_CHAT_ID = int(os.getenv("TEST_CHAT_ID","0") or "0")
TEST_USER_ID = int(os.getenv("TEST_USER_ID","0") or "0")
# Новый fallback: если оба TEST_* заданы — считаем TEST_MODE=True, даже без флага
TEST_MODE = _flag("NEWCOMER_TEST_ONLY") or (bool(TEST_CHAT_ID) and bool(TEST_USER_ID))
NEWCOMER_WINDOW_SECONDS = _get_int_env("NEWCOMER_WINDOW_SECONDS", 24*60*60)
ADMIN_IDS = _parse_ids(os.getenv("ADMIN_IDS",""))

# --- окно новичка из app.py (если доступно) ---
try:
    from app import newcomer_until as _app_newcomer_until  # type: ignore
    def _newcomer_until(uid: int, cid: int) -> Optional[int]:
        return _app_newcomer_until(uid, cid)
    _LOG.info("NEWCOMER_TESTONLY: using app.newcomer_until()")
except Exception as e:
    _LOG.warning("NEWCOMER_TESTONLY: fallback newcomer_until: %r", e)
    def _newcomer_until(uid: int, cid: int) -> Optional[int]:
        return int(time.time()) + NEWCOMER_WINDOW_SECONDS

# Кто уже уведомлён (в рамках одного запуска)
_notified: Set[tuple[int,int]] = set()

async def _notify_admins_once(message: Message, until_ts: int) -> None:
    if not ADMIN_IDS:
        _LOG.info("TESTONLY: ADMIN_IDS empty — skip")
        return
    bot = getattr(message, "bot", None)
    if bot is None:
        _LOG.warning("TESTONLY: message.bot is None — cannot DM")
        return

    chat_id = int(message.chat.id)
    user_id = int(message.from_user.id) if getattr(message, "from_user", None) else 0
    key = (chat_id, user_id)
    if key in _notified:
        _LOG.info("TESTONLY: already notified key=%s", key); return

    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip() or "<без текста>"
    preview = text if len(text) <= 300 else (text[:297] + "…")
    until_hh = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(until_ts)))

    body = (
        "⚠️ Новичок (тестовый) отправил первое сообщение\n"
        f"• chat_id: {chat_id}\n"
        f"• user_id: {user_id}\n"
        f"• окно до: {until_hh} (ts={until_ts})\n"
        "• сообщение (удалено в чате):\n"
        f"———\n{preview}\n———"
    )

    ok = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, body)
            ok += 1
        except Exception as e:
            _LOG.warning("TESTONLY: DM admin_id=%s failed: %r", admin_id, e)
    if ok > 0:
        _notified.add(key)
        _LOG.info("TESTONLY: notified %s admin(s) key=%s", ok, key)

async def _on_message(message: Message) -> None:
    _LOG.info("TESTONLY: probe(entry) chat=%s uid=%s",
              getattr(getattr(message,"chat",None),"id",None),
              getattr(getattr(message,"from_user",None),"id",None))
    try:
        if not TEST_MODE:
            _LOG.info("TESTONLY: TEST_MODE=0 — skip"); return
        if not getattr(message, "chat", None) or not getattr(message, "from_user", None):
            _LOG.info("TESTONLY: no chat/from_user — skip"); return
        if int(message.chat.id) != TEST_CHAT_ID:
            _LOG.info("TESTONLY: other chat %s — skip", message.chat.id); return
        uid = int(message.from_user.id)
        if uid != TEST_USER_ID:
            _LOG.info("TESTONLY: other user %s — skip", uid); return

        until_ts = _newcomer_until(uid, TEST_CHAT_ID)
        if until_ts is None:
            _LOG.info("TESTONLY: newcomer_until=None — not approved yet"); return
        now = int(time.time())
        if now >= int(until_ts):
            _LOG.info("TESTONLY: window expired now=%s until=%s — skip", now, until_ts); return

        await _notify_admins_once(message, int(until_ts))
    except Exception as e:
        _LOG.exception("TESTONLY: handler error: %r", e)

def setup_newcomer_testonly(router: Router, log: logging.Logger | None = None) -> None:
    if log is not None:
        global _LOG; _LOG = log
    # Регистрация на router
    if hasattr(router, "message") and hasattr(router.message, "register"):
        router.message.register(_on_message)
        _LOG.info("NEWCOMER_TESTONLY: handler registered via router.message.register")
    else:
        _LOG.warning("NEWCOMER_TESTONLY: router.message.register missing")
    # Параллельно пробуем зарегистрироваться на dp (если app.dp существует)
    try:
        import app as _app  # type: ignore
        dp = getattr(_app, "dp", None)
        if dp and hasattr(dp, "message") and hasattr(dp.message, "register"):
            dp.message.register(_on_message)
            _LOG.info("NEWCOMER_TESTONLY: handler also registered via dp.message.register")
    except Exception as e:
        _LOG.info("NEWCOMER_TESTONLY: dp register skipped: %r", e)

# Совместимые алиасы (на случай других вызовов из app.py)
def setup_newcomer_testonly_compat(*args, **kwargs): return setup_newcomer_testonly(*(args[:1] or (kwargs.get("router"),)), kwargs.get("log"))
def init_newcomer_testonly(*args, **kwargs):       return setup_newcomer_testonly(*(args[:1] or (kwargs.get("router"),)), kwargs.get("log"))
def init_newcomer_test_only(*args, **kwargs):      return setup_newcomer_testonly(*(args[:1] or (kwargs.get("router"),)), kwargs.get("log"))
def setup(*args, **kwargs):                        return setup_newcomer_testonly(*(args[:1] or (kwargs.get("router"),)), kwargs.get("log"))
