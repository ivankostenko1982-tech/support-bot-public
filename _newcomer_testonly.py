from typing import Optional
from aiogram import Router
from aiogram.types import ChatMemberUpdated
import os, logging

def _is_test_pair(chat_id: int, user_id: int) -> bool:
    try:
        tc = int(os.getenv("TEST_CHAT_ID","0") or "0")
        tu = int(os.getenv("TEST_USER_ID","0") or "0")
        test_only = (os.getenv("NEWCOMER_TEST_ONLY","0").lower() in {"1","true","yes","on"})
        return bool(test_only and chat_id and user_id and chat_id==tc and user_id==tu)
    except Exception:
        return False

def setup_newcomer_testonly(router: Router, log: Optional[logging.Logger] = None) -> None:
    log = log or logging.getLogger("support-join-guard")

    @router.chat_member()
    async def _newcomer_log(event: ChatMemberUpdated):
        try:
            chat_id = int(getattr(event.chat, "id", 0) or 0)
            # В aiogram 3 у new_chat_member.user -> User; fallback на from_user
            user = getattr(getattr(event, "new_chat_member", None), "user", None)
            uid = int(getattr(user, "id", 0) or getattr(event.from_user, "id", 0) or 0)
        except Exception:
            chat_id, uid = 0, 0

        if not _is_test_pair(chat_id, uid):
            return

        old = getattr(event, "old_chat_member", None)
        new = getattr(event, "new_chat_member", None)

        def _st(x):
            # в aiogram 3 статус — Enum; берём .value либо str
            return getattr(getattr(x, "status", None), "value", str(getattr(x, "status", None)))

        log.info("NEWCOMER_TEST STEP1: ChatMemberUpdated chat=%s uid=%s %s->%s",
                 chat_id, uid, _st(old), _st(new))

# --- compat alias (star-args) for app.py calling with variable params ---
def setup_newcomer_testonly(*args, **kwargs):
    """Robust alias: accept any params from app.py, delegate to init_*."""
    try:
        router = args[0] if args else kwargs.get('router')
        return init_newcomer_testonly(router)
    except NameError:
        # init_* может отсутствовать — делаем no-op, чтобы не падать
        return None

