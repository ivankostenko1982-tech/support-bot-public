from __future__ import annotations
##
# BEGIN PATCH:newcomer_until
def newcomer_until(user_id: int, chat_id: int) -> int | None:
    """Return UNIX timestamp until which user is considered a newcomer, or None if not approved yet."""
    import sqlite3, logging
    log = logging.getLogger("support-join-guard")
    try:
        with sqlite3.connect(SQLITE_PATH, timeout=3.0) as conn:
            cur = conn.execute("SELECT approved_at FROM approvals WHERE user_id=? AND chat_id=?", (int(user_id), int(chat_id)))
            row = cur.fetchone()
            if not row or row[0] is None:
                return None
            return int(row[0]) + int(NEWCOMER_WINDOW_SECONDS)
    except Exception:
        log.exception("newcomer_until: failed user_id=%s chat_id=%s", user_id, chat_id)
        return None
# END PATCH:newcomer_until
try:
    import _watchdog_testuser as _wd
    HAS_WD = True
except Exception as _e:
    HAS_WD = False
#!/usr/bin/env python3


# --- safe stub: avoid NameError from _removed_is_newcomer ---
def _removed_is_newcomer(user_id: int, chat_id: int) -> bool:
    """Test-only gate: treat as 'newcomer' ONLY for (TEST_USER_ID, TEST_CHAT_ID) when NEWCOMER_TEST_ONLY=1."""
    import os
    test_only = (os.getenv("NEWCOMER_TEST_ONLY","0").lower() in {"1","true","yes","on"})
    tu = int(os.getenv("TEST_USER_ID","0") or "0")
    tc = int(os.getenv("TEST_CHAT_ID","0") or "0")
    if test_only:
        return bool(user_id and chat_id and int(user_id)==tu and int(chat_id)==tc)
    return False


import os, time, sqlite3, asyncio, logging, html, hmac, re, platform
from dataclasses import dataclass
from contextlib import closing
from typing import Optional, List, Tuple, Set
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
try:
    import _watchdog_testuser as _wd
    HAS_WD = True
except Exception as _e:
    HAS_WD = False
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType, ChatMemberStatus
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    ChatJoinRequest, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberAdministrator, ChatMemberOwner, ChatMember, ChatPermissions, ChatMemberUpdated
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ChatMemberStatus

# --- Bootstrap: env & DB checks (injected) ---
import os, sys, sqlite3, time, logging, pathlib

from aiogram.exceptions import TelegramBadRequest

async def _safe_approve(bot, chat_id: int, user_id: int) -> bool:
    import logging
    log = logging.getLogger("support-join-guard")
    try:
        await bot.approve_chat_join_request(chat_id, user_id)
        log.info("approve: ok user_id=%s chat_id=%s", user_id, chat_id)
        return True
    except TelegramBadRequest as e:
        # уже одобрено/неактуально — не роняем бота
        log.warning("approve: badrequest user_id=%s chat_id=%s err=%s", user_id, chat_id, e)
        return False
    except Exception:
        log.exception("approve: failed user_id=%s chat_id=%s", user_id, chat_id)
        return False


def _load_support_env():
    # prefer explicit path; default system path
    env_path = os.environ.get("SUPPORT_ENV_PATH", "/etc/tgbots/support.env")
    try:
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    # do not overwrite already-set env
                    if k and (k not in os.environ):
                        os.environ[k] = v
    except Exception as e:
        print(f"[BOOT] WARN: cannot load env from {env_path}: {e}", file=sys.stderr)

