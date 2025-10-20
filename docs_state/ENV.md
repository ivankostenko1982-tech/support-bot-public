# ENV (без секретов)
```
# === Required ===

#@krasnogorskichat Id: -1001209607608 @odingrad_centr Id: -1001404423510 @portland_moscow Id: -1001878435829 @odingrad Id: -1001437148632 @mkrdesna Id: -1001276110445 @odingrad_lesnoy Id: -1001329487433
# @rasskazovochat Id: -1001472589350 @chatvatutinki Id: -1001355629107 @odingrad_boltalka Id: -1001210525113 @innovaciyachat Id: -1001274723644 @odingrad_semeyniy Id: -1001413291597
# === Chats ===
TARGET_CHAT_IDS="-1002099408662,-1001209607608,-1001404423510,-1001878435829,-1001437148632,-1001276110445,-1001329487433,-1001472589350,-1001355629107,-1001210525113,-1001274723644,-1001413291597"

# === (optional) Admins ===
# ADMIN_IDS=123456789 987654321
# ADMIN_CONTACT_OVERRIDE=yourpublicadmin

# === Behaviour toggles ===
DELETE_SYSTEM_MESSAGES=true
LOCKDOWN_NONADMIN_BOTS=true
AGGRESSIVE_CHANNEL_ANTILINK=true

# === Timers ===
JOIN_REQUEST_TTL=600
EXPIRE_SWEEP_INTERVAL=20
NEWCOMER_WINDOW_SECONDS=86400

# === SQLite path (must be writable by systemd sandbox) ===
SQLITE_PATH=/opt/tgbots/bots/support/join_guard_state.db
SWEEPER_MODE=live
LOG_LEVEL=DEBUG
NEWCOMER_PROBE=1
NEWCOMER_TRACE=1

TEST_CHAT_ID=-1002099408662
TEST_USER_ID=6700029291
TRACE_TEST_CHAT=1

HUMAN_MIN_DELAY=3
HUMAN_TTL_STEP1=180
HUMAN_TTL_STEP2=60
# GUARD_SECRET опционален (сейчас не используется, т.к. токены хранятся в БД)

DIAG_ENABLE=1               # включить/выключить (по умолчанию 1)
DIAG_DIR=/opt/tgbots/bots/support/diag     # куда писать (по умолчанию рядом с БД)
DIAG_BASENAME=diag          # префикс имени файла
DIAG_DB_ROWS=20             # сколько строк примеров выводить из таблиц
DIAG_INCLUDE_DB=1           # включать ли блок БД
DIAG_INCLUDE_ENV=1          # включать ли блок ENV
DIAG_INCLUDE_ROUTERS=1      # включать ли роутеры/хендлеры (best-effort)
DIAG_KEEP=15                # сколько последних файлов держать

# где лежат все служебные .sh
UTILS_DIR=/opt/tgbots/utils

# пин рабочей версии aiogram (пример)
AIROGRAM_VERSION=3.22.0


NEWCOMER_TEST_ONLY=1

ENABLE_HOOKS=1
HOOKS_DIR=/opt/tgbots/utils/hooks

```
