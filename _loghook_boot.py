# -*- coding: utf-8 -*-
"""
_loghook_boot: защитный loghook-хендлер для 'support-join-guard'.
Задачи:
- навесить совместимый обработчик на логгер (и переустанавливать, если handlers перетрут)
- распарсить 'TESTPURGE: deleted chat=... uid=... mid=... until=...' и отправить DM админу
- ASCII-текст, без эмодзи; один раз на пару chat:user за процесс
"""
from __future__ import annotations
import logging, os, re, threading, time, json, urllib.request, urllib.parse

_LOGGER_NAME = "support-join-guard"
_RE_DELETED = re.compile(
    r"TESTPURGE:\s*deleted.*?\bch(?:at)?[=:]\s*(-?\d+).*?\buid[=:]\s*(\d+).*?\bmid[=:]\s*(\d+).*?\buntil[=:]\s*(\d+)",
    re.IGNORECASE,
)

class _OnceNotifyCompatHandler(logging.Handler):
    _sent_keys: set[str] = set()
    _lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            return
        m = _RE_DELETED.search(msg or "")
        if not m:
            return
        cid, uid, mid, until = m.groups()
        key = f"{cid}:{uid}"
        with self._lock:
            if key in self._sent_keys:
                return
            self._sent_keys.add(key)
        try:
            _notify_admins_ascii(chat_id=int(cid), user_id=int(uid), msg_id=int(mid), until=int(until))
        except Exception:
            # не шумим, чтобы не ломать производственный логгер
            pass

def _parse_admin_ids() -> list[int]:
    raw = (os.getenv("ADMIN_IDS", "") or "").strip()
    out: list[int] = []
    for p in raw.replace(",", " ").split():
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out

def _notify_admins_ascii(*, chat_id: int, user_id: int, msg_id: int, until: int) -> None:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    admins = _parse_admin_ids()
    if not token or not admins:
        return
    log = logging.getLogger(_LOGGER_NAME)
    log.info("LOGHOOK: notify start cid=%s uid=%s mid=%s admins=%s until=%s", chat_id, user_id, msg_id, admins, until)

    text = (
        "Newcomer message deleted\n"
        f"chat: {chat_id}\n"
        f"user: {user_id}\n"
        f"msg_id: {msg_id}\n"
        f"window until: {until}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent = 0
    for aid in admins[:1]:  # шлём первому админу (минимально инвазивно)
        try:
            data = urllib.parse.urlencode({
                "chat_id": str(aid),
                "text": text,
                "disable_notification": "true",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=6) as resp:
                # читаем, но не логируем тело во избежание PII
                _ = resp.read()
            sent += 1
        except Exception as e:
            try:
                log.warning("LOGHOOK: notify fail admin=%s cid=%s uid=%s err=%r", aid, chat_id, user_id, e)
            except Exception:
                pass
    if sent:
        log.info("LOGHOOK: notify sent=1 key=%s:%s", chat_id, user_id)

def _ensure_handler() -> None:
    """Повесить наш хендлер, если он отсутствует."""
    log = logging.getLogger(_LOGGER_NAME)
    for h in list(getattr(log, "handlers", [])):
        if isinstance(h, _OnceNotifyCompatHandler):
            return
    h = _OnceNotifyCompatHandler()
    try:
        h.setLevel(logging.INFO)
    except Exception:
        pass
    log.addHandler(h)
    # Логируем факт установки — уже после addHandler, чтобы точно увидеть в журнале
    try:
        log.info("LOGHOOK: compat handler installed")
    except Exception:
        pass

def _guard_thread() -> None:
    """Фоновый сторож: если приложение пересобрало handlers — переустановить наш."""
    while True:
        try:
            _ensure_handler()
        except Exception:
            pass
        time.sleep(2.0)

# Инициализация при импорте (через .pth или прямой импорт в app.py)
try:
    _ensure_handler()
except Exception:
    pass
try:
    t = threading.Thread(target=_guard_thread, name="loghook-guard", daemon=True)
    t.start()
except Exception:
    pass