def _ensure_sqlite_and_schema():
    # SQLITE_PATH used by existing code; fallback to JOIN_GUARD_DB_PATH
    db_path = os.environ.get("SQLITE_PATH") or os.environ.get("JOIN_GUARD_DB_PATH")
    if not db_path:
        # default to historical path
        db_path = "/opt/tgbots/bots/support/join_guard_state.db"
        os.environ["SQLITE_PATH"] = db_path
    p = pathlib.Path(db_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[BOOT] ERROR: cannot create DB directory {p.parent}: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        con = sqlite3.connect(db_path, timeout=3.0)
        cur = con.cursor()
        # Minimal tables commonly referenced by support-join-guard
        cur.execute("""CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY,
            value TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS approvals (
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            approved_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, chat_id)
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS pending_requests (
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            payload TEXT,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, chat_id)
        )""")
        con.commit()
        con.close()
    except Exception as e:
        print(f"[BOOT] ERROR: cannot init sqlite {db_path}: {e}", file=sys.stderr)
        sys.exit(1)


def _drop_newcomer_columns_if_present():
    """If approvals.newcomer_until exists, rebuild table without it."""
    from contextlib import closing
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(approvals)")}
        if "newcomer_until" in cols:
            conn.execute("BEGIN")
            # Create new table without newcomer_until, keep NOT NULL on approved_at for your legacy logic;
            # if you want approved_at nullable, change NOT NULL to NULL here.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals_new (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    approved_at INTEGER NOT NULL,
                    PRIMARY KEY(user_id, chat_id)
                )
            """)
            # Copy data (fallback: absent newcomer_until ignored)
            try:
                conn.execute("INSERT INTO approvals_new(user_id, chat_id, approved_at) SELECT user_id, chat_id, COALESCE(NULLIF(approved_at, 0), CAST(strftime('%s','now') AS INTEGER)) FROM approvals")
            except Exception:
                # If approved_at is NULL in some rows, coerce to now to satisfy NOT NULL
                conn.execute("INSERT INTO approvals_new(user_id, chat_id, approved_at) SELECT user_id, chat_id, COALESCE(approved_at, CAST(strftime('%s','now') AS INTEGER)) FROM approvals")
            conn.execute("DROP TABLE approvals")
            conn.execute("ALTER TABLE approvals_new RENAME TO approvals")
            conn.commit()


def _validate_core_env():
    ok = True
    token = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("[BOOT] ERROR: BOT_TOKEN is not set (or TELEGRAM_BOT_TOKEN).", file=sys.stderr)
        ok = False
    # window for newcomers
    try:
        int(os.environ.get("NEWCOMER_WINDOW_SECONDS", "86400"))
    except Exception:
        print("[BOOT] WARN: NEWCOMER_WINDOW_SECONDS invalid; using default 86400.", file=sys.stderr)
        os.environ["NEWCOMER_WINDOW_SECONDS"] = "86400"
    if not ok:
        sys.exit(1)

def bootstrap_dependencies():
    _load_support_env()
    _ensure_sqlite_and_schema()
    _drop_newcomer_columns_if_present()
    _validate_core_env()
# --- End bootstrap ---

def _db_integrity_check_and_repair():
    """
    Validate and lightly repair tables used by join-guard.
    - PRAGMA integrity_check
    - approvals: drop rows with NULLs; clamp approved_at to sane range [0, now+30d]
    - pending_requests: ensure created_at sane; drop rows with NULL ids
    - settings: drop rows with empty id
    """
    import time, json

import os

def utils_path(name: str) -> str:
    """Join UTILS_DIR and file name safely."""
    base = globals().get("UTILS_DIR", "/opt/tgbots/utils")
    return os.path.join(base, name)
    now = int(time.time())
    max_future = now + 30*24*3600  # 30 days into the future is considered suspicious
    db_path = os.environ.get("SQLITE_PATH") or os.environ.get("JOIN_GUARD_DB_PATH") or "/opt/tgbots/bots/support/join_guard_state.db"
    try:
        con = sqlite3.connect(db_path, timeout=3.0)
        cur = con.cursor()

        # 1) Integrity check
        try:
            rows = list(cur.execute("PRAGMA integrity_check"))
            ok_rows = [r[0] for r in rows if isinstance(r, tuple) and r]
            if not ok_rows or ok_rows[0].lower() != "ok":
                print(f"[DBCHK] WARN integrity_check: {ok_rows[:3]}")
        except Exception as e:
            print(f"[DBCHK] WARN: integrity_check failed: {e}")

        # 2) approvals sanity
        cur.execute("""CREATE TABLE IF NOT EXISTS approvals(
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            approved_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, chat_id)
        )""")
        # Drop broken null-key rows
        cur.execute("DELETE FROM approvals WHERE user_id IS NULL OR chat_id IS NULL")
        # Fix approved_at non-integers / NULL
        cur.execute("UPDATE approvals SET approved_at = ? WHERE approved_at IS NULL", (now,))
        # Clamp too-future values
        cur.execute("UPDATE approvals SET approved_at = ? WHERE approved_at > ?", (now, max_future))
        # Clamp negatives
        cur.execute("UPDATE approvals SET approved_at = 0 WHERE approved_at < 0")

        # 3) pending_requests sanity
        cur.execute("""CREATE TABLE IF NOT EXISTS pending_requests(
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            payload TEXT,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, chat_id)
        )""")
        cur.execute("DELETE FROM pending_requests WHERE user_id IS NULL OR chat_id IS NULL")
        cur.execute("UPDATE pending_requests SET created_at = ? WHERE created_at IS NULL", (now,))
        cur.execute("UPDATE pending_requests SET created_at = ? WHERE created_at > ?", (now, max_future))
        cur.execute("UPDATE pending_requests SET created_at = 0 WHERE created_at < 0")
        # If payload too large, truncate to 64KB to avoid bloating DB
        try:
            cur.execute("UPDATE pending_requests SET payload = substr(payload, 1, 65536) WHERE payload IS NOT NULL AND length(payload) > 65536")
        except Exception:
            pass

        # 4) settings sanity
        cur.execute("""CREATE TABLE IF NOT EXISTS settings(
            id TEXT PRIMARY KEY,
            value TEXT
        )""")
        cur.execute("DELETE FROM settings WHERE id IS NULL OR trim(id) = ''")

        con.commit()
        con.close()
        print("[DBCHK] OK: sanity pass complete")
    except Exception as e:
        print(f"[DBCHK] ERROR: {e}")




# Optional systemd watchdog
try:
    from sdnotify import SystemdNotifier  # type: ignore
except Exception:  # pragma: no cover
    SystemdNotifier = None  # type: ignore

# ── Meta / version ──────────────────────────────────────────────────────────────
APP_NAME = "support-join-guard"
APP_VERSION = os.getenv("APP_VERSION", "2.1.0")  # bump when logic changes
START_MONO = time.monotonic()
START_TS = int(time.time())

# ── Logging ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger(APP_NAME)

# ── ENV helpers ─────────────────────────────────────────────────────────────────
def _get_env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return int(default)
    try:
        return int(raw.strip())
    except Exception:
        raise SystemExit(f"ENV {key} must be integer, got: {raw!r}")

def _parse_id_list(raw: str) -> Set[int]:
    ids: Set[int] = set()
    if not raw or not raw.strip():
        return ids
    for token in raw.replace(",", " ").split():
        if "=" in token:
            log.warning("Ignoring non-id token in list: %r", token); continue
        try:
            ids.add(int(token))
        except ValueError:
            log.warning("Skipping malformed ID: %r", token)
    return ids

# ── ENV ─────────────────────────────────────────────────────────────────────────
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
UTILS_DIR = os.getenv("UTILS_DIR", "/opt/tgbots/utils")
VERIFY_SECRET = (os.getenv("VERIFY_SECRET") or "").strip()
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is required in /etc/tgbots/support.env")
if not VERIFY_SECRET:
    raise SystemExit("VERIFY_SECRET is required in /etc/tgbots/support.env")

JOIN_REQUEST_TTL = _get_env_int("JOIN_REQUEST_TTL", 600)
SQLITE_PATH = os.getenv("SQLITE_PATH", "/opt/tgbots/bots/support/join_guard_state.db")
UTILS_DIR = os.getenv("UTILS_DIR", "/opt/tgbots/utils")
ENV_DELETE_SYSTEM_MESSAGES = os.getenv("DELETE_SYSTEM_MESSAGES", "false").lower() in {"1","true","yes","on"}
EXPIRE_SWEEP_INTERVAL = _get_env_int("EXPIRE_SWEEP_INTERVAL", 20)
ADMIN_CONTACT_OVERRIDE = (os.getenv("ADMIN_CONTACT_OVERRIDE") or "").strip().lstrip("@")
NEWCOMER_WINDOW_SECONDS = _get_env_int("NEWCOMER_WINDOW_SECONDS", 24*60*60)
ENV_LOCKDOWN_NONADMIN_BOTS = os.getenv("LOCKDOWN_NONADMIN_BOTS", "true").lower() in {"1","true","yes","on"}
AGGRESSIVE_CHANNEL_ANTILINK = os.getenv("AGGRESSIVE_CHANNEL_ANTILINK", "false").lower() in {"1","true","yes","on"}

# 🔎 Тестовый чат и флаг тотального трассирования
TEST_CHAT_ID = int(os.getenv("TEST_CHAT_ID", "0") or "0")
TEST_USER_ID = int(os.getenv("TEST_USER_ID", "0") or "0")
TRACE_TEST_CHAT = os.getenv("TRACE_TEST_CHAT", "0").lower() in {"1","true","yes","on"}

log.info(
    "BOOT: app.py loaded file=%s SQLITE_PATH=%s WINDOW=%s",
    __file__,
    SQLITE_PATH if "SQLITE_PATH" in globals() else os.getenv("SQLITE_PATH"),
    os.getenv("NEWCOMER_WINDOW_SECONDS","86400"),
)

ALLOWLIST = _parse_id_list(os.getenv("TARGET_CHAT_IDS", "")) | _parse_id_list(os.getenv("TARGET_CHAT_ID", ""))
if ALLOWLIST:
    log.info("Allowlist enabled for chat_ids=%s", sorted(ALLOWLIST))
else:
    log.info("Allowlist is empty — bot will accept join requests from ANY chat")

ADMIN_IDS = _parse_id_list(os.getenv("ADMIN_IDS", ""))
if ADMIN_IDS:
    log.info("Static admin ids set: %s", sorted(ADMIN_IDS))

# ── Bot/Dispatcher/Router ───────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
# ВАЖНО: отдельный роутер для команд — подключаем ПЕРВЫМ, чтобы команды имели приоритет
cmd_router = Router(name="commands")

router = Router(name="main")
# from _snapshot_guard import enforce_snapshot as _enf_snap
# _enf_snap(app_file=__file__, meta_dir="/opt/tgbots/utils/snapshots")

# [SAFE-PATCH MARKER] no-op marker after router init


dp.include_router(cmd_router)

dp.include_router(router)


# ── App State ───────────────────────────────────────────────────────────────────
@dataclass
class AppState:
    sys_clean_enabled: bool = False
    me_id: Optional[int] = None
    me_username: Optional[str] = None
    botlock_enabled: bool = True
    diag_enabled: bool = False  # toggle via /diag

state = AppState()

# ── SQLite ──────────────────────────────────────────────────────────────────────
db_dir = os.path.dirname(SQLITE_PATH) or "."
os.makedirs(db_dir, exist_ok=True)

def init_db() -> None:
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_requests (
                user_id      INTEGER NOT NULL,
                chat_id      INTEGER NOT NULL,
                chat_title   TEXT,
                requested_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, chat_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS approvals (
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                approved_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, chat_id)
            )
            """
        )
        conn.commit()

