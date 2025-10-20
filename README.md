# Support Bot (Telegram) — код, автодеплой и эксплуатация

Этот репозиторий хранит **рабочий код бота** (`app.py`). Пуш в серверный bare‑репозиторий триггерит **автодеплой**: снапшот → бэкап → `py_compile` → установка нового `app.py` → `systemctl restart tgbot@support.service` → сбор журнала и автодоков в ветку `state` (генерируется **на сервере**).

- Боевой код: `/opt/tgbots/bots/support/app.py`
- Сервис: `tgbot@support.service`
- ENV: `/etc/tgbots/support.env` (секреты **не коммитим**)
- Venv: `/opt/tgbots/.venv`
- БД (SQLite, WAL): `/opt/tgbots/bots/support/join_guard_state.db`
- Bare‑repo: `/opt/tgbots/git/support.git` → worktree хуков: `/opt/tgbots/repos/support`
- Утилиты/скрипты: `/opt/tgbots/utils/`

---

## 1) Быстрый старт локально (Windows/Linux/macOS)

```bash
# в папке проекта на ноутбуке
git init
git add app.py .gitignore README.md
git commit -m "initial import"

# привязать серверный репозиторий (пример для root@82.146.35.169)
git remote add origin "ssh://root@82.146.35.169/opt/tgbots/git/support.git"
git branch -M main
git push -u origin main
```

После push хук на сервере выполнит деплой. Проверка на сервере:
```bash
journalctl -u tgbot@support.service -n 200 --no-pager
```

---

## 2) Конфигурация через ENV (секреты вне Git)

Файл окружения для инстанса **support**: `/etc/tgbots/support.env`. Доступ: `root` и `tgbot` (обычно `chmod 640`, `chown root:tgbot`).

Минимальный пример:
```
BOT_TOKEN=...                        # секрет! (не печатать в логах)
SQLITE_PATH=/opt/tgbots/bots/support/join_guard_state.db
UTILS_DIR=/opt/tgbots/utils

TEST_CHAT_ID=-1002099408662
TEST_USER_ID=6700029291
TRACE_TEST_CHAT=1
NEWCOMER_WINDOW_SECONDS=86400
NEWCOMER_TEST_ONLY=1

DELETE_SYSTEM_MESSAGES=true
LOCKDOWN_NONADMIN_BOTS=true
AGGRESSIVE_CHANNEL_ANTILINK=true

TARGET_CHAT_IDS=-1002099408662,-1001878435829
ADMIN_IDS=11111111,22222222
```
Проверка без утечки секретов:
```bash
/opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env
```

---

## 3) Сервисный запуск (systemd)

Инстанс: `tgbot@support.service`. Типовой `ExecStart`:
```
/opt/tgbots/.venv/bin/python /opt/tgbots/bots/support/app.py --instance support
```
Полезное:
```bash
systemctl status tgbot@support.service --no-pager
journalctl -u tgbot@support.service -n 200 --no-pager
systemctl show -p ExecStart --value tgbot@support.service
```

---

## 4) БД SQLite (WAL) — хранение состояния

Путь берётся из `SQLITE_PATH`. Типовые таблицы: `pending_requests`, `approvals`, `newcomer_seen`. Режим WAL, таймаут блокировок ~3 с. Быстрые проверки:
```bash
sqlite3 "$SQLITE_PATH" "PRAGMA journal_mode; PRAGMA busy_timeout; PRAGMA integrity_check; .tables;"
```

Бэкап «на горячую»:
```bash
sqlite3 "$SQLITE_PATH" ".backup /opt/tgbots/bots/support/join_guard_state.db.bak.$(date -u +%Y%m%d-%H%M%SZ)"
```

---

## 5) Патчи и безопасный workflow правок (без ручного редактирования app.py)

**Правим код только через утилиты в `/opt/tgbots/utils/`:**
- `app_safe_apply.sh` — полный безопасный цикл (SNAPSHOT → BACKUP → TMP → py_compile → install → restart → TRACE → авто‑откат при фатальных паттернах).
- `app_quick_apply.sh` — упрощённый цикл для часто повторяемых малых правок.
- `snapshot_app.sh` — быстрый снимок (sha256, size, head, `py_compile`).
- `app_baseline.sh` — признать текущее состояние эталоном (обновляет baseline).
- `diag_collect.sh` — собрать полную диагностику.

Шаблон применения патча (патч — это отдельный `patch_*.py`, работающий по TMP‑файлу):
```bash
/opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/patch_my_change.py
journalctl -u tgbot@support.service -n 200 --no-pager
```
Ручной откат на последний бэкап:
```bash
cp -a /opt/tgbots/bots/support/app.bak.*.py /opt/tgbots/bots/support/app.py --backup=t
systemctl restart tgbot@support.service
```

---

## 6) Снапшоты, baseline и трассы

Артефакты:
- Бэкапы кода: `/opt/tgbots/bots/support/app.bak.YYYYMMDD-HHMMSSZ.py`
- Снимки: `/opt/tgbots/utils/snapshots/`
- Baseline: `/opt/tgbots/utils/app.baseline.json`
- Трейсы: `/opt/tgbots/utils/trace-*.txt`

Типовой цикл:
1) `snapshot_app.sh` перед рисковыми правками
2) `app_safe_apply.sh ...` (или `app_quick_apply.sh ...`)
3) Проверить журнал/трейс
4) Зафиксировать baseline `app_baseline.sh` после подтверждения стабильности

---

## 7) Диагностика и логи

Базовые команды:
```bash
journalctl -u tgbot@support.service -n 300 --no-pager
ls -1 /opt/tgbots/utils/trace-*.txt | tail -n 3
/opt/tgbots/utils/diag_collect.sh && tail -n 100 /opt/tgbots/utils/diag/diag-*.txt
```
Фатальные паттерны, требующие вмешательства: `Traceback|SyntaxError|IndentationError|NameError|SNAPSHOT MISMATCH|database is locked|ModuleNotFoundError`.

---

## 8) Что НЕ коммитим в Git

- Любые секреты (`.env`, `BOT_TOKEN`, `VERIFY_SECRET`)
- Базы/логи/снимки/диагностику: `*.db`, `*.sqlite*`, `docs_state/`, `snapshots/`, `diag_logs/`
- Серверные пути из `/opt`

---

## 9) Полезные сценарии эксплуатации

- **Smoke‑test после деплоя**: `python -m py_compile /opt/tgbots/bots/support/app.py` + просмотр `journalctl`
- **Проверка ENV** без секрета: `/opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env`
- **Миграции SQLite** делаем отдельно: `.backup → DDL → smoke‑test → журнал`
- **Сайдкар наблюдатель тест‑пользователя**: отдельный unit `tgbot-testwatch.service` (читает тот же ENV, хранит своё состояние вне SQLite).

---

## 10) FAQ (коротко)

**Бот не стартует, в логах SNAPSHOT MISMATCH.**  
Либо обновить baseline (`app_baseline.sh`), если это верное состояние, либо откатить `app.py` на рабочий бэкап и перезапустить сервис.

**`database is locked` в журнале.**  
Увеличьте busy_timeout, избегайте параллельных писателей, для тяжёлых операций останавливайте сервис на время.
