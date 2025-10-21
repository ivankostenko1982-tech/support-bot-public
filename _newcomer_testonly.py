# newcomer test-only sidecar (clean rewrite)
# - устойчивые точки входа: setup_newcomer_testonly(*args, **kwargs) и init_newcomer_testonly(*args, **kwargs)
# - уведомление админов (ADMIN_IDS) о первом сообщении новичка в тестовом чате
# - окно новичка: approved_at + NEWCOMER_WINDOW_SECONDS (SQLite)
# - никаких удалений: этим занимается _watchdog_testpurge.py
from __future__ import annotations

import os
import sqlite3
import time
from typing import Iterable, Optional, Tuple

# Маркеры логов ищем по "ADMIN_NOTIFY"
_LOG_NAME = "support-join-guard"

# in-memory защита "только один раз"
_notified_once: set[Tuple[int,int]] = set()

def _env_flag(name: str, default: str="0") -> bool:
    return (os.getenv(name, default).lower() in {"1","true","yes","on"})

def _parse_admin_ids() -> list[int]:
    raw = os.getenv("ADMIN_IDS","").strip()
    ids: list[int] = []
    if raw:
        for tok in raw.replace(",", " ").split():
            try:
                ids.append(int(tok))
            except Exception:
                pass
    return ids

def _is_newcomer_now(uid: int, cid: int) -> Tuple[bool, Optional[int], int]:
    """
    Возвращает (is_new, newcomer_until_ts|None, now_ts)
    """
    db = os.getenv("SQLITE_PATH", "/opt/tgbots/bots/support/join_guard_state.db")
    win = int(os.getenv("NEWCOMER_WINDOW_SECONDS", "86400") or "86400")
    now = int(time.time())
    try:
        with sqlite3.connect(db, timeout=3.0) as conn:
            row = conn.execute(
                "SELECT approved_at FROM approvals WHERE user_id=? AND chat_id=?",
                (int(uid), int(cid))
            ).fetchone()
            if not row or row[0] is None:
                return (False, None, now)
            until = int(row[0]) + win
            return (now < until, until, now)
    except Exception:
        # тихо: оповещение — вспомогательное, не ломаем основной поток
        return (False, None, now)

async def _notify_admins_once(bot, m, log):
    """
    Отправляет уведомление всем ADMIN_IDS ровно один раз для пары (chat_id, user_id).
    Содержимое: пометка «новичок» и кусок текста сообщения (если есть).
    """
    uid = (m.from_user.id if m.from_user else 0) or 0
    cid = m.chat.id
    key = (cid, uid)
    if key in _notified_once:
        return
    _notified_once.add(key)

    admins = _parse_admin_ids()
    if not admins:
        log.info("ADMIN_NOTIFY: no ADMIN_IDS set; skipping")
        return

    # Склейка короткого превью — без медиа, без PII
    text_preview = ""
    try:
        if getattr(m, "text", None):
            t = (m.text or "").strip().replace("\n", " ")
            if len(t) > 140:
                t = t[:140] + "…"
            text_preview = t
        elif getattr(m, "caption", None):
            t = (m.caption or "").strip().replace("\n", " ")
            if len(t) > 140:
                t = t[:140] + "…"
            text_preview = t
    except Exception:
        text_preview = ""

    try:
        ulink = f"<a href=\"tg://user?id={uid}\">{uid}</a>"
    except Exception:
        ulink = str(uid)

    msg = f"🟡 <b>Новичок</b> в чате <code>{cid}</code>: {ulink}\n"
    if text_preview:
        msg += f"Сообщение: <i>{text_preview}</i>"

    for aid in admins:
        try:
            await bot.send_message(aid, msg, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            # не роняем обработку
            pass

def _extract_dispatcher_or_router(obj):
    """
    Возвращает объект, у которого есть .message.register (Dispatcher/Router).
    """
    if obj is None:
        return None
    try:
        msg = getattr(obj, "message", None)
        if msg is not None and hasattr(msg, "register"):
            return obj
    except Exception:
        return None
    return None

def _pick_reg_target(*args, **kwargs):
    # сначала из kwargs
    for k in ("router", "dp", "dispatcher"):
        tgt = kwargs.get(k)
        tgt = _extract_dispatcher_or_router(tgt)
        if tgt is not None:
            return tgt
    # затем из args
    for a in args:
        tgt = _extract_dispatcher_or_router(a)
        if tgt is not None:
            return tgt
    return None

def setup_newcomer_testonly(*args, **kwargs):
    # совместимость: alias
    return init_newcomer_testonly(*args, **kwargs)

def init_newcomer_testonly(*args, **kwargs):
    """
    Регистрирует хэндлер, который при первом сообщении от (TEST_USER_ID, TEST_CHAT_ID) в активном окне новичка
    отправит нотификацию ADMIN_IDS.
    """
    try:
        import logging
        from aiogram.types import Message
    except Exception:
        return None

    log = logging.getLogger(_LOG_NAME)

    # Флаг: включен ли тестовый режим
    if not _env_flag("NEWCOMER_TEST_ONLY", "0"):
        log.info("ADMIN_NOTIFY: test-only disabled; skip registering")
        return None

    # Пара теста
    try:
        TU = int(os.getenv("TEST_USER_ID", "0") or "0")
        TC = int(os.getenv("TEST_CHAT_ID", "0") or "0")
    except Exception:
        TU, TC = 0, 0

    if not (TU and TC):
        log.info("ADMIN_NOTIFY: TEST pair not set; skip registering")
        return None

    target = _pick_reg_target(*args, **kwargs)
    if target is None:
        # нет цели для регистрации — тихо выходим
        log.info("ADMIN_NOTIFY: no router/dispatcher to register; skip")
        return None

    async def _h(m: Message, bot):
        # входные пробы
        if not (m and m.chat and m.from_user):
            return
        if not (m.chat.id == TC and m.from_user.id == TU):
            return

        is_new, until, now = _is_newcomer_now(TU, TC)
        if not is_new:
            return

        await _notify_admins_once(bot, m, log)

    try:
        target.message.register(_h)  # aiogram v3 direct registration
        log.info("ADMIN_NOTIFY: handler registered via dp.message.register (v3)")
    except Exception:
        # на случай отличий — оставляем просто no-op, не ломаем поток
        pass

    return None