def db_get_setting(key: str) -> Optional[str]:
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

def db_set_setting(key: str, value: str) -> None:
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()

def set_pending(user_id: int, chat_id: int, chat_title: str) -> None:
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        conn.execute(
            """
            INSERT INTO pending_requests(user_id, chat_id, chat_title, requested_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                chat_title=excluded.chat_title,
                requested_at=excluded.requested_at
            """,
            (user_id, chat_id, chat_title, int(time.time())),
        )
        conn.commit()

def clear_pending(user_id: int, chat_id: int) -> None:
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        conn.execute("DELETE FROM pending_requests WHERE user_id=? AND chat_id=?", (user_id, chat_id))
        conn.commit()

def record_approval(user_id: int, chat_id: int) -> None:
    """
    Фиксирует одобрение пользователя в чате:
    - если записи ещё нет, создаёт её
    - если есть, обновляет approved_at на текущее время
    """
    ts = int(time.time())
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        conn.execute(
            """
            INSERT INTO approvals(user_id, chat_id, approved_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                approved_at=excluded.approved_at
            """,
            (user_id, chat_id, ts),
        )
        conn.commit()

# ── Admin & bot rights checks ───────────────────────────────────────────────────
async def _get_chat_member_safe(chat_id: int, user_id: int) -> Optional['ChatMember']:
    try:
        return await bot.get_chat_member(chat_id, user_id)
    except Exception as e:
        log.debug("get_chat_member failed chat=%s uid=%s: %s", chat_id, user_id, e)
        return None

def _is_admin_cm(cm: Optional['ChatMember']) -> bool:
    return isinstance(cm, (ChatMemberAdministrator, ChatMemberOwner))

async def is_user_admin(user_id: Optional[int], chat_id_context: Optional[int] = None) -> bool:
    if user_id is None:
        return False
    if user_id in ADMIN_IDS:
        return True
    if chat_id_context is not None:
        cm = await _get_chat_member_safe(chat_id_context, user_id)
        if _is_admin_cm(cm):
            return True
    # Only current chat matters (plus explicit ADMIN_IDS). No cross-chat admin inference.
    return False

async def log_bot_rights(chat_id: int) -> None:
    try:
        me = await bot.get_me()
        cm = await _get_chat_member_safe(chat_id, me.id)
        if cm is None:
            log.warning("BOT-RIGHTS: cannot read bot ChatMember in chat=%s", chat_id)
            return
        role = getattr(cm, "status", "unknown")
        can_send = True
        if role == "restricted":
            perms = getattr(cm, "permissions", None)
            if isinstance(perms, ChatPermissions):
                can_send = bool(getattr(perms, "can_send_messages", False))
        log.info("BOT-RIGHTS: chat=%s role=%s can_send=%s", chat_id, role, can_send)
        if not can_send:
            log.warning("BOT-RIGHTS: bot cannot send messages to chat=%s — проверьте права/ограничения", chat_id)
    except Exception as e:
        log.debug("BOT-RIGHTS: failed for chat=%s: %s", chat_id, e)

async def ensure_admin(m: 'Message') -> bool:
    chat_id_ctx = m.chat.id if m.chat else None
    user_id = m.from_user.id if m.from_user else None
    sender_chat_id = m.sender_chat.id if m.sender_chat else None
    if chat_id_ctx:
        await log_bot_rights(chat_id_ctx)
    if sender_chat_id and chat_id_ctx and sender_chat_id == chat_id_ctx:
        return True
    ok = await is_user_admin(user_id, chat_id_ctx)
    log.debug("ensure_admin: chat=%s uid=%s -> %s", chat_id_ctx, user_id, ok)
    return ok

# ── HMAC helpers ────────────────────────────────────────────────────────────────
def _sig16(payload: str) -> str:
    import hashlib
    mac = hmac.new(VERIFY_SECRET.encode('utf-8'), payload.encode('utf-8'), digestmod=hashlib.sha256).digest()
    return mac[:8].hex()

def build_verify_cbdata(chat_id: int, user_id: int) -> str:
    ts = int(time.time())
    core = f"{chat_id}:{user_id}:{ts}"
    sig = _sig16(core)
    return f"v:{chat_id}:{ts}:{sig}"

def parse_and_verify_cbdata(cbdata: str, actual_user_id: int) -> tuple[bool, Optional[int], Optional[str]]:
    if not cbdata.startswith("v:"):
        return (False, None, "Некорректные данные")
    try:
        _, chat_id_s, ts_s, sig = cbdata.split(":", 3)
        chat_id = int(chat_id_s); ts = int(ts_s)
    except Exception:
        return (False, None, "Некорректные данные")
    if int(time.time()) - ts > JOIN_REQUEST_TTL + 30:
        return (False, None, "Время действия истекло")
    core = f"{chat_id}:{actual_user_id}:{ts}"
    if _sig16(core) != sig:
        return (False, None, "Подпись не сходится")
    return (True, chat_id, None)

# ── UI helpers ──────────────────────────────────────────────────────────────────
def verify_keyboard(chat_id: int, user_id: int) -> 'InlineKeyboardMarkup':
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Я человек (подтвердить)", callback_data=build_verify_cbdata(chat_id, user_id))
    kb.button(text="🔄 Обновить", callback_data="refresh")
    return kb.as_markup()

def requests_keyboard(user_id: int, requests: List[Tuple[int, str, int]]) -> 'InlineKeyboardMarkup':
    kb = InlineKeyboardBuilder()
    for chat_id, chat_title, _ in requests:
        label = f"Подтвердить вступление в «{chat_title or chat_id}»"
        kb.button(text=label, callback_data=build_verify_cbdata(chat_id, user_id))
    kb.button(text="🔄 Обновить", callback_data="refresh")
    return kb.as_markup()

