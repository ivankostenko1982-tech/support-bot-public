# -*- coding: utf-8 -*-
# Compat adapter for test-purge: prefer app.newcomer_until() in test-only mode
import os, sqlite3, time, logging
log = logging.getLogger("support-join-guard")

def _flag(name: str) -> bool:
    v = (os.getenv(name, "0") or "0").strip().lower()
    return v in {"1","true","yes","on"}

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except Exception:
        return default

def resolve_newcomer_until(user_id: int, chat_id: int):
    """
    Return UNIX ts when newcomer window ends; None if not started.
    Prefer app.newcomer_until() when NEWCOMER_TEST_ONLY=1; else fallback to DB.
    """
    win = _get_int("NEWCOMER_WINDOW_SECONDS", 86400)
    # 1) test-only path via app.newcomer_until()
    if _flag("NEWCOMER_TEST_ONLY"):
        try:
            import importlib
            app = importlib.import_module("app")
            fn = getattr(app, "newcomer_until", None)
            if callable(fn):
                until = fn(int(user_id), int(chat_id))  # app may use its own store/logic
                log.info("TESTPURGE: until via app.newcomer_until source=app uid=%s chat=%s until=%s", user_id, chat_id, until)
                return until
        except Exception as e:
            log.warning("TESTPURGE: app.newcomer_until unavailable source=app err=%r", e)
    # 2) fallback to DB approvals
    try:
        db = os.getenv("SQLITE_PATH", "/opt/tgbots/bots/support/join_guard_state.db")
        with sqlite3.connect(db, timeout=3.0) as conn:
            row = conn.execute(
                "SELECT approved_at FROM approvals WHERE user_id=? AND chat_id=?",
                (int(user_id), int(chat_id)),
            ).fetchone()
            if not row or row[0] is None:
                log.info("TESTPURGE: newcomer window not started source=db uid=%s chat=%s", user_id, chat_id)
                return None
            until = int(row[0]) + int(win)
            log.info("TESTPURGE: until via approvals source=db uid=%s chat=%s until=%s", user_id, chat_id, until)
            return until
    except Exception:
        log.exception("TESTPURGE: resolve_newcomer_until DB error uid=%s chat=%s", user_id, chat_id)
        return None
