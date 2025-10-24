import os, logging
from typing import Set

_cache: Set[str] = set()

def _flag(name: str) -> bool:
    v = (os.getenv(name, "0") or "0").strip().lower()
    return v in {"1", "true", "yes", "on"}

async def notify_once(m, until: int) -> None:
    """
    Отправляет админу ЛС только один раз на пару (chat_id:user_id) за жизнь процесса.
    Требует: NEWCOMER_NOTIFY_TO_CHAT=1 и ADMIN_IDS со списком ID.
    """
    if not _flag("NEWCOMER_NOTIFY_TO_CHAT"):
        return

    log = logging.getLogger("support-join-guard")

    chat_id = int(getattr(getattr(m, "chat", None), "id", 0) or 0)
    uid     = int(getattr(getattr(m, "from_user", None), "id", 0) or 0)
    mid     = int(getattr(m, "message_id", 0) or 0)

    key = f"{chat_id}:{uid}"
    if key in _cache:
        return

    raw = (os.getenv("ADMIN_IDS", "") or "").strip()
    admins = []
    for part in raw.replace(",", " ").split():
        p = part.strip()
        if p.isdigit():
            admins.append(int(p))

    log.info("TESTPURGE: notify start cid=%s uid=%s mid=%s admins=%s until=%s",
             chat_id, uid, mid, admins, until)

    if not admins:
        log.info("TESTPURGE: notify no admins configured")
        return

    txt = ("Newcomer message was deleted\n"
           f"chat: {chat_id}\n"
           f"user: {uid}\n"
           f"msg_id: {mid}\n"
           f"window until: {until}")

    sent = 0
    for aid in admins:
        try:
            await m.bot.send_message(chat_id=aid, text=txt, disable_notification=True)
            sent += 1
        except Exception as e:
            log.warning("TESTPURGE: notify fail admin=%s cid=%s uid=%s err=%r", aid, chat_id, uid, e)

    if sent > 0:
        _cache.add(key)
        log.info("TESTPURGE: notify sent=%s key=%s", sent, key)
    else:
        log.info("TESTPURGE: notify no-sends cid=%s uid=%s", chat_id, uid)