async def get_public_admin_mention(chat_id: int) -> Optional[str]:
    if ADMIN_CONTACT_OVERRIDE:
        uname = ADMIN_CONTACT_OVERRIDE
        return f'<a href="https://t.me/{uname}">@{uname}</a>'
    try:
        admins: List['ChatMember'] = await bot.get_chat_administrators(chat_id)
    except Exception as e:
        log.debug("get_chat_administrators failed for chat %s: %s", chat_id, e)
        return None
    for cm in admins:
        try:
            is_admin = isinstance(cm, (ChatMemberAdministrator, ChatMemberOwner))
            if not is_admin:
                continue
            if isinstance(cm, ChatMemberAdministrator) and getattr(cm, "is_anonymous", False):
                continue
            user = getattr(cm, "user", None)
            if not user or user.is_bot:
                continue
            uname = user.username
            if not uname:
                continue
            return f'<a href="https://t.me/{uname}">@{uname}</a>'
        except Exception:
            continue
    return None

async def get_group_open_url(chat_id: int) -> Optional[str]:
    try:
        chat = await bot.get_chat(chat_id)
        if getattr(chat, "username", None):
            return f"https://t.me/{chat.username}"
    except Exception as e:
        log.debug("get_chat failed for %s: %s", chat_id, e)
    try:
        expire = int((datetime.utcnow() + timedelta(minutes=30)).timestamp())
        link = await bot.create_chat_invite_link(
            chat_id=chat_id,
            name="auto-open",
            expire_date=expire,
            member_limit=1,
            creates_join_request=False,
        )
        return link.invite_link
    except Exception as e:
        log.debug("create_chat_invite_link failed for %s: %s", chat_id, e)
        return None

def open_group_keyboard(url: str, title: Optional[str] = None) -> 'InlineKeyboardMarkup':
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text=title or "Перейти в группу", url=url))
    return kb.as_markup()

# ── Filters ─────────────────────────────────────────────────────────────────────
group_msg_filter = (F.chat.type == ChatType.SUPERGROUP) | (F.chat.type == ChatType.GROUP)

