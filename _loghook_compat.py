# -*- coding: utf-8 -*-
"""
_loghook_compat: дополнительный логгер-хендлер, который слушает 'support-join-guard'
и реагирует на строку 'TESTPURGE: deleted ...' в ОБЕИХ формах:
  • "TESTPURGE: deleted ch<chat_id> uid=<uid> mid=<mid> now=<now> until=<until>"
  • "TESTPURGE: deleted chat=<chat_id> uid=<uid> mid=<mid> now=<now> until=<until>"
Отправляет разовый DM админам из ADMIN_IDS (ENV) при первом удалении пары <chat_id>:<uid>.
Никаких правок try/except в коде бота.
"""
from __future__ import annotations

import logging, os, re, time, json, urllib.request, urllib.parse, threading

_LOGGER = logging.getLogger("support-join-guard")

# Разные реальные форматы лога — поддержим оба.
# Примеры:
#   "TESTPURGE: deleted chat=-1002099408662 uid=6700029291 mid=829 now=1761299592 until=1761385992"
#   "TESTPURGE: deleted ch-1002099408662 uid=6700029291 mid=4089 now=... until=..."
_RE_DELETED = re.compile(
    r"TESTPURGE:\s+deleted\s+(?:chat=(?P<chat>-?\d+)|ch(?P<ch>-?\d+))\s+uid=(?P<uid>\d+)\s+mid=(?P<mid>\d+)\s+now=(?P<now>\d+)\s+until=(?P<until>\d+)"
)

def _flag(name: str) -> bool:
    v = (os.getenv(name, "0") or "0").strip().lower()
    return v in {"1", "true", "yes", "on"}

def _admin_ids() -> list[int]:
    raw = (os.getenv("ADMIN_IDS", "") or "").replace(",", " ")
    return [int(x) for x in raw.split() if x.isdigit()]

def _bot_token() -> str:
    return (os.getenv("BOT_TOKEN") or "").strip()

# Разовый кеш "chat:uid" -> True
_once_cache: set[str] = set()
_cache_lock = threading.Lock()

def _send_dm(aid: int, text: str) -> bool:
    token = _bot_token()
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": aid,
        "text": text,
        "disable_notification": True,
    }
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            # успешный ответ — ok:true
            payload = json.loads(resp.read().decode("utf-8", "replace"))
            return bool(payload.get("ok"))
    except Exception:
        return False

class _CompatOnceNotifyHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.setLevel(logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            return
        m = _RE_DELETED.search(msg or "")
        if not m:
            return

        chat = m.group("chat") or m.group("ch")
        uid  = m.group("uid")
        mid  = m.group("mid")
        until = m.group("until")

        try:
            cid = int(chat)
            u   = int(uid)
        except Exception:
            return

        # Флаг в ENV должен быть включён
        if not _flag("NEWCOMER_NOTIFY_TO_CHAT"):
            return

        key = f"{cid}:{u}"
        with _cache_lock:
            if key in _once_cache:
                return
            _once_cache.add(key)

        admins = _admin_ids()
        if not admins:
            _LOGGER.info("LOGHOOK: notify skip (no admins) cid=%s uid=%s", cid, u)
            return

        _LOGGER.info("LOGHOOK: notify start cid=%s uid=%s mid=%s admins=%s until=%s", cid, u, mid, admins, until)

        # Текст строго ASCII, без эмодзи/суррогатов.
        text = (
            "Newcomer message deleted\n"
            f"chat: {cid}\n"
            f"user: {u}\n"
            f"msg_id: {mid}\n"
            f"window until: {until}"
        )

        sent = 0
        for aid in admins:
            if _send_dm(aid, text):
                sent += 1

        if sent:
            _LOGGER.info("LOGHOOK: notify sent=1 key=%s", key)
        else:
            _LOGGER.info("LOGHOOK: notify no-sends key=%s", key)

def _install_handler() -> None:
    lg = _LOGGER
    # Не плодим дубликаты.
    for h in lg.handlers:
        if isinstance(h, _CompatOnceNotifyHandler):
            return
    lg.addHandler(_CompatOnceNotifyHandler())

# Автоустановка при импорте.
try:
    _install_handler()
    _LOGGER.info("LOGHOOK: compat handler installed")
except Exception:
    # Тихо игнорируем — не ломаем приложение.
    pass
