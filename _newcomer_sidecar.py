# -*- coding: utf-8 -*-
# Newcomer sidecar: step1 — только логирование ChatMemberUpdated для тестовой пары
import os, logging

LOG = logging.getLogger('support-join-guard')

def _flag(v: str) -> bool:
    return str(v or "").lower() in {"1","true","yes","on"}

def _is_test_pair(chat_id: int, user_id: int) -> bool:
    try:
        tc = int(os.getenv("TEST_CHAT_ID", "0") or "0")
        tu = int(os.getenv("TEST_USER_ID", "0") or "0")
        return bool(chat_id and user_id and chat_id == tc and user_id == tu)
    except Exception:
        return False

def init_newcomer_sidecar(router):
    """
    Подключается из app.py ПОСЛЕ создания router.
    Если NEWCOMER_TEST_ONLY не включён — хендлер не регистрируем.
    """
    if not _flag(os.getenv("NEWCOMER_TEST_ONLY", "0")):
        LOG.info("NEWCOMER_SIDE: disabled (NEWCOMER_TEST_ONLY off)")
        return

    from aiogram.types import ChatMemberUpdated  # локальный импорт (безопасно для рантайма)

    @router.chat_member()
    async def _newcomer_step1_log(event: ChatMemberUpdated):
        try:
            chat_id = int(getattr(getattr(event, "chat", None), "id", 0) or 0)
            uid = 0
            newm = getattr(event, "new_chat_member", None)
            if newm is not None:
                user = getattr(newm, "user", None)
                uid = int(getattr(user, "id", 0) or 0)
            if not uid:
                uid = int(getattr(getattr(event, "from_user", None), "id", 0) or 0)
        except Exception:
            chat_id, uid = 0, 0

        # работаем ТОЛЬКО с тестовой парой
        if not _is_test_pair(chat_id, uid):
            return

        oldm = getattr(event, "old_chat_member", None)
        newm = getattr(event, "new_chat_member", None)

        def _st(x):
            try:
                s = getattr(x, "status", None)
                return getattr(s, "value", str(s))
            except Exception:
                return str(getattr(x, "status", None))

        LOG.info("NEWCOMER_SIDE STEP1: chat=%s uid=%s %s->%s", chat_id, uid, _st(oldm), _st(newm))