# === Newcomer hard gate: delete ANY message within window and notify ===
async def _notify_newcomer_user(user_id: int, window_seconds: int, chat_title: str | None):
    try:
        hours = max(1, int(window_seconds // 3600))
        txt = (
            f"⚠️ Антиспам: в ближайшие {hours} ч. ваши сообщения "
            + (f"в группе «{chat_title}» " if chat_title else "в группе ")
            + "будут автоматически удаляться. Это защита от спама для новых участников."
        )
        await bot.send_message(user_id, txt, disable_web_page_preview=True)
        log.info("AntiSpam(Newcomer): DM sent to user uid=%s", user_id)
    except Exception as e:
        log.debug("AntiSpam(Newcomer): DM to user uid=%s failed: %s", user_id, e)

async def _notify_admins_about_deletion(chat_id: int, user_id: int, username: str | None, chat_title: str | None):
    try:
        admins = await bot.get_chat_administrators(chat_id)
    except Exception as e:
        log.debug("AntiSpam(Newcomer): get_chat_administrators failed chat=%s err=%s", chat_id, e)
        return
    uref = f"@{username}" if username else str(user_id)
    ctitle = f"«{chat_title}»" if chat_title else str(chat_id)
    msg = f"🧹 AntiSpam: удалено сообщение у новичка {uref} в чате {ctitle}. Проверьте активность пользователя."
    for cm in admins:
        u = getattr(cm, "user", None)
        if not u or getattr(u, "is_bot", False):
            continue
        try:
            await bot.send_message(u.id, msg, disable_web_page_preview=True)
        except Exception as e:
            log.debug("AntiSpam(Newcomer): DM to admin %s failed: %s", u.id if u else "-", e)

async def _newcomer_delete_and_notify(m: 'Message'):
    u = m.from_user
    if not u or u.is_bot:
        return
    if not _removed_is_newcomer(u.id, m.chat.id):
        return
    # allow admins to bypass even if 'newcomer' accidentally set
    if await is_user_admin(u.id, m.chat.id):
        return
    chat_title = getattr(m.chat, "title", None)
    try:
        await m.delete()
        log.info("AntiSpam(Newcomer): deleted ANY msg chat=%s mid=%s uid=%s", m.chat.id, m.message_id, u.id)
    except Exception as e:
        log.warning("AntiSpam(Newcomer): delete failed chat=%s mid=%s err=%s", m.chat.id, m.message_id, e)
        return
    # notifications (best-effort)
    try:
        await _notify_newcomer_user(u.id, NEWCOMER_WINDOW_SECONDS, chat_title)
    except Exception:
        pass
    try:
        await _notify_admins_about_deletion(m.chat.id, u.id, getattr(u, "username", None), chat_title)
    except Exception:
        pass

@router.message(group_msg_filter)
async def newcomer_gate_delete_all(m: 'Message'):
    await _newcomer_delete_and_notify(m)

@router.edited_message(group_msg_filter)
async def newcomer_gate_delete_all_edited(m: 'Message'):
    await _newcomer_delete_and_notify(m)


def _has_bot_command(m: 'Message') -> bool:
    for e in (m.entities or []) + (m.caption_entities or []):
        if getattr(e, "type", None) == "bot_command":
            return True
    return False

# ── Command handlers (PRIORITY router) ─────────────────────────────────────────
def _log_cmd_ignored(m: 'Message', cmd: str):
    uid = m.from_user.id if m.from_user else None
    uname = f"@{m.from_user.username}" if (m.from_user and m.from_user.username) else "-"
    log.info("CMD %s ignored: user is not admin in chat=%s uid=%s %s", cmd, getattr(m.chat, "id", None), uid, uname)

@cmd_router.message(Command("health"))
async def health(m: 'Message'):
    log.debug("HEALTH handler entered: chat=%s uid=%s", getattr(m.chat, "id", None), getattr(m.from_user, "id", None))
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/health")
        return
    if m.chat:
        await log_bot_rights(m.chat.id)
    await m.answer("ok")

@cmd_router.message(Command("ping"))
async def ping(m: 'Message'):
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/ping"); return
    # измеряем round-trip API-вызовом get_me()
    t0 = time.monotonic()
    try:
        await bot.get_me()
    except Exception:
        pass
    dt = int((time.monotonic() - t0)*1000)
    await m.answer(f"pong {dt}ms")

@cmd_router.message(Command("version"))
async def version_cmd(m: 'Message'):
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/version"); return
    import aiogram
    uptime = int(time.monotonic() - START_MONO)
    up_h = uptime // 3600
    up_m = (uptime % 3600) // 60
    up_s = uptime % 60
    await m.answer(
        "🧩 Версия бота\n"
        f"- app: {APP_NAME} {APP_VERSION}\n"
        f"- aiogram: {aiogram.__version__}\n"
        f"- python: {platform.python_version()}\n"
        f"- uptime: {up_h:02d}:{up_m:02d}:{up_s:02d}\n"
        f"- sys_clean: {state.sys_clean_enabled}\n"
        f"- botlock: {state.botlock_enabled}\n"
        f"- diag: {state.diag_enabled}"
    )

@cmd_router.message(Command("allowlist"))
async def allowlist_cmd(m: 'Message'):
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/allowlist"); return
    if ALLOWLIST:
        await m.answer("Разрешённые chat_id:\n" + "\n".join(str(i) for i in sorted(ALLOWLIST)))
    else:
        await m.answer("Разрешённые chat_id не заданы (бот принимает заявки из любых чатов).")

@cmd_router.message(Command("sysclean"))
async def sysclean_cmd(m: 'Message'):
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/sysclean"); return
    parts = (m.text or "").split()
    if len(parts) == 1:
        origin = "override(БД)" if db_get_setting("sysclean_enabled") is not None else "env"
        await m.answer(
            "Очистка системных сообщений сейчас "
            f"{'включена' if state.sys_clean_enabled else 'выключена'} "
            f"(источник: {origin}).\n"
            "Используй: /sysclean on  или  /sysclean off"
        ); return
    arg = parts[1].strip().lower()
    if arg in {"on", "off"}:
        enabled = (arg == "on")
        db_set_setting("sysclean_enabled", "true" if enabled else "false")
        state.sys_clean_enabled = enabled
        await m.answer(
            "Готово. Очистка системных сообщений теперь "
            f"{'включена' if enabled else 'выключена'} (сохранено, переживёт рестарт)."
        )

@cmd_router.message(Command("botlock"))
async def botlock_cmd(m: 'Message'):
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/botlock"); return
    parts = (m.text or "").split()
    if len(parts) == 1:
        origin = "override(БД)" if db_get_setting("botlock_enabled") is not None else "env"
        await m.answer(
            "Блокировка не-админ-ботов сейчас "
            f"{'включена' if state.botlock_enabled else 'выключена'} "
            f"(источник: {origin}).\n"
            "Используй: /botlock on  или  /botlock off"
        ); return
    arg = parts[1].strip().lower()
    if arg in {"on", "off"}:
        enabled = (arg == "on")
        db_set_setting("botlock_enabled", "true" if enabled else "false")
        state.botlock_enabled = enabled
        await m.answer(
            "Готово. Блокировка не-админ-ботов теперь "
            f"{'включена' if enabled else 'выключена'} (сохранено, переживёт рестарт)."
        )

@cmd_router.message(Command("diag"))
async def diag_cmd(m: 'Message'):
    if not await ensure_admin(m):
        _log_cmd_ignored(m, "/diag"); return
    parts = (m.text or "").split()
    if len(parts) == 1:
        await m.answer(
            "Диагностика логов сейчас "
            f"{'включена' if state.diag_enabled else 'выключена'}.\n"
            "Используй: /diag on | /diag off"
        ); return
    arg = parts[1].strip().lower()
    if arg in {"on", "off"}:
        enabled = (arg == "on")
        db_set_setting("diag_enabled", "true" if enabled else "false")
        state.diag_enabled = enabled
        await m.answer(f"Диагностика логов {'включена' if enabled else 'выключена'} (сохранено).")

# Страховка: если по какой-то причине Command(...) не сработал
@cmd_router.message(group_msg_filter)
async def _health_text_alias(m: 'Message'):
    t = (m.text or "").strip()
    if not t.startswith("/"):
        return
    uname = (state.me_username or "").lower() if hasattr(state, "me_username") else ""
    head = t.split()[0].lower()
    variants = {"/health", f"/health@{uname}"} if uname else {"/health"}
    if head in variants:
        await health(m)

# Диагностический логгер команд
@cmd_router.message(group_msg_filter)
async def _log_any_commands(m: 'Message'):
    if not _has_bot_command(m):
        return
    uid = m.from_user.id if m.from_user else None
    uname = f"@{m.from_user.username}" if (m.from_user and m.from_user.username) else "-"
    txt = (m.text or m.caption or "") or ""
    cmds = []
    for e in (m.entities or []) + (m.caption_entities or []):
        if getattr(e, "type", None) == "bot_command":
            try:
                cmds.append(txt[e.offset:e.offset+e.length])
            except Exception:
                pass
    log.info("COMMAND seen: chat=%s uid=%s %s cmds=%s text=%r", getattr(m.chat, "id", None), uid, uname, cmds, txt[:400])

# ── Service cleaner ────────────────────────────────────────────────────────────
service_filter = (
    (F.chat.type == ChatType.GROUP) | (F.chat.type == ChatType.SUPERGROUP)
) & (
    F.new_chat_members | F.left_chat_member | F.new_chat_title | F.new_chat_photo |
    F.delete_chat_photo | F.group_chat_created | F.supergroup_chat_created |
    F.migrate_to_chat_id | F.migrate_from_chat_id | F.pinned_message
)

@router.message(service_filter)
async def delete_service_messages(m: 'Message'):
    if not state.sys_clean_enabled:
        return
    if ALLOWLIST and int(m.chat.id) not in ALLOWLIST:
        return
    try:
        await bot.delete_message(chat_id=m.chat.id, message_id=m.message_id)
    except Exception as e:
        logging.debug("delete_message failed in chat %s mid=%s: %s", m.chat.id, m.message_id, e)

# ── Bot lockdown ───────────────────────────────────────────────────────────────
def _zero_perms() -> 'ChatPermissions':
    return ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )

async def _restrict_bot_forever(chat_id: int, user_id: int) -> None:
    if not state.botlock_enabled:
        return
    if state.me_id and user_id == state.me_id:
        return
    try:
        cm = await bot.get_chat_member(chat_id, user_id)
        if isinstance(cm, (ChatMemberAdministrator, ChatMemberOwner)):
            return
    except Exception:
        pass
    try:
        now = int(time.time())
        forever_days = 400
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=_zero_perms(),
            until_date=now + forever_days * 24 * 60 * 60,
        )
        log.info("Bot lockdown: restricted bot user_id=%s in chat_id=%s", user_id, chat_id)
    except Exception as e:
        log.debug("Bot lockdown failed for user_id=%s chat_id=%s: %s", user_id, chat_id, e)

@router.message((F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})) & F.new_chat_members)
async def on_new_members_lockdown(m: 'Message'):
    for u in (m.new_chat_members or []):
        if u.is_bot:
            await _restrict_bot_forever(m.chat.id, u.id)
        else:
            record_approval(u.id, m.chat.id)

@router.message((F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})) & F.from_user.as_("u"))
async def on_any_group_message_lock_bots(m: 'Message', u):
    try:
        if u and getattr(u, "is_bot", False):
            await _restrict_bot_forever(m.chat.id, u.id)
    except Exception:
        pass

# ── Join Request flow ──────────────────────────────────────────────────────────
@router.chat_join_request()
async def on_join_request(event: 'ChatJoinRequest'):
    if ALLOWLIST and int(event.chat.id) not in ALLOWLIST:
        log.info("Ignoring join request for non-allowed chat_id=%s title=%s", event.chat.id, event.chat.title)
        return

    set_pending(event.from_user.id, event.chat.id, event.chat.title or "")

    title = event.chat.title or "группа"
    open_url = await get_group_open_url(event.chat.id)
    if open_url:
        title_html = f'<a href="{html.escape(open_url, quote=True)}">{html.escape(title)}</a>'
    else:
        title_html = html.escape(title)

    text = (
        f"👋 Привет! Чтобы вступить в {title_html}, пройдите короткую проверку.\n\n"
        "Нажмите кнопку ниже — и вы будете одобрены автоматически. "
        "Если кнопка не работает, нажмите /start ещё раз."
    )

    try:
        await bot.send_message(
            chat_id=event.from_user.id,
            text=text,
            reply_markup=verify_keyboard(chat_id=event.chat.id, user_id=event.from_user.id),
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.info("DM failed (maybe user hasn't started bot yet): %s", e)

# ── Start & callbacks ──────────────────────────────────────────────────────────
@router.message(CommandStart())
async def on_start(message: 'Message'):
    await expire_old_requests()
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        rows = list(conn.execute(
            "SELECT chat_id, chat_title, requested_at FROM pending_requests WHERE user_id=?",
            (message.from_user.id,)
        ))
    if not rows:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Обновить", callback_data="refresh")
        await message.answer(
            "Привет! Пока нет активных заявок на вступление.\n"
            "Если вы только что нажали «Вступить», подождите несколько секунд и нажмите «Обновить».",
            reply_markup=kb.as_markup(),
        )
        return

    if len(rows) == 1:
        chat_id, chat_title, _ = rows[0]
        safe = html.escape(chat_title) if chat_title else str(chat_id)
        await message.answer(
            f"Заявка на вступление в «{safe}». Нажмите кнопку для подтверждения.",
            reply_markup=verify_keyboard(chat_id=chat_id, user_id=message.from_user.id),
        )
    else:
        await message.answer(
            "Найдены несколько заявок. Выберите чат ниже:",
            reply_markup=requests_keyboard(message.from_user.id, rows),
        )

@router.callback_query(F.data == "refresh")
async def on_refresh(cb: 'CallbackQuery'):
    await expire_old_requests()
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        rows = list(conn.execute(
            "SELECT chat_id, chat_title, requested_at FROM pending_requests WHERE user_id=?",
            (cb.from_user.id,)
        ))
    if not rows:
        try:
            await cb.message.edit_text("Заявок не найдено. Если вы только что отправили запрос, подождите и нажмите ещё раз.")
        except Exception:
            pass
        await cb.answer("Обновлено")
        return

    if len(rows) == 1:
        chat_id, chat_title, _ = rows[0]
        safe = html.escape(chat_title) if chat_title else str(chat_id)
        await cb.message.edit_text(
            f"Заявка на вступление в «{safe}». Нажмите кнопку для подтверждения.",
            reply_markup=verify_keyboard(chat_id=chat_id, user_id=cb.from_user.id),
        )
        await cb.answer("Ок")
        return

    await cb.message.edit_text(
        "Найдены несколько заявок. Выберите чат ниже:",
        reply_markup=requests_keyboard(cb.from_user.id, rows),
    )
    await cb.answer("Обновлено")

@router.callback_query(F.data.startswith("v:"))
async def on_verify(cb: 'CallbackQuery'):
    ok, chat_id, err = parse_and_verify_cbdata(cb.data, actual_user_id=cb.from_user.id)
    if not ok or chat_id is None:
        await cb.answer(err or "Ошибка", show_alert=True); return

    if ALLOWLIST and chat_id not in ALLOWLIST:
        await cb.answer("Эта заявка не из разрешённого чата.", show_alert=True); return

    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        row = conn.execute(
            "SELECT chat_title, requested_at FROM pending_requests WHERE user_id=? AND chat_id=?",
            (cb.from_user.id, chat_id),
        ).fetchone()

    if not row:
        await cb.answer("Заявка не найдена или устарела. Нажмите «Обновить».", show_alert=True); return

    chat_title, requested_at = row
    chat_title_safe = html.escape(chat_title) if chat_title else str(chat_id)

    if int(time.time()) - int(requested_at) > JOIN_REQUEST_TTL:
        clear_pending(cb.from_user.id, chat_id)
        try:
            await bot.decline_chat_join_request(chat_id=chat_id, user_id=cb.from_user.id)
        except Exception:
            pass
        await cb.answer("Заявка просрочена. Отправьте её заново.", show_alert=True); return

    try:
        await _safe_approve(bot, chat_id, cb.from_user.id)
        record_approval(cb.from_user.id, chat_id)
        clear_pending(cb.from_user.id, chat_id)

        await cb.message.edit_text(f"Готово! Заявка одобрена — добро пожаловать в «{chat_title_safe}».")
        await cb.answer("Подтверждено ✅")

        url = await get_group_open_url(chat_id)
        if url:
            try:
                await bot.send_message(
                    chat_id=cb.from_user.id,
                    text=f"Добро пожаловать! Откройте чат «{chat_title_safe}»:",
                    reply_markup=open_group_keyboard(url, title=f"Перейти в «{chat_title_safe}»"),
                    disable_web_page_preview=True,
                )
            except Exception as e:
                log.debug("DM with open button failed: %s", e)

    except Exception:
        logging.exception("approve_chat_join_request failed")
        await cb.answer("Не удалось одобрить. Попробуйте позже.", show_alert=True)

# ── Diagnostics ────────────────────────────────────────────────────────────────
def _brief_entities(m: 'Message'):
    ents = []
    for e in (m.entities or []) + (m.caption_entities or []):
        ents.append(getattr(e, "type", "?"))
    return ",".join(ents) if ents else "-"

def _has_links_or_mentions(m: 'Message') -> bool:
    txt = (m.text or m.caption or "") or ""
    if MENTION_OR_LINK_RE.search(txt):
        return True
    for ent in (m.entities or []) + (m.caption_entities or []):
        if getattr(ent, "type", None) in ("url", "text_link", "mention"):
            return True
    return False

@router.message(group_msg_filter)
async def __diag_log_new(m: 'Message'):
    # Команды не трогаем
    if (m.text or "").startswith("/") or _has_bot_command(m):
        return
    if not state.diag_enabled:
        return
    uid = m.from_user.id if m.from_user else None
    uname = f"@{m.from_user.username}" if (m.from_user and m.from_user.username) else "-"
    is_bot = getattr(m.from_user, "is_bot", None) if m.from_user else None
    txt = (m.text or m.caption or "")
    has = _has_links_or_mentions(m)
    is_new = (uid is not None and _removed_is_newcomer(uid, m.chat.id))
    await log_bot_rights(m.chat.id)
    log.info("DIAG message: chat=%s mid=%s uid=%s %s is_bot=%s entities=[%s] has_links=%s newcomer=%s text=%r",
             m.chat.id, m.message_id, uid, uname, is_bot, _brief_entities(m), has, is_new, txt[:400])

@router.edited_message(group_msg_filter)
async def __diag_log_edit(m: 'Message'):
    if (m.text or "").startswith("/") or _has_bot_command(m):
        return
    if not state.diag_enabled:
        return
    uid = m.from_user.id if m.from_user else None
    uname = f"@{m.from_user.username}" if (m.from_user and m.from_user.username) else "-"
    is_bot = getattr(m.from_user, "is_bot", None) if m.from_user else None
    txt = (m.text or m.caption or "")
    has = _has_links_or_mentions(m)
    is_new = (uid is not None and _removed_is_newcomer(uid, m.chat.id))
    await log_bot_rights(m.chat.id)
    log.info("DIAG edited:  chat=%s mid=%s uid=%s %s is_bot=%s entities=[%s] has_links=%s newcomer=%s text=%r",
             m.chat.id, m.message_id, uid, uname, is_bot, _brief_entities(m), has, is_new, txt[:400])

# ── Anti-link for newcomers (24h) ──────────────────────────────────────────────
MENTION_OR_LINK_RE = re.compile(
    r'(?i)('
    r'https?://\S+|t\.me/\S+|www\.\S+|'
    r'@[A-Za-z0-9_]{4,}|'
    r'\b[A-Za-z0-9-]{2,}\.(?:com|ru|net|org|io|co|app|site|link|info|me|pro|dev)\b'
    r')'
)

@router.message(group_msg_filter)
async def newcomer_anti_links(m: 'Message'):
    await _antilink_core(m)

@router.edited_message(group_msg_filter)
async def newcomer_anti_links_edited(m: 'Message'):
    await _antilink_core(m)

# ── Chat member updates ─────────────────────────────────────────────────────────
@router.chat_member()
async def on_chat_member_update(ev: 'ChatMemberUpdated'):
    if ev.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    new_s = ev.new_chat_member.status
    old_s = ev.old_chat_member.status
    if new_s == ChatMemberStatus.MEMBER and old_s in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.RESTRICTED}:
        u = ev.new_chat_member.user
        if u and not u.is_bot:
            pass
            
# ── TTL Expirer ────────────────────────────────────────────────────────────────
async def expire_old_requests() -> None:
    now = int(time.time())
    with closing(sqlite3.connect(SQLITE_PATH, timeout=3.0)) as conn:
        rows = list(conn.execute("SELECT user_id, chat_id, chat_title, requested_at FROM pending_requests"))
        for user_id, chat_id, chat_title, requested_at in rows:
            if now - requested_at <= JOIN_REQUEST_TTL:
                continue
            try:
                log.info("TTL expired: approving & restricting user_id=%s chat_id=%s", user_id, chat_id)
                await _safe_approve(bot, chat_id, user_id)
                record_approval(user_id, chat_id)
                forever_days = 400
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=_zero_perms(),
                    until_date=now + forever_days * 24 * 60 * 60,
                )
                title = chat_title or str(chat_id)
                open_url = await get_group_open_url(chat_id)
                if open_url:
                    title_html = f'<a href="{html.escape(open_url, quote=True)}">{html.escape(title)}</a>'
                else:
                    title_html = html.escape(title)
                admin_mention = await get_public_admin_mention(chat_id)
                if admin_mention:
                    txt = (
                        f"Вы приняты в группу {title_html}, но отправка сообщений отключена навсегда.\n"
                        f"Чтобы получить право писать, пройдите проверку у администратора {admin_mention}."
                    )
                else:
                    txt = (
                        f"Вы приняты в группу {title_html}, но отправка сообщений отключена навсегда.\n"
                        "Чтобы получить право писать, пройдите проверку у администратора."
                    )
                try:
                    await bot.send_message(chat_id=user_id, text=txt, disable_web_page_preview=True)
                except Exception as e:
                    log.debug("DM to user %s failed: %s", user_id, e)
            except Exception:
                logging.exception("approve+restrict failed for user_id=%s chat_id=%s", user_id, chat_id)
            conn.execute("DELETE FROM pending_requests WHERE user_id=? AND chat_id=?", (user_id, chat_id))
        conn.commit()

async def expirer_loop():
    await asyncio.sleep(5)
    log.info("Expirer loop started: interval=%ss ttl=%ss", EXPIRE_SWEEP_INTERVAL, JOIN_REQUEST_TTL)
    while True:
        try:
            await expire_old_requests()
        except Exception:
            log.exception("expire_old_requests() crashed")
        await asyncio.sleep(EXPIRE_SWEEP_INTERVAL)

# ── Optional systemd watchdog heartbeat ────────────────────────────────────────
async def watchdog_task():
    if SystemdNotifier is None:
        return
    try:
        n = SystemdNotifier()
        n.notify("READY=1")
        wd_usec = os.getenv("WATCHDOG_USEC")
        if not wd_usec:
            return
        interval = max(1.0, int(wd_usec) / 1_000_000 / 2.0)  # half of watchdog
        log.info("Systemd watchdog enabled: interval=%.1fs", interval)
        while True:
            n.notify("WATCHDOG=1")
            await asyncio.sleep(interval)
    except Exception as e:
        log.debug("Watchdog task stopped: %s", e)

# ── Тестовая тотальная трасса (в самом конце, чтобы перекрывала странные случаи) ──
def _is_test_chat(chat_id: Optional[int]) -> bool:
    return bool(TEST_CHAT_ID and chat_id and int(chat_id) == TEST_CHAT_ID)

def tlog(chat_id: Optional[int], msg: str) -> None:
    if TRACE_TEST_CHAT and _is_test_chat(chat_id):
        log.info("TRACE: chat=%s | %s", chat_id, msg)

@router.message()
async def __trace_all_msgs(m: Message):
    try:
        if not _is_test_chat(getattr(getattr(m, "chat", None), "id", None)):
            return
        uid = getattr(getattr(m, "from_user", None), "id", None)
        t = (m.text or m.caption or "") or ""
        ents = [getattr(e, "type", None) for e in (m.entities or []) + (m.caption_entities or [])]
        tlog(m.chat.id, f"MSG mid={getattr(m,'message_id',None)} uid={uid} type={getattr(getattr(m,'chat',None),'type',None)} "
                        f"entities={ents} text={t[:200]!r}")
    except Exception as e:
        log.debug("TRACE: message hook failed: %s", e)

@router.edited_message()
async def __trace_all_edits(m: Message):
    try:
        if not _is_test_chat(getattr(getattr(m, "chat", None), "id", None)):
            return
        uid = getattr(getattr(m, "from_user", None), "id", None)
        t = (m.text or m.caption or "") or ""
        ents = [getattr(e, "type", None) for e in (m.entities or []) + (m.caption_entities or [])]
        tlog(m.chat.id, f"EDIT mid={getattr(m,'message_id',None)} uid={uid} entities={ents} text={t[:200]!r}")
    except Exception as e:
        log.debug("TRACE: edited_message hook failed: %s", e)

# ── Entry point ─────────────────────────────────────────────────────────────────
async def main():
    init_db()
    # load toggles
    val = db_get_setting("sysclean_enabled")
    state.sys_clean_enabled = (val.lower() == "true") if val is not None else ENV_DELETE_SYSTEM_MESSAGES
    val2 = db_get_setting("botlock_enabled")
    state.botlock_enabled = (val2.lower() == "true") if val2 is not None else ENV_LOCKDOWN_NONADMIN_BOTS
    val3 = db_get_setting("diag_enabled")
    state.diag_enabled = (val3.lower() == "true") if val3 is not None else False

    me = await bot.get_me()
    state.me_id = me.id
    state.me_username = (me.username or "").lower()
    log.info("Bot username: @%s (support, sys-clean=%s, botlock=%s, diag=%s)",
             me.username, state.sys_clean_enabled, state.botlock_enabled, state.diag_enabled)
    log.info(
        "ENV: SQLITE_PATH=%s DELETE_SYSTEM_MESSAGES=%s LOCKDOWN_NONADMIN_BOTS=%s AGGRESSIVE_CHANNEL_ANTILINK=%s "
        "ALLOWLIST=%s TEST_CHAT_ID=%s TRACE_TEST_CHAT=%s",
        SQLITE_PATH, ENV_DELETE_SYSTEM_MESSAGES, ENV_LOCKDOWN_NONADMIN_BOTS, AGGRESSIVE_CHANNEL_ANTILINK,
        sorted(ALLOWLIST) if ALLOWLIST else "ALL", TEST_CHAT_ID or 0, TRACE_TEST_CHAT
    )

    # background tasks
    asyncio.create_task(expirer_loop())
    asyncio.create_task(watchdog_task())

    try:
        if HAS_WD:
            await _wd.start(bot, dp, log, cmd_router, TEST_CHAT_ID, TEST_USER_ID)
    except Exception as e:
        log.warning("TESTUSER WD start error: %r", e)
    # BEGIN PATCH: call DB integrity check before polling
    try:
        import logging
        logging.getLogger("support-join-guard").info("DB CHECK: start")
        _db_integrity_check_and_repair()
        logging.getLogger("support-join-guard").info("DB CHECK: done")
    except Exception:
        import logging
        logging.getLogger("support-join-guard").exception("DB CHECK: failed")
    # END PATCH
    await dp.start_polling(
        bot,
        allowed_updates = ['message','edited_message','chat_member','my_chat_member','chat_join_request','callback_query'],
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass


async def _antilink_core(m: Message):
    # DIAG
    if state.diag_enabled:
        has_l = _has_links_or_mentions(m)
        newc = (m.from_user and _removed_is_newcomer(m.from_user.id, m.chat.id)) if m.from_user else False
        log.info(
            "DIAG message: chat=%s mid=%s uid=%s is_bot=%s has_links=%s newcomer=%s text=%r",
            m.chat.id, m.message_id,
            getattr(getattr(m, "from_user", None), "id", None),
            getattr(getattr(m, "from_user", None), "is_bot", None),
            has_l, newc, (m.text or m.caption or "")[:180],
        )

    # Команды не трогаем
    if m.text and m.text.startswith('/'):
        return

    # Сообщение от канала/анона
    if getattr(m, "sender_chat", None) is not None and getattr(m.sender_chat, "id", None) is not None:
        if AGGRESSIVE_CHANNEL_ANTILINK and _has_links_or_mentions(m):
            try:
                await bot.delete_message(m.chat.id, m.message_id)
                log.info("Aggressive AntiLink: deleted CHANNEL/ANON message mid=%s chat=%s", m.message_id, m.chat.id)
            except Exception as e:
                log.info("Aggressive AntiLink: failed mid=%s in chat %s: %s", m.message_id, m.chat.id, e)
        else:
            log.info("SKIP-AntiLink: sender_chat present but no links mid=%s chat=%s", m.message_id, m.chat.id)
        return

    if not m.from_user:
        log.info("SKIP-AntiLink: no from_user (channel/anon) mid=%s chat=%s", m.message_id, m.chat.id)
        return

    uid = m.from_user.id

    # Админам можно всё
    if await is_user_admin(uid, m.chat.id):
        log.info("SKIP-AntiLink: sender is admin uid=%s chat=%s mid=%s", uid, m.chat.id, m.message_id)
        return

    # Нет ссылок/упоминаний
    if not _has_links_or_mentions(m):
        if state.diag_enabled:
            log.info("SKIP-AntiLink: no link/mention uid=%s chat=%s mid=%s", uid, m.chat.id, m.message_id)
        return

    # Обеспечить окно новичка
    nu = newcomer_until(uid, m.chat.id)
    if nu is None:
        record_approval(uid, m.chat.id)
        nu = newcomer_until(uid, m.chat.id)
    now = int(time.time())
    if not (nu and nu > now):
        log.info("SKIP-AntiLink: not newcomer uid=%s chat=%s mid=%s (until=%s now=%s)", uid, m.chat.id, m.message_id, nu, now)
        return

    try:
        await bot.delete_message(m.chat.id, m.message_id)
        log.info("AntiLink: deleted from user_id=%s chat_id=%s mid=%s", uid, m.chat.id, m.message_id)
    except Exception as e:
        log.info("AntiLink: failed delete mid=%s in chat %s: %s", m.message_id, m.chat.id, e)

# === NEWCOMER PROBE (debug-only, enable via NEWCOMER_PROBE=1 in /etc/tgbots/support.env) ===
try:
    if os.getenv("NEWCOMER_PROBE","0") == "1":
        log.info("PROBE: enabled")
        @router.message(~F.chat.type.in_({ChatType.PRIVATE}))
        async def __probe_newcomer_any_message(m: Message):
            u = m.from_user
            uid = getattr(u, "id", None)
            newcomer = (uid is not None and _removed_is_newcomer(uid, m.chat.id))
            log.info("PROBE: hit chat=%s type=%s mid=%s uid=%s newcomer=%s",
                     getattr(m.chat, "id", None), getattr(m.chat, "type", None),
                     getattr(m, "message_id", None), uid, newcomer)
            if newcomer and u and not u.is_bot:
                try:
                    await m.delete()
                    log.info("PROBE: deleted chat=%s mid=%s uid=%s", m.chat.id, m.message_id, uid)
                except Exception as e:
                    log.warning("PROBE: delete failed chat=%s mid=%s uid=%s err=%s", m.chat.id, getattr(m,'message_id',None), uid, e)
except Exception as _e:
    log.warning("PROBE: attach failed: %s", _e)

# --- TESTUSER LEAVE LOGGING (auto-inserted) -----------------------------------
# Логируем выход тестового пользователя из тестового чата:
# - событие ChatMemberUpdated, когда статус стал LEFT/KICKED
@router.chat_member()
async def _testuser_leave_logger(ev: 'ChatMemberUpdated'):
    try:
        if not (TEST_CHAT_ID and TEST_USER_ID):
            return
        chat_id = getattr(getattr(ev, "chat", None), "id", None)
        newcm = getattr(ev, "new_chat_member", None)
        user = getattr(newcm, "user", None)
        status = getattr(newcm, "status", None)
        uid = getattr(user, "id", None)
        uname = ("@" + getattr(user, "username", "")) if getattr(user, "username", None) else "-"
        if chat_id == TEST_CHAT_ID and uid == TEST_USER_ID and status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
            actor = getattr(getattr(ev, "from_user", None), "id", None)
            log.info("TESTUSER LEFT: chat=%s uid=%s %s status=%s by=%s", chat_id, uid, uname, status, actor)
    except Exception as e:
        # не валим обработку — логируем и продолжаем
        log.warning("TESTUSER LEFT log error: %r", e)
# ------------------------------------------------------------------------------

