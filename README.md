# Support Bot (Telegram) — полная документация

_Собрано автоматически: 2025-10-20 20:58:26Z_

---

## Обзор


Этот README агрегирует всю актуальную эксплуатационную документацию проекта и включает:
- Полное содержание предоставленных *.txt файлов (ниже — в отдельных разделах).
- Описание инфраструктуры деплоя через **git** (server bare → work-tree → боевой `app.py`) и зеркала на GitHub.
- Изменения, добавленные в ходе аудита (минимальные и безопасные правки).

**Критические пути:**  
- Боевой код: `/opt/tgbots/bots/support/app.py`  
- Bare-репозиторий: `/opt/tgbots/git/support.git`  
- Work-tree хуков: `/opt/tgbots/repos/support`  
- Утилиты/скрипты: `/opt/tgbots/utils`  
- Сервис: `tgbot@support.service`  
- ENV: `/etc/tgbots/support.env`  
- SQLite (WAL): `/opt/tgbots/bots/support/join_guard_state.db`


## NEWCOMER GATE (join‑guard)

### Назначение
Фильтр на вход новых участников чатов. Может работать в **DRYRUN** (только логирует) или **ACTIVE** (не даёт мгновенного одобрения, включает ограничение на время окна).

### Переменные окружения (`/etc/tgbots/support.env`)
```
NEWCOMER_GATE_ENABLE=1                # включить логику гейта
NEWCOMER_GATE_DRYRUN=0                # 1 — только лог; 0 — активный режим
NEWCOMER_GATE_CHATS_FILE=/etc/tgbots/newcomer_gate_chats.txt
NEWCOMER_GATE_PURGE_ALL=1             # (опционально) расширять TESTPURGE до purge для всех чатов из allowlist
```

### Allowlist чатов
Файл `NEWCOMER_GATE_CHATS_FILE` содержит **один chat_id на строку**:
```
-1002099408662
-1001210525113
```
Пустые строки и `# комментарии` допускаются.

### Как это видно в логах (`journalctl -u tgbot@support.service -n 200 --no-pager`)
- ACTIVE‑режим при вступлении:
  ```
  GATE TRACE: resolved chat=<cid> _cid=<cid> _uid=<uid> fu.id=<actor> join.id=<joined>
  GATE ACTIVE: member-join chat=<cid> uid=<uid> -- suppress immediate approve
  ```
- DRYRUN‑режим (когда `NEWCOMER_GATE_DRYRUN=1`):
  ```
  GATE DRYRUN: member-join chat=<cid> uid=<uid> would apply newcomer gate (no immediate approve)
  ```

### Безопасные фоллбеки идентификаторов (patch уже на месте)
В DRYRUN‑блок добавлены фоллбеки получения `chat_id` и `user_id` из `ev.chat.id`, `ev.from_user.id` и `ev.new_chat_member.user.id`.
Также введено извлечение prefer‑ID именно **присоединившегося** пользователя (а не актёра).

### Типичные проверки
- Компиляция: `python3 -m py_compile /opt/tgbots/bots/support/app.py`
- Диагностика гейта: `/opt/tgbots/utils/diag_gate_status.sh`
  - Показывает окно кода вокруг обработчика join, наличие DRYRUN‑блока/логов и текущее содержимое allowlist.

---

## TESTPURGE / PURGE_ALL (чистка входящих сообщений новичков)

### Что это
Служебная логика, которая удаляет входные сообщения пользователя в период “новичка”. В логах видны пробеги вида:
```
TESTPURGE: probe(entry) mid=<id> uid=<uid> chat=<cid>
TESTPURGE: deleted chat=<cid> uid=<uid> mid=<mid> now=<ts> until=<ts>
TESTPURGE: skip(reason=not_test_pair) got_chat=<cid> got_uid=<uid>
```

### Расширение до PURGE_ALL для allowlist
Чтобы расширить тестовую чистку **на все чаты из allowlist**, используется флаг `NEWCOMER_GATE_PURGE_ALL=1` в `/etc/tgbots/support.env`.
Патч в `app.py` уже применён: skip‑ветка оборачивается проверкой allowlist, и в разрешённых чатах чистка не пропускается.

Проверка статуса:
```
/opt/tgbots/utils/diag_purge_skip_anchors.sh
journalctl -u tgbot@support.service -n 300 --no-pager | egrep -i "TESTPURGE:|PURGE_ALL|deleted|skip\(reason"
```

---

## Безопасные обёртки (run_safe.sh) и быстрые сценарии

### Универсальный раннер
`/opt/tgbots/utils/run_safe.sh "команда ..."`, гарантирует вывод с префиксами и кодом возврата.
Примеры:
```
/opt/tgbots/utils/run_safe.sh "/opt/tgbots/utils/diag_gate_status.sh"
/opt/tgbots/utils/run_safe.sh "bash -lc 'systemctl restart tgbot@support.service; sleep 2; journalctl -u tgbot@support.service -n 120 --no-pager'"
```

### Частые операции
- Перезапуск и короткий хвост:
  ```
  /opt/tgbots/utils/run_safe.sh "bash -lc 'systemctl restart tgbot@support.service; sleep 2; journalctl -u tgbot@support.service -n 180 --no-pager'"
  ```
- Проверка allowlist и ENV:
  ```
  /opt/tgbots/utils/run_safe.sh "bash -lc 'nl -ba /etc/tgbots/newcomer_gate_chats.txt'"
  /opt/tgbots/utils/run_safe.sh "bash -lc 'egrep -n "NEWCOMER_GATE_(ENABLE|DRYRUN|CHATS_FILE|PURGE_ALL)" /etc/tgbots/support.env'"
  ```

---

## Git‑поток, автодеплой и зеркало (кратко)
- Пуш в `ssh:///opt/tgbots/git/support.git` (ветка `main`) → `post-receive` обновляет work-tree → сравнивает SHA → безопасно выкладывает `app.py` (py_compile, backup) → рестартует сервис.
- Отдельный хук зеркалит коммиты в публичный GitHub-репозиторий.

---

## Триггеры и сигналы в логах
- `BOOT: app.py loaded ...` — успешная загрузка файла и конфигурации.
- `PROBE: enabled` / `DB CHECK: done` — sanity‑проверки.
- `TESTUSER STATUS CHANGE: chat=... uid=... <from>-><to>` — движение тест-пользователя.
- `GATE ACTIVE/DRYRUN` — состояние newcomer‑gate.
- `TESTPURGE: deleted / skip(reason=...)` — чистка сообщений.

---

## Быстрый чеклист администратора
1. `systemctl status tgbot@support.service --no-pager`
2. `journalctl -u tgbot@support.service -n 200 --no-pager | egrep -i "GATE|TESTPURGE|BOOT|DB CHECK|STATUS CHANGE"`
3. Проверить ENV и allowlist: см. команды выше.
4. `python3 -m py_compile /opt/tgbots/bots/support/app.py` — валидность кода.
5. Если поведение не соответствует ожиданию — `diag_gate_status.sh` и снимок кода.

---


## Git-поток, автодеплой и зеркало


**Пуш в** `ssh://<server>/opt/tgbots/git/support.git` (**ветка `main`**) запускает `hooks/post-receive` на сервере:

1. **Обновление work-tree**: `git checkout -f` в `/opt/tgbots/repos/support` — гарантирует, что рабочее дерево соответствует последнему коммиту.
2. **Сравнение SHA**: `sha256sum` у `WORK/app.py` и боевого `APP`.  
   - Если **отличаются** → компиляция `py_compile` → бэкап `APP.bak.<TS>` → установка нового `app.py` → `systemctl restart tgbot@support.service`.
   - Если **совпадают** → деплой пропускается.
3. **Документация**: запуск docgen → генерация служебных артефактов в `docs_state/*` и обновление рефа (ветка `state`).
4. **Зеркало на GitHub**: зеркалирование в `git@github.com:<USER_OR_ORG>/support-bot-public.git` через deploy-key.

**Windows-примечания**: используем системный OpenSSH, включён `.gitattributes` со строгим `eol=lf` для кросс-платформенной согласованности; при необходимости — `git add --renormalize .`.


## Что добавлено/исправлено (минимальные и безопасные правки)


- **Graceful shutdown фоновых задач**: после остановки `dp.start_polling(...)` выполняется сбор всех незавершённых `asyncio` задач, их `cancel()` и `await gather(..., return_exceptions=True)`. Логи: `SHUTDOWN: cancelling ...` / `... cancelled`.
- **Надёжный деплой в hook**: перед сравнением хэшей теперь **всегда** выполняется `git checkout -f` рабочего дерева. Это устраняет гонку, когда work-tree ещё не обновлён.
- **Чистка головы файла**: удалены дубли shebang и повторный импорт, убран мёртвый `return False` в `_removed_is_newcomer()`.
- **LF-переводы строк**: добавлен `.gitattributes` с `* text=auto eol=lf`, чтобы исключить проблемы CRLF/LF на Windows и на GitHub Raw.
- **Набор диагностик и сервисных утилит** (все под `/opt/tgbots/utils`):
  - `check_github_app.sh` — сравнить GitHub RAW и боевой `app.py` (хэши, diff, `py_compile`).
  - `hook_add_deploy_app_v2.sh` / `fix_deploy_order.sh` — вставка/починка деплой-блока в `post-receive`.
  - `diag_deploy_hook.sh` — проверка хуков, work-tree, прав и dry‑run компиляции.
  - `verify_deploy_and_dbcheck.sh` — сверка SHA `APP` vs `WORK`, поиск `DB CHECK` логов.
  - `patch_graceful_shutdown.sh` — добавляет мягкое завершение фоновых задач.
  - `patch_minimal_cleanup.sh` — минимальная санитарная чистка `app.py`.
  - `safe_apply_app_from_work.sh` — разовый безопасный деплой `WORK/app.py` в `APP` (py_compile → backup → install → restart).


## Как обновить этот README вручную


1. Скачай этот файл из ассистента и помести как `README.md` в корень твоего локального репозитория.
2. Коммит и пуш:
   ```powershell
   git add README.md
   git commit -m "docs: update README"
   git push origin main
   ```
Зеркало на GitHub обновится автоматически; серверный деплой **не тронется**, т.к. меняется только документация.


---

## Приложения: исходные документы (*.txt)


### MINI_CHEATSHEET.txt

```text
# MINI CHEATSHEET — частые команды админа

## 0) Быстрые статусы
systemctl status tgbot@support.service --no-pager
journalctl -u tgbot@support.service -n 200 --no-pager

## 1) Рестарт / старт / стоп бота
sudo systemctl restart tgbot@support.service
sudo systemctl start   tgbot@support.service
sudo systemctl stop    tgbot@support.service

## 2) Снимок и компиляция app.py
/opt/tgbots/utils/snapshot_app.sh /opt/tgbots/bots/support/app.py
python3 -m py_compile /opt/tgbots/bots/support/app.py || echo "PY_COMPILE=FAIL"

## 3) Список бэкапов и откат
ls -1t /opt/tgbots/bots/support/app.bak.*.py | head
# восстановление конкретного:
# sudo cp -v /opt/tgbots/bots/support/app.bak.<STAMP>.py /opt/tgbots/bots/support/app.py && \
# sudo systemctl restart tgbot@support.service

## 4) Диагностика и окружение
/opt/tgbots/utils/diag_collect.sh
/opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

## 5) Проверка участия тест-юзера и DM (сырые API)
/opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env
/opt/tgbots/utils/probe_dm.sh

## 6) Сайдкар тест-наблюдателя (если используется)
systemctl status  tgbot-testwatch.service --no-pager
sudo systemctl restart tgbot-testwatch.service
journalctl -u tgbot-testwatch.service -n 200 --no-pager
sudo cat /var/lib/tgbots/testwatch/testuser.status.json 2>/dev/null || true

## 7) Версии Python/aiogram в .venv
/opt/tgbots/.venv/bin/python -V
/opt/tgbots/.venv/bin/python -c "import aiogram,sys;print('aiogram', aiogram.__version__, 'python', sys.version)"
/opt/tgbots/.venv/bin/pip list --outdated

## 8) Аккуратное обновление aiogram (с точкой отката)
mkdir -p /opt/tgbots/utils/pins
/opt/tgbots/.venv/bin/pip freeze > /opt/tgbots/utils/pins/requirements.freeze.txt
/opt/tgbots/.venv/bin/pip install --upgrade "aiogram>=3,<4"
# откат:
# /opt/tgbots/.venv/bin/pip install -r /opt/tgbots/utils/pins/requirements.freeze.txt

## 9) Уборка старых файлов
ls -1t /opt/tgbots/bots/support/app.bak.*.py | tail -n +21 | xargs -r sudo rm -v
find /opt/tgbots/utils/snapshots -type f -name 'app.*.txt' -mtime +30 -delete
find /opt/tgbots/utils -maxdepth 1 -type f -name 'trace-*.txt' -mtime +21 -delete
find /opt/tgbots/utils/diag -type f -mtime +21 -delete

## 10) Полезное
df -h /opt
tail -n 200 /opt/tgbots/utils/diag/diag-*.txt 2>/dev/null | less
```

### BACKUPS_RETENTION.txt

```text
# Ретеншн бэкапов и служебных файлов

## Что мы накапливаем
- Бэкапы кода: `/opt/tgbots/bots/support/app.bak.*.py`
- Снимки: `/opt/tgbots/utils/snapshots/app.*.txt`
- Диагностика/трейсы: `/opt/tgbots/utils/diag/diag-*.txt`, `/opt/tgbots/utils/trace-*.txt`
- Сайдкар-состояние (если есть): `/var/lib/tgbots/testwatch/*` (обычно мало места)

## Рекомендуемые лимиты
- Бэкапы `app.bak.*.py`: хранить последние 15–20 шт.
- Снимки `snapshots/`: 30–50 шт. (или 30 дней).
- Диагностика/трейсы: по времени — 14–30 дней.

## Быстрая уборка (dry-run → реальное удаление)
# Бэкапы: оставить последние 20
ls -1t /opt/tgbots/bots/support/app.bak.*.py | tail -n +21

# Реально удалить “лишние” бэкапы
ls -1t /opt/tgbots/bots/support/app.bak.*.py | tail -n +21 | xargs -r sudo rm -v

# Снимки старше 30 дней (dry-run)
find /opt/tgbots/utils/snapshots -type f -name 'app.*.txt' -mtime +30 -print

# Удалить снимки старше 30 дней
find /opt/tgbots/utils/snapshots -type f -name 'app.*.txt' -mtime +30 -delete

# Диагностика/трейсы старше 21 дня
find /opt/tgbots/utils/diag -type f -mtime +21 -print
find /opt/tgbots/utils -maxdepth 1 -type f -name 'trace-*.txt' -mtime +21 -print

# Удалить:
find /opt/tgbots/utils/diag -type f -mtime +21 -delete
find /opt/tgbots/utils -maxdepth 1 -type f -name 'trace-*.txt' -mtime +21 -delete

## Контроль диска
df -h /opt
du -sh /opt/tgbots/bots/support/app.bak.*.py 2>/dev/null | awk '{s+=$1} END{print "total (human): check per-file"}'

## Автоматизация (cron/systemd timer) — идея
- Раз в сутки: удалять старые снимки/логи по правилам выше.
- Перед удалением больших объёмов — делать свежий снимок состояния и короткий отчёт.
```

### BASELINE_ROLLBACK_POLICY.txt

```text
# Политика baseline/rollback для app.py

Цель: любые правки `app.py` проходят через снимки (snapshot) и создают бэкапы с автопроверками.
Живая логика guard в systemd сейчас отключена, но политика остаётся — чтобы не ловить "тихие" поломки.

## Артефакты и пути
- Текущий файл: `/opt/tgbots/bots/support/app.py`
- Бэкапы: `/opt/tgbots/bots/support/app.bak.*.py`
- Снимки (чисто информационные): `/opt/tgbots/utils/snapshots/app.YYYYMMDD-HHMMSSZ.txt`
- Диагностика: `/opt/tgbots/utils/diag/diag-*.txt`, `/opt/tgbots/utils/trace-*.txt`
- Базовая мета (если используется): `/opt/tgbots/utils/app.baseline.json`

## Когда обновлять baseline
- Только когда текущий `app.py` стабильно работает в проде и пройдено ручное тестирование.
- После обновления baseline — дальнейшие патчи сверяем против него (чтобы ловить неожиданные различия).

## Строгий порядок внесения правок
1) Снимок до правки:
   /opt/tgbots/utils/snapshot_app.sh /opt/tgbots/bots/support/app.py
2) Применение патча (любой безопасный apply-скрипт, формата: создать TMP → py_compile → atomically install → restart).
3) Автотест запуска (журнал за последние ~300 строк).
4) Если есть ошибки — автооткат на последний бэкап и сохранение трейса.

## Откат (ручной)
# Посмотреть доступные бэкапы
ls -1t /opt/tgbots/bots/support/app.bak.*.py | head

# Выбрать нужный и восстановить
cp -v /opt/tgbots/bots/support/app.bak.<STAMP>.py /opt/tgbots/bots/support/app.py
systemctl restart tgbot@support.service
journalctl -u tgbot@support.service -n 200 --no-pager

## Обновление baseline под текущий рабочий app.py (по необходимости)
# Создать/пересоздать baseline-мета и референсный снимок
/opt/tgbots/utils/app_baseline.sh
# Проверить: /opt/tgbots/utils/app.baseline.json и снимок в /opt/tgbots/utils/snapshots/

## Типовые инциденты и реакция
- Изменился размер/хэш app.py “сам по себе”: сразу делаем снимок, смотрим diff и откатываемся на ближайший рабочий бэкап.
- Патч применился, но бот не стартует: журнал + автосозданный trace; затем откат на `/opt/tgbots/bots/support/app.bak.*.py`.

## Антипаттерны
- Редактировать `app.py` напрямую в месте — без TMP/py_compile и бэкапа.
- Обновлять baseline “на горячую”, если код ещё не проверен.
```

### VENV_LAYOUT.txt

```text
# VENV_LAYOUT — где живёт Python окружение и как им пользоваться

## Расположение
- Основное виртуальное окружение: `/opt/tgbots/.venv`
- Рабочий код бота: `/opt/tgbots/bots/support/app.py`

## Почему именно .venv
- Изоляция зависимостей от системного Python.
- Предсказуемые пути бинарей: `/opt/tgbots/.venv/bin/python`, `/opt/tgbots/.venv/bin/pip`.

## Базовые команды
# Проверка версий
/opt/tgbots/.venv/bin/python -V
/opt/tgbots/.venv/bin/pip -V

# Список пакетов / устаревшие
/opt/tgbots/.venv/bin/pip list
/opt/tgbots/.venv/bin/pip list --outdated

# Версия aiogram
/opt/tgbots/.venv/bin/python -c "import aiogram,sys;print(aiogram.__version__, sys.version)"

## Обновление зависимостей (безопасно)
# 1) Заморозка текущего состояния (на случай отката)
mkdir -p /opt/tgbots/utils/pins
/opt/tgbots/.venv/bin/pip freeze > /opt/tgbots/utils/pins/requirements.freeze.txt

# 2) Прицельное обновление (пример: aiogram)
/opt/tgbots/.venv/bin/pip install --upgrade "aiogram>=3,<4"

# 3) Проверка обратной совместимости
/opt/tgbots/.venv/bin/python -m py_compile /opt/tgbots/bots/support/app.py

# 4) Если что-то сломалось — откат зависимостей
/opt/tgbots/.venv/bin/pip install -r /opt/tgbots/utils/pins/requirements.freeze.txt

## Запрещённые практики
- Не использовать системный `pip`/`python` для установки пакетов бота.
- Не смешивать второе окружение `venv/` с `.venv`. Если есть лишний каталог `venv/`, удалить/архивировать.

## Советы
- Команды внутри unit-файлов всегда указываем полные пути из `.venv`.
- При апдейтах фиксируем версии (pin) ключевых пакетов: aiogram, aiohttp, pydantic.
```

### SIDE_CAR_TESTWATCH_README.txt

```text
# Sidecar: наблюдатель тест-пользователя (tgbot-testwatch.service)

## Назначение
Независимый от основного бота процесс, который опрашивает Telegram API `getChatMember` для пары
(TEST_CHAT_ID, TEST_USER_ID) и при первом стабильном входе в чат отправляет DM тест-юзеру.
Служит для безопасной отладки “новичка”, не трогая основной код `app.py`.

## Файлы и пути
- Юнит systemd:      /etc/systemd/system/tgbot-testwatch.service
- Скрипт сайдкара:   /opt/tgbots/utils/sidecar_testuser_watch.py
- Состояние:         /var/lib/tgbots/testwatch/testuser.status
- Форс-уведомление:  /opt/tgbots/utils/force_testuser_notify.sh
- Зонд членства:     /opt/tgbots/utils/probe_membership.sh
- Переменные:        /etc/tgbots/support.env

## Обязательные переменные окружения (support.env)
- BOT_TOKEN            — токен бота (тот же, что у основного инстанса)
- TEST_CHAT_ID         — id тестового чата (отрицательный для супергруппы)
- TEST_USER_ID         — id тест-пользователя
- TESTWATCH_DM_TEXT    — (опц.) текст первого DM при входе

Проверка:
  /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

## Состояние (state file)
/var/lib/tgbots/testwatch/testuser.status — плоский k=v:
- last=in|out        — последнее известное состояние
- stable_in=INT      — счётчик стабильных подряд опросов «в чате»
- last_notify=UNIX   — когда отправили DM (0 — ещё не отправляли)
- ts=UNIX            — время последней записи

Сбросить (перед новой сессией теста):
  sudo rm -f /var/lib/tgbots/testwatch/testuser.status

## Логика (FSM)
1) Каждые 3–4 сек делать `getChatMember(TEST_CHAT_ID, TEST_USER_ID)`
2) status → cur: {member|administrator|creator} → in, иначе out
3) Если переход out→in и last_notify==0 → отправить DM 1 раз, записать last_notify=now
4) Если переход in→out → last=in→out, stable_in=0 (готовы поймать повторный вход)
5) Печатать телеметрию в journal: `poll last=<...> status_api=<...> stable_in=<...> last_notify=<...>`

## Запуск/статус
- Включить автозапуск:
    sudo systemctl enable --now tgbot-testwatch.service
- Статус/лог:
    systemctl status tgbot-testwatch.service --no-pager
    journalctl -u tgbot-testwatch.service -n 100 --no-pager
- Перезапустить:
    sudo systemctl restart tgbot-testwatch.service

## Утилиты
- Ручной пинг в DM (проверка токена и диалога):
    /opt/tgbots/utils/force_testuser_notify.sh /etc/tgbots/support.env
- Проверка членства:
    /opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env
  Ожидаемые статусы: left|kicked|restricted|member|administrator|creator

## Требования к правам
- Скрипты в /opt/tgbots/utils — исполняемые: `chmod +x`
- Владелец /var/lib/tgbots/testwatch и state-файла — tgbot:tgbot, режим 0644/0664
- У юнита User=tgbot, Group=tgbot есть доступ R к /etc/tgbots/support.env и RW к /var/lib/tgbots/testwatch

Быстрая починка:
  sudo chown -R tgbot:tgbot /var/lib/tgbots /opt/tgbots/utils
  sudo chmod -R u+rwX,g+rwX /opt/tgbots/utils
  sudo find /opt/tgbots/utils -type f -name "*.sh" -exec chmod +x {} \;

## Типичные проблемы и решения
- Юнит «flaps» (часто рестартится), в журнале нет логов скрипта → проверь BOT_TOKEN/TEST_* в env.
- DM не приходит, ручной пинг OK → `last_notify!=0` (уже слали). Удалить state для повторного теста.
- `status_api` всегда left → тест-юзер реально вне чата или чат неверный. Сверить TEST_CHAT_ID.
- Read-only FS на /opt или /var → исправить монтирование до RW.

## Безопасность
Сайдкар не правит БД, не трогает `app.py`, не требует перезапуска основного сервиса. Вся логика — опрос API и локальный state.
```

### PERMISSIONS_OWNERSHIP_README.txt

```text
# Права и владельцы (permissions & ownership)

## Почему критично
- Бот (user=tgbot) должен читать .env, писать в свой SQLite и логи, запускать утилиты в /opt/tgbots/utils.
- Любые “permission denied”/read-only ломают автозапуск, снапшоты и диагностику.

## Базовые ожидания
- Владелец каталога проекта: tgbot:tgbot
- Исполняемые скрипты utils: 0755 или 0775 (для группы tgbot)
- Файлы данных (db, state): 0664, каталоги: 0775

## Ключевые пути
- Код:              /opt/tgbots/bots/support/app.py
- Виртуалка:        /opt/tgbots/.venv
- Конфиг (.env):    /etc/tgbots/support.env
- БД:               /opt/tgbots/bots/support/join_guard_state.db
- Утилиты:          /opt/tgbots/utils
- Диагностика:      /opt/tgbots/bots/support/diag
- Снэпшоты:         /opt/tgbots/utils/snapshots
- Сайдкары/хуки:    /opt/tgbots/utils/hooks
- Состояния:        /var/lib/tgbots (подсистемы могут класть state сюда)

## Быстрая починка владельцев/прав
# ВНИМАНИЕ: команды idempotent, безопасны для «починки» окружения
sudo chown -R tgbot:tgbot /opt/tgbots /var/lib/tgbots
sudo chown -R root:root   /etc/tgbots
sudo chmod -R u+rwX,g+rwX /opt/tgbots
sudo chmod -R u+rwX       /var/lib/tgbots
sudo chmod     0640       /etc/tgbots/support.env
sudo chmod -R  u+rwX,g+rwX /opt/tgbots/utils
sudo find /opt/tgbots/utils -type f -name "*.sh" -exec chmod +x {} \;
sudo find /opt/tgbots/utils -type f -name "*.py" -exec chmod +x {} \;

## Точки отказа (симптомы → решение)
- systemd пишет: Read-only file system
  → ФС/монтирование: проверь `mount | grep ' /opt '`; если сборка контейнерная, убедись, что /opt RW.
- SNAPSHOT MISMATCH при старте
  → Убедись, что /opt/tgbots/utils/snapshots доступен для записи и время системы корректно.
- sqlite «database is locked»
  → Убедись, что владелец БД — tgbot и активных процессов, держащих файл, нет. Проверь `lsof` (если доступен).

## Проверка текущего состояния
namei -l /etc/tgbots/support.env
namei -l /opt/tgbots/bots/support
namei -l /opt/tgbots/bots/support/join_guard_state.db
namei -l /opt/tgbots/utils
ls -l /opt/tgbots/utils | sed -n '1,80p'
```

### TESTWATCH_SIDECAR.txt

```text
=== TESTWATCH_SIDECAR — наблюдатель за тестовым новичком =======================

НАЗНАЧЕНИЕ
- Вне основного бота, отдельным сервисом отслеживает статус TEST_USER_ID в TEST_CHAT_ID.
- При первом стабильном входе отправляет одному пользователю (DM) один раз уведомление.
- Держит собственное состояние на диске, чтобы избежать повторных отправок.

ФАЙЛЫ
- Скрипт: /opt/tgbots/utils/sidecar_testuser_watch.py
- Юнит:  /etc/systemd/system/tgbot-testwatch.service
- Env:   /etc/tgbots/support.env  (используется тем же окружением, что и бот)
- State: /var/lib/tgbots/testwatch/testuser.status
         формат key=value (last, stable_in, last_notify, ts)

ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ В /etc/tgbots/support.env
- BOT_TOKEN=...                       # токен бота
- TEST_CHAT_ID=-100...                # id тестового чата
- TEST_USER_ID=...                    # id тест-пользователя (человек)
- TESTWATCH_DM_TEXT="🔔 Тестовое уведомление ..."   # текст DM (опционально)
- (опц.) ENV_FILE=/etc/tgbots/support.env           # для sidecar; по умолчанию так и есть

ЛОГИКА РАБОТЫ
- Каждые ~3 секунды вызывает getChatMember(chat_id, user_id).
- Определяет cur статус: "in" если member/administrator/creator, иначе "out".
- Считает stable_in (сколько последовательных опросов «in»).
- Отправляет DM один раз при переходе out->in при условии last_notify == 0.
- Сохраняет состояние в /var/lib/tgbots/testwatch/testuser.status.

КОМАНДЫ УПРАВЛЕНИЯ (systemd)
- Включить автозапуск:
    sudo systemctl enable --now tgbot-testwatch.service
- Проверить статус:
    systemctl status tgbot-testwatch.service --no-pager
- Логи (последние 200 строк):
    journalctl -u tgbot-testwatch.service -n 200 --no-pager
- Перезапуск:
    sudo systemctl restart tgbot-testwatch.service

ПРОВЕРКА РУКАМИ
- Пробный DM напрямую (обходит всю логику sidecar):
    /opt/tgbots/utils/probe_dm.sh                # использует support.env
- Проверить членство:
    /opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env
  ожидаемый JSON с "status": "member" / "left" и т.п.

СБРОС СОСТОЯНИЯ (для повторного теста «первого входа»)
- Остановить сервис:
    sudo systemctl stop tgbot-testwatch.service
- Удалить/очистить state:
    sudo rm -f /var/lib/tgbots/testwatch/testuser.status
  (допускается вручную записать last=out, stable_in=0, last_notify=0)
- Запустить сервис:
    sudo systemctl start tgbot-testwatch.service

ТИПОВЫЕ ПРОБЛЕМЫ
1) Сервис мгновенно перезапускается без логов
   - Проверь, что файл скрипта исполняемый:
       ls -l /opt/tgbots/utils/sidecar_testuser_watch.py
       sudo chmod +x /opt/tgbots/utils/sidecar_testuser_watch.py
   - Убедись, что EnvironmentFile существует и содержит BOT_TOKEN/TEST_CHAT_ID/TEST_USER_ID.

2) В логах только poll last=out, статус не меняется
   - Проверь фактическое членство:
       /opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env
   - В Telegram действительно ли TEST_USER_ID в тестовом чате?

3) DM не приходит, но ручной пинг работает
   - Проверь state: last_notify может быть ненулевым.
       sudo cat /var/lib/tgbots/testwatch/testuser.status || true
   - Сбрось состояние (см. выше) и повтори вход в чат.

4) Нет прав на запись state
   - Дай права каталогу:
       sudo mkdir -p /var/lib/tgbots/testwatch
       sudo chown -R tgbot:tgbot /var/lib/tgbots/testwatch
       sudo chmod -R u+rwX,g+rwX /var/lib/tgbots/testwatch

ОБНОВЛЕНИЕ/ПРАВКИ СИДЕКАРА
- Скрипт простой, без внешних зависимостей, HTTP через urllib.
- Для модификаций предпочтительно: копия -> правка -> systemctl restart tgbot-testwatch.service.
- Диагностику смотри через journalctl (см. выше).

БЕЗОПАСНОСТЬ
- Юнит работает под пользователем tgbot, без повышенных прав.
- Не трогает БД бота, хранит лишь текстовый state.
- Токен читается из ENV (support.env); сам токен в логах не печатается, только хвост.

===============================================================================
КРАТКО
- Сервис tgbot-testwatch.service читает support.env, опрашивает getChatMember и 1 раз шлёт DM при первом входе тест-пользователя. Состояние — в /var/lib/tgbots/testwatch/testuser.status. Управление — через systemctl; отладка — journalctl.
```

### PATCH_APPLY_WORKFLOW.txt

```text
=== PATCH_APPLY_WORKFLOW — как безопасно вносить правки в app.py =================

ЦЕЛЬ
- Делать правки без прямого редактирования app.py.
- Всегда иметь снимок (snapshot), бэкап и автоматический откат при сбоях.

КЛЮЧЕВЫЕ СКРИПТЫ (де-факто)
- /opt/tgbots/utils/snapshot_app.sh            — делает текстовый снапшот app.py (хеш, head, py_compile)
- /opt/tgbots/utils/app_safe_apply.sh          — «строгий» применитель патча (с бэкапом, компиляцией, рестартом и авто-роллбэком по логам)
- /opt/tgbots/utils/app_quick_apply.sh         — «быстрый» применитель (снимок + применить + рестарт + первичная проверка)
- /opt/tgbots/utils/diag_collect.sh            — полный сбор диагностики после проблемы
- /opt/tgbots/utils/snapshots/                 — каталог с текстовыми снапшотами

ГДЕ ПАТЧ?
- Патч — это обычный Python-скрипт, который принимает путь к ВРЕМЕННОЙ копии app.py
  и изменяет её на месте. Пример подписи:
    #!/usr/bin/env python3
    import sys, pathlib
    APP = pathlib.Path(sys.argv[1])
    src = APP.read_text(encoding="utf-8")
    # ... меняем текст ...
    APP.write_text(src, encoding="utf-8")
    print("OK: patch applied")

БАЗОВЫЕ ПРАВИЛА
1) Никогда не правим /opt/tgbots/bots/support/app.py руками.
2) Любая правка идёт через временный файл + проверку компиляции + рестарт сервиса.
3) Если после рестарта в журнале ловим «fatal»/Traceback — код откатывается на бэкап.

ШАГИ «СТРОГОГО» ПРИМЕНЕНИЯ (app_safe_apply.sh)
1) Сделать рабочую копию (скрипт сам создаст tmp):
   sudo -E /opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/YOUR_PATCH.py /path/will/be/auto

   Что делает:
   - Снимает snapshot текущего app.py
   - Делает бэкап app.bak.YYYYMMDD-HHMMSSZ.py
   - Создаёт временный файл app.tmp.YYYYMMDD-HHMMSSZ.py
   - Запускает ваш патч с путём к tmp
   - Компилирует tmp (python -m py_compile)
   - Устанавливает tmp как app.py и перезапускает tgbot@support.service
   - Читает журнал; при ошибках — откатывает на бэкап и сохраняет trace-*.txt

2) Проверка результата:
   journalctl -u tgbot@support.service -n 200 --no-pager

3) Если всё ок — работаем дальше; если нет — см. «ОТКАТ».

ШАГИ «БЫСТРОГО» ПРИМЕНЕНИЯ (app_quick_apply.sh)
1) Когда нужен упрощённый цикл:
   sudo -E /opt/tgbots/utils/app_quick_apply.sh python3 /opt/tgbots/utils/YOUR_PATCH.py

   Скрипт делает:
   - Снапшот
   - Применение патча к tmp
   - Установка как app.py
   - Перезапуск
   - Базовая проверка журнала; при фаталах — мгновенный откат

КОГДА КАКОЙ?
- app_safe_apply.sh — по умолчанию; максимум страховок.
- app_quick_apply.sh — для мелких правок/экспериментов, когда важна скорость, но всё равно есть роллбэк.

ОТКАТ (если сервис упал после патча)
1) Посмотреть, какой бэкап последний:
   ls -1t /opt/tgbots/bots/support/app.bak.*.py | head -n1

2) Восстановить:
   sudo cp -v /opt/tgbots/bots/support/app.bak.YYYYMMDD-*.py /opt/tgbots/bots/support/app.py
   sudo chown tgbot:tgbot /opt/tgbots/bots/support/app.py
   sudo systemctl restart tgbot@support.service

3) Снять диагностику сбоя:
   /opt/tgbots/utils/diag_collect.sh
   # смотрим путь к diag-*.txt в конце вывода

ТРИГГЕРЫ ДЛЯ АВТО-РОЛЛБЭКА
- В журнале после рестарта найдены строки:
  • Traceback / SyntaxError / IndentationError / NameError
  • database is locked (в критических местах)
  • Любые «fatal patterns», указанные в применяющем скрипте
- В этих случаях app_safe_apply.sh и app_quick_apply.sh сами откатят app.py и положат trace-YYYYMMDD-HHMMSSZ.txt в /opt/tgbots/utils/

ПРОВЕРКИ ПЕРЕД ПАТЧЕМ
- Компиляция текущего файла:
  python3 -m py_compile /opt/tgbots/bots/support/app.py || echo "PY_COMPILE_FAIL"
- Снимок:
  /opt/tgbots/utils/snapshot_app.sh /opt/tgbots/bots/support/app.py

ЧИСТКА СТАРЫХ СНАПШОТОВ/ТРЕЙСОВ (по необходимости)
- Сохранить N последних, остальные архивировать/удалять — делается вручную или отдельным cron/скриптом (пока не автоматизировано).

==============================================================================

КРАТКО
- Патч — отдельный Py-скрипт -> app_safe_apply.sh / app_quick_apply.sh -> авто-снапшот, бэкап, компиляция, рестарт, проверка журналов -> при проблемах авто-откат + трейс в /opt/tgbots/utils/.
- Никакой ручной правки app.py. Всегда воспроизводимый процесс.
```

### RUNTIME_DIAG.txt

```text
=== RUNTIME_DIAG — быстрая диагностика инстанса "support" ======================

ЦЕЛЬ
- Дать пошаговые команды для проверки окружения, сервисов, логов, БД и сетевых вызовов Telegram.
- Используем только готовые утилиты из /opt/tgbots/utils, без ручного редактирования кода.

БЫСТРЫЙ ЧЕК-ЛИСТ (копируй построчно)
1) Состояние сервиса:
   systemctl status tgbot@support.service --no-pager || true
   journalctl -u tgbot@support.service -n 300 --no-pager

2) Снимок env (без токенов) и ключевых переменных:
   /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

3) Снапшот кода (хеш, первые строки, py_compile):
   /opt/tgbots/utils/snapshot_app.sh /opt/tgbots/bots/support/app.py

4) Полный сбор диагностики (логи, env-эффективный, БД, права, и т.д.):
   /opt/tgbots/utils/diag_collect.sh
   # В конце покажет путь к файлу вида: /opt/tgbots/utils/diag/diag-YYYYMMDD-HHMMSSZ.txt

5) Проверка связи с Telegram (быстрые зонды):
   # Личные сообщения тест-юзеру (проверка DM)
   /opt/tgbots/utils/probe_dm.sh
   # Статус членства тест-юзера в тестовом чате
   /opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env

6) Проверка доступности БД и схемы:
   sqlite3 /opt/tgbots/bots/support/join_guard_state.db ".tables"
   sqlite3 /opt/tgbots/bots/support/join_guard_state.db "PRAGMA integrity_check;"

7) Проверка прав и монтирования:
   namei -l /opt/tgbots/bots/support/join_guard_state.db
   mount | grep ' /opt ' || true

ТИПОВЫЕ СИМПТОМЫ → ПРИЧИНЫ → ДЕЙСТВИЯ
A) Сервис не стартует без трейсбэка, но быстро «падает»
   - Возможные причины:
     • Несовпадение снапшота (контрольная сумма/размер).
     • Нет доступа на запись (read-only FS, права).
     • Не хватает env переменных (BOT_TOKEN, TEST_CHAT_ID и пр.).
   - Что делать:
     • Посмотреть последние строки журнала:
       journalctl -u tgbot@support.service -n 200 --no-pager
     • Проверить снапшоты/хеш:
       /opt/tgbots/utils/snapshot_app.sh /opt/tgbots/bots/support/app.py
     • Проверить права на /opt/tgbots/bots/support и БД:
       namei -l /opt/tgbots/bots/support
       namei -l /opt/tgbots/bots/support/join_guard_state.db

B) Бот работает, но «молчит» (нет реакции/DM)
   - Возможные причины:
     • Telegram запрос уходит, но бот заблокирован пользователем.
     • Логика фильтров отбрасывает апдейты (allowlist, router-правила).
     • Ошибка в переменных окружения (не тот чат/пользователь).
   - Действия:
     • Проверить probe_dm.sh и probe_membership.sh (см. выше).
     • Просмотреть логи за период и grep по ключам:
       journalctl -u tgbot@support.service -n 400 --no-pager | egrep -i "NEWCOMER|JOIN|notify|error|traceback" || true
     • Проверить /etc/tgbots/support.env через echo_env.sh.

C) «database is locked» / таймауты БД
   - Причины:
     • Долгие транзакции или параллельные записи.
   - Действия:
     • Снизить конкуренцию, проверить busy_timeout/journal_mode.
     • При необходимости: systemctl stop tgbot@support.service && sqlite3 "$SQLITE_PATH" "VACUUM;" && systemctl start tgbot@support.service

D) Read-only filesystem (ROFS)
   - Симптомы:
     • Логи «Read-only file system» при записи в /opt/tgbots/utils/* или в БД.
   - Действия:
     • Проверить монтирование:
       mount | grep ' /opt ' || true
     • Если это bind/RO-монтаж — вернуть RW или писать в разрешённые пути:
       - /opt/tgbots/bots/support (RW — задаётся в юните через ReadWritePaths)
       - /var/lib/tgbots (создать и chown tgbot:tgbot)

E) Ошибки импорта/версии
   - Проверить версию Python и aiogram в активном venv:
     /opt/tgbots/.venv/bin/python -V
     /opt/tgbots/.venv/bin/pip show aiogram
   - Если используется другой venv — убедиться, что юнит ссылается на правильный интерпретатор.

«ПЛЕЙБУК» ВОССТАНОВЛЕНИЯ
1) Снимок диагностики:
   /opt/tgbots/utils/diag_collect.sh
2) Быстрый перезапуск:
   sudo systemctl restart tgbot@support.service
3) Если сломался код/патч:
   - выбрать рабочую резервную копию /opt/tgbots/bots/support/app.bak.*.py
   - заменить текущий app.py
     sudo cp -v /opt/tgbots/bots/support/app.bak.YYYYMMDD-*.py /opt/tgbots/bots/support/app.py
     sudo chown tgbot:tgbot /opt/tgbots/bots/support/app.py
   - перезапуск сервиса:
     sudo systemctl restart tgbot@support.service
4) Проверка «ожила ли» обработка апдейтов:
   journalctl -u tgbot@support.service -n 200 --no-pager | egrep -i "Start polling|Run polling|Update id="

ОКРУЖЕНИЕ И ПУТИ (де-факто)
- Код:           /opt/tgbots/bots/support/app.py
- ENV:           /etc/tgbots/support.env
- Venv (основной): /opt/tgbots/.venv
- БД:            /opt/tgbots/bots/support/join_guard_state.db
- Диаг-скрипты:  /opt/tgbots/utils/*
- Документация:  /opt/tgbots/utils/docs/*

ЗАПОМНИТЬ
- Никаких «горячих правок» в коде без фиксации снапшота и бэкапа.
- Любая ошибка → сначала сбор диагностики, потом откат, потом правка через аккуратный патч+проверка.

===============================================================================
```

### DB_SCHEMA_NOTES.txt

```text
=== DB_SCHEMA_NOTES — SQLite для инстанса "support" ============================

ФАЙЛ БД
- Путь (переменная SQLITE_PATH в env):
  /opt/tgbots/bots/support/join_guard_state.db

ПРАВА И БЕЗОПАСНОСТЬ
- Рекомендуется: chown tgbot:tgbot, chmod 664 (или 660)
- Родительские директории должны быть доступны пользователю tgbot.
- Проверка цепочки прав: namei -l /opt/tgbots/bots/support/join_guard_state.db

АКТУАЛЬНЫЕ ТАБЛИЦЫ (де-факто)
1) pending_requests
   - purpose: заявки на вступление (join requests), которые бот видит и обрабатывает
   - примерные поля (может отличаться по типам):
       id INTEGER PRIMARY KEY AUTOINCREMENT
       chat_id INTEGER NOT NULL
       user_id INTEGER NOT NULL
       date_ts INTEGER NOT NULL         -- unix time
       status TEXT NOT NULL             -- 'pending'|'approved'|'rejected'
       payload TEXT                     -- сырой json / доп.инфо
   - индексы: (chat_id, user_id), (status)

2) approvals
   - purpose: сохранение факта авторизации/разрешения на писанину и/или снятие ограничений
   - поля:
       id INTEGER PRIMARY KEY AUTOINCREMENT
       chat_id INTEGER NOT NULL
       user_id INTEGER NOT NULL
       approved_ts INTEGER NOT NULL
       approver_id INTEGER               -- кто подтвердил (если есть)
       note TEXT                         -- комментарий
   - индексы: (chat_id, user_id), approved_ts

3) newcomer_seen   (используется опционально, когда включена логика «новичка»)
   - purpose: фиксирует «первое замечание» пользователя в чате для окна NEWCOMER_WINDOW_SECONDS
   - поля:
       chat_id INTEGER NOT NULL
       user_id INTEGER NOT NULL
       first_seen_ts INTEGER NOT NULL
       PRIMARY KEY(chat_id, user_id)

ПРОВЕРКА СХЕМЫ
- Список таблиц:
  sqlite3 "$SQLITE_PATH" ".tables"
- Структура:
  sqlite3 "$SQLITE_PATH" "PRAGMA table_info(pending_requests);"
  sqlite3 "$SQLITE_PATH" "PRAGMA table_info(approvals);"
  sqlite3 "$SQLITE_PATH" "PRAGMA table_info(newcomer_seen);"

ИНДЕКСЫ (рекомендации)
- Для массовых выборок по chat_id/user_id:
  CREATE INDEX IF NOT EXISTS idx_pending_chat_user ON pending_requests(chat_id, user_id);
  CREATE INDEX IF NOT EXISTS idx_approvals_chat_user ON approvals(chat_id, user_id);
- Для поиска по статусу:
  CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_requests(status);
- Для временных диапазонов:
  CREATE INDEX IF NOT EXISTS idx_approvals_ts ON approvals(approved_ts);

ВАЛИДАЦИЯ И ОБСЛУЖИВАНИЕ
- Проверка целостности:
  sqlite3 "$SQLITE_PATH" "PRAGMA integrity_check;"
- Режим журналирования и таймаут:
  sqlite3 "$SQLITE_PATH" "PRAGMA journal_mode; PRAGMA busy_timeout;"
- VACUUM (сжимает базу; делать при остановленном сервисе):
  systemctl stop tgbot@support.service
  sqlite3 "$SQLITE_PATH" "VACUUM;"
  systemctl start tgbot@support.service

БЕКАП
- Горячий бэкап через .backup (без остановки, но лучше с низкой нагрузкой):
  sqlite3 "$SQLITE_PATH" ".backup '/opt/tgbots/bots/support/join_guard_state.db.bak.$(date -u +%Y%m%d-%H%M%SZ)'"
- Холодный бэкап (надёжнее): остановить сервис, скопировать файл, запустить сервис.

ТИПОВЫЕ ЗАПРОСЫ
- Найти открытые заявки в чате:
  SELECT * FROM pending_requests WHERE chat_id=? AND status='pending' ORDER BY date_ts DESC LIMIT 50;
- Отметить одобрение:
  INSERT INTO approvals(chat_id,user_id,approved_ts,approver_id,note) VALUES (?,?,?,?,?);
- Пометить «первое замечание» новичка:
  INSERT OR IGNORE INTO newcomer_seen(chat_id,user_id,first_seen_ts) VALUES (?,?,?);

МИГРАЦИИ
- Схема не зацементирована — возможны ALTER TABLE/CREATE TABLE IF NOT EXISTS при обновлениях.
- Общий подход:
  1) Создать новые таблицы/индексы через IF NOT EXISTS.
  2) Для изменения существующих полей — либо ALTER TABLE ADD COLUMN, либо
     временная таблица + копирование + переименование.
  3) Всегда делать бэкап перед миграцией и иметь план отката.

ДИАГНОСТИКА (быстрые команды)
- Диаг-скрипт (не светит токен): /opt/tgbots/utils/diag_collect.sh
- Хвост журнала systemd:
  journalctl -u tgbot@support.service -n 300 --no-pager | egrep -i 'Traceback|database is locked|sqlite|NEWCOMER|JOIN|ERROR' || true

ЧАСТЫЕ ПРОБЛЕМЫ
- "database is locked"
  * решить контеншен, увеличить PRAGMA busy_timeout, убедиться что нет долгих транзакций.
- Нет таблицы newcomer_seen
  * включена логика новичка — создать таблицу:
    CREATE TABLE IF NOT EXISTS newcomer_seen (
      chat_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      first_seen_ts INTEGER NOT NULL,
      PRIMARY KEY(chat_id, user_id)
    );
- Права на файл/директорию мешают записи
  * проверь namei -l, chown/chmod для tgbot.

===============================================================================
```

### ENV_AND_SECRETS.txt

```text
=== ENV_AND_SECRETS — окружение и секреты ======================================

ФАЙЛЫ ОКРУЖЕНИЯ
- Главный env для инстанса "support":
  /etc/tgbots/support.env

- Примеры других инстансов (по шаблону):
  /etc/tgbots/<instance>.env

ТРЕБОВАНИЯ К ПРАВАМ
- Доступ: только root и tgbot.
  chown root:tgbot /etc/tgbots/support.env
  chmod 640 /etc/tgbots/support.env

КЛЮЧЕВЫЕ ПЕРЕМЕННЫЕ
- BOT_TOKEN=...               # Токен Telegram бота (секрет!)
- VERIFY_SECRET=...           # Секрет для внутренних хуков (если используется)

- SQLITE_PATH=/opt/tgbots/bots/support/join_guard_state.db
  # путь к SQLite БД состояния

- UTILS_DIR=/opt/tgbots/utils  # служебные утилиты

- TARGET_CHAT_IDS= -100..., -100...
- TARGET_CHAT_ID= -100...      # список/один целевой чат для join-request логики
- ADMIN_IDS= 12345, 67890      # статический список админов (если нужен)

- DELETE_SYSTEM_MESSAGES=true|false        # удалять системные "user joined" и т.п.
- LOCKDOWN_NONADMIN_BOTS=true|false        # жёсткая блокировка сторонних ботов
- AGGRESSIVE_CHANNEL_ANTILINK=true|false   # агрессивное удаление ссылок-каналов

- TEST_CHAT_ID= -1002099408662
- TEST_USER_ID= 6700029291
- TRACE_TEST_CHAT=true|false   # подробный трассинг тест-чата

- NEWCOMER_WINDOW_SECONDS=86400 # окно "новичка" (секунды)
- NEWCOMER_TEST_ONLY=1          # включать логику новичка только для тест-пары

- DIAG_ENABLE=1                 # включает автодиагностику в юните
- DIAG_DIR=/opt/tgbots/bots/support/diag
- DIAG_BASENAME=diag
- DIAG_DB_ROWS=20
- DIAG_KEEP=15                  # сколько файлов диагностики хранить

- ENABLE_HOOKS=1
- HOOKS_DIR=/opt/tgbots/utils/hooks
  # если используется механизм внешних «хуков» (модулей)

- TESTWATCH_DM_TEXT="🔔 Тестовое уведомление: зафиксирован вход в чат."
  # текст сообщения для сайдкара тестового наблюдателя (если запущен)

БЕЗОПАСНАЯ ПРОВЕРКА ОКРУЖЕНИЯ
- Не светим секреты (скрипт сам скрывает):
  /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env
  # вывод: TEST_CHAT_ID, TEST_USER_ID, NEWCOMER_WINDOW_SECONDS, NEWCOMER_TEST_ONLY, SQLITE_PATH, UTILS_DIR

ТОЧЕЧНАЯ ПРОСМОТР/ПОПРАВКА
- Показать ключевые значения (без секретов):
  awk -F= '!/^(BOT_TOKEN|VERIFY_SECRET)=/ {print}' /etc/tgbots/support.env

- Добавить/изменить значение:
  # пример — включить тест-режим для новичка
  sudo sed -i 's/^NEWCOMER_TEST_ONLY=.*/NEWCOMER_TEST_ONLY=1/' /etc/tgbots/support.env \
    || echo 'NEWCOMER_TEST_ONLY=1' | sudo tee -a /etc/tgbots/support.env >/dev/null

- После правок обязательно перезапустить сервис(ы):
  sudo systemctl restart tgbot@support.service
  # если используется сайдкар-тествотчер:
  sudo systemctl restart tgbot-testwatch.service

ВАЛИДАЦИЯ НАСТРОЕК (шпаргалка)
- Проверить, что переменные подгружаются:
  /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

- Убедиться, что БД доступна и есть таблицы:
  sqlite3 /opt/tgbots/bots/support/join_guard_state.db '.tables'

- Файл и права:
  ls -l /etc/tgbots/support.env
  namei -l /opt/tgbots/bots/support/join_guard_state.db

ШТОРМОВЫЕ СИТУАЦИИ
- «SNAPSHOT MISMATCH» в журнале:
  Это не про env, а про контроль целостности app.py. Сначала приводим app.py к эталону
  или обновляем baseline (см. PATCH_WORKFLOW.txt / SERVICE_TEMPLATES.txt).

- Бот не стартует после правок env:
  1) Проверить синтаксис (нет пробелов до/после ключа? нет кавычек, «умных» символов?)
  2) echo_env.sh — убедиться, что нужные переменные реально «видны»
  3) journalctl -u tgbot@support.service -n 200 --no-pager — посмотреть стек
  4) Вернуть предыдущее состояние env и рестартнуть

ПРИМЕР МИНИМАЛЬНОГО /etc/tgbots/support.env
-------------------------------------------------------------------------------
BOT_TOKEN=123456789:ABC...XYZ
VERIFY_SECRET=redacted
SQLITE_PATH=/opt/tgbots/bots/support/join_guard_state.db
UTILS_DIR=/opt/tgbots/utils

TARGET_CHAT_ID=-1002099408662
ADMIN_IDS=12345,67890

DELETE_SYSTEM_MESSAGES=true
LOCKDOWN_NONADMIN_BOTS=true
AGGRESSIVE_CHANNEL_ANTILINK=true

TEST_CHAT_ID=-1002099408662
TEST_USER_ID=6700029291
TRACE_TEST_CHAT=true

NEWCOMER_WINDOW_SECONDS=86400
NEWCOMER_TEST_ONLY=1

DIAG_ENABLE=1
DIAG_DIR=/opt/tgbots/bots/support/diag
DIAG_BASENAME=diag
DIAG_DB_ROWS=20
DIAG_KEEP=15

ENABLE_HOOKS=0
HOOKS_DIR=/opt/tgbots/utils/hooks

TESTWATCH_DM_TEXT=🔔 Тестовое уведомление: зафиксирован вход в чат.
-------------------------------------------------------------------------------

КРАТКИЕ КОМАНДЫ
- Печать env без секретов:
  /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

- Рестарт бота:
  sudo systemctl restart tgbot@support.service

- Рестарт тествотчера (если включен):
  sudo systemctl restart tgbot-testwatch.service

===============================================================================
```

### PATCH_WORKFLOW.txt

```text
=== PATCH_WORKFLOW — безопасное применение правок к app.py =====================

ЦЕЛЬ
- Вносить изменения в /opt/tgbots/bots/support/app.py без ручного редактирования.
- Гарантировать снапшот, бэкап, проверку компиляции, авто-сбор трейса и автоматический откат при ошибках.
- Исключить sed и опасные правки «в лоб».

КЛЮЧЕВЫЕ СКРИПТЫ
- /opt/tgbots/utils/snapshot_app.sh
  Делает снимок app.py: sha256, первые строки, py_compile.

- /opt/tgbots/utils/app_safe_apply.sh  <cmd> <args...>
  Универсальная «обёртка»: 
  1) создаёт SNAPSHOT, 
  2) делает BACKUP app.py, 
  3) копирует app.py -> app.tmp.$STAMP.py, 
  4) запускает patch-команду над TMP-файлом, 
  5) py_compile TMP, 
  6) ставит TMP как боевой app.py, 
  7) рестарт сервиса,
  8) слушает журнал, сохраняет TRACE, 
  9) если ловит фатальные паттерны — откатывает на BACKUP.

- /opt/tgbots/utils/app_quick_apply.sh <cmd> <args...>
  Упрощённый цикл для «быстрых» повторяемых патчей (без перезаписи baseline).

- /opt/tgbots/utils/diag_collect.sh
  Сводная диагностика после/перед патчем.

ОСНОВНЫЕ ПРАВИЛА
1) Не трогать app.py руками. Только через app_safe_apply.sh / app_quick_apply.sh.
2) Каждая правка — атомарный patch_*.py с чёткими якорями (anchors) и идемпотентной логикой.
3) Никаких sed/awk-хакингов по коду — только осмысленный парсинг/регексы в Python.
4) Всегда проверять py_compile и runtime-журнал; при ошибке — автоматический откат обязателен.
5) При необходимости обновить baseline (если текущее состояние признано эталоном) — делать явной командой.

ШАБЛОН РАБОЧЕГО ЦИКЛА
1) Снимок и диагностика (необязательно, но полезно):
   /opt/tgbots/utils/snapshot_app.sh
   /opt/tgbots/utils/diag_collect.sh

2) Применить патч:
   /opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/patch_my_change.py

   Обёртка:
   - сохранит BACKUP: /opt/tgbots/bots/support/app.bak.$STAMP.py
   - создаст TMP:     /opt/tgbots/bots/support/app.tmp.$STAMP.py
   - выполнит patch_my_change.py TMP
   - проверит компиляцию и перезапустит сервис
   - если в журнале обнаружены фатальные паттерны — сделает ROLLBACK и сохранит TRACE:
     /opt/tgbots/utils/trace-$STAMP.txt

3) Проверка:
   journalctl -u tgbot@support.service -n 200 --no-pager
   tail -n 200 /opt/tgbots/utils/trace-*.txt

4) При успешном патче серия таких изменений может потребовать «зафиксировать» baseline, чтобы снапшот-страж не ругался:
   /opt/tgbots/utils/app_baseline.sh
   # создаст/обновит /opt/tgbots/utils/app.baseline.json и снимок состояния

ФАТАЛЬНЫЕ ПАТТЕРНЫ (приводят к откату)
- Traceback|SyntaxError|IndentationError|NameError (регистронезависимо)
- SNAPSHOT MISMATCH (если включена защита снапшотом и sha/size не совпали)
- database is locked (многократно подряд)
- ModuleNotFoundError для критических импортов

БЫСТРЫЙ ОТКАТ (если нужно вручную)
- Посмотреть доступные бэкапы:
  ls -lt /opt/tgbots/bots/support/app.bak.*.py
- Откатиться на нужный (пример: самый свежий):
  cp -a /opt/tgbots/bots/support/app.bak.*.py /opt/tgbots/bots/support/app.py --backup=t
  systemctl restart tgbot@support.service

СТИЛЬ ПАТЧ-СКРИПТА (Python)
- Вход: путь к TMP-файлу app.py (argv[1]).
- Выход: переписанный TMP (на месте), stdout: «OK: ...», при ошибке — sys.exit(не 0).
- Идемпотентность: патч должен проверять, не добавлен ли блок раньше (метка/якорь).
- Безопасные якоря:
  * строка инициализации роутера:   ^\s*router\s*=\s*Router\(name="main"\)\s*$
  * комментарий-маркер после роутера: # \[SAFE-PATCH MARKER\] no-op marker after router init
  * включение router: dp.include_router(router)
  * функция main / dp.start_polling(...)
- Никогда не вставлять код «перед from __future__». Импорты будущего — строго первой строкой.
- Не трогать BOT_TOKEN и чувствительные места.
- После вставки — НЕ изменять форматирование вокруг import/логгеров без необходимости.

МИНИ-ШАБЛОН patch_*.py
-------------------------------------------------------------------------------
#!/usr/bin/env python3
import sys, re, pathlib

def die(msg, code=2):
    print(msg, file=sys.stderr); sys.exit(code)

def main():
    if len(sys.argv) < 2: die("ERR: app path missing", 2)
    app = pathlib.Path(sys.argv[1])
    if not app.is_file(): die("ERR: not a file: %s" % app, 2)
    src = app.read_text(encoding="utf-8")

    # пример: вставить блок сразу после router=Router(name="main")
    anchor = r'^\\s*router\\s*=\\s*Router\\(name="main"\\)\\s*$'
    if "## [my-patch] begin" in src:
        print("OK: already patched"); return

    m = re.search(anchor, src, flags=re.M)
    if not m: die("ERR: router anchor not found", 3)

    block = """
## [my-patch] begin
# ваш код здесь — стараться без внешних импортов, использовать существующие log/bot/dp/router
## [my-patch] end
""".lstrip()

    pos = m.end()
    src = src[:pos] + "\n" + block + src[pos:]
    app.write_text(src, encoding="utf-8")
    print("OK: patch applied")

if __name__ == "__main__":
    main()
-------------------------------------------------------------------------------

РАБОТА С BASELINE (если используется снапшот-контроль)
- Если защита включена и ругается на SNAPSHOT MISMATCH:
  1) Если текущее состояние верное — обновить baseline:
     /opt/tgbots/utils/app_baseline.sh
  2) Если нет — откатить app.py на подходящий app.bak.*.py.

ШПАРГАЛКИ
- Снять снапшот:
  /opt/tgbots/utils/snapshot_app.sh
- Применить патч:
  /opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/patch_xxx.py
- Быстрая серия патчей:
  /opt/tgbots/utils/app_quick_apply.sh python3 /opt/tgbots/utils/patch_xxx.py
- Диагностика:
  /opt/tgbots/utils/diag_collect.sh

===============================================================================
```

### DIAGNOSTICS_LOGS.txt

```text
=== Диагностика и логи ==========================================================

КУДА СМОТРЕТЬ СНАЧАЛА
- systemd-журнал сервиса бота:
  journalctl -u tgbot@support.service -n 300 --no-pager

- Трейсы автоприменения патчей (если использовались safe/quick apply):
  ls -1 /opt/tgbots/utils/trace-*.txt
  tail -n 200 /opt/tgbots/utils/trace-YYYYMMDD-HHMMSSZ.txt

- Сводная диагностика (скрипт собирает всё в один файл):
  /opt/tgbots/utils/diag_collect.sh
  tail -n 100 /opt/tgbots/utils/diag/diag-*.txt

КЛЮЧЕВЫЕ ЛОКАЦИИ
- Боевое приложение:      /opt/tgbots/bots/support/app.py
- Бэкапы приложения:      /opt/tgbots/bots/support/app.bak.*.py
- Снимки/сводки:          /opt/tgbots/utils/snapshots/
- Диагностика:            /opt/tgbots/utils/diag/
- Журналы (systemd):      journalctl -u tgbot@support.service
- БД sqlite:              /opt/tgbots/bots/support/join_guard_state.db
- Env-файл:               /etc/tgbots/support.env

ЧТО СЧИТАЕМ ФАТАЛЬНЫМИ ПАТТЕРНАМИ
- В журнале/трейсе присутствуют (регистронезависимо):
  Traceback | SyntaxError | IndentationError | NameError
  SNAPSHOT MISMATCH (несовпадение sha/size снапшота)
  database is locked (если повторяется)
  ModuleNotFoundError (для обязательных модулей)

БЫСТРЫЕ ФИЛЬТРЫ ЖУРНАЛА
- Последние ошибки:
  journalctl -u tgbot@support.service -n 400 --no-pager \
    | egrep -i 'Traceback|Error|Exception|SNAPSHOT|locked' || true

- Полный хвост:
  journalctl -u tgbot@support.service -n 400 --no-pager

- Логи только aiogram-событий:
  journalctl -u tgbot@support.service -n 400 --no-pager | grep 'aiogram.' || true

ПРОВЕРКИ ЦЕЛОСТНОСТИ И ОКРУЖЕНИЯ
- Снимок и компиляция кода:
  /opt/tgbots/utils/snapshot_app.sh
  # в файле SNAPSHOT будет sha256 и статус PY_COMPILE=OK/FAIL

- Проверка ключевых env (без токенов):
  /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

- Быстрая сверка sha/size app.py с baseline (если baseline ведётся):
  cat /opt/tgbots/utils/app.baseline.json  # см. sha/size
  sha256sum /opt/tgbots/bots/support/app.py

- Права/пермишены:
  namei -l /opt/tgbots/bots/support/join_guard_state.db
  namei -l /opt/tgbots/utils

- Проверка импортов/якорей в app.py (если скрипт есть):
  /opt/tgbots/utils/check_newcomer_anchors.sh /opt/tgbots/bots/support/app.py

SQLite БЫСТРАЯ ДИАГНОСТИКА
- Общий статус:
  sqlite3 /opt/tgbots/bots/support/join_guard_state.db \
    "PRAGMA journal_mode; PRAGMA busy_timeout; PRAGMA integrity_check; .tables;"

- Схема основных таблиц:
  sqlite3 /opt/tgbots/bots/support/join_guard_state.db \
    "PRAGMA table_info(pending_requests); PRAGMA table_info(approvals);"

ТИПОВЫЕ ПРИЧИНЫ НЕЗАПУСКА
1) SNAPSHOT MISMATCH
   — sha/size текущего app.py не совпал с эталонными.
   Решение: либо обновить baseline (если текущее состояние признано эталоном),
           либо откатить app.py на нужный бэкап.
   Команды:
     /opt/tgbots/utils/app_baseline.sh           # признать текущее состояние эталоном
     cp -a /opt/tgbots/bots/support/app.bak.*.py /opt/tgbots/bots/support/app.py --backup=t
     systemctl restart tgbot@support.service

2) Синтаксическая ошибка (py_compile FAIL / Traceback SyntaxError)
   — в патче/коде ошибка синтаксиса.
   Решение: откат + исправление патча → повторное применение.
   Команды:
     cp -a /opt/tgbots/bots/support/app.bak.*.py /opt/tgbots/bots/support/app.py --backup=t
     systemctl restart tgbot@support.service
     tail -n 200 /opt/tgbots/utils/trace-*.txt

3) Read-only filesystem при записи снапшота/трейса
   — система не даёт писать в /opt/tgbots/utils/ или /opt/tgbots/bots/support/
   Решение: remount rw (если уместно), поправить права:
     sudo chown -R tgbot:tgbot /opt/tgbots/utils /opt/tgbots/bots/support
     sudo chmod -R u+rwX,g+rwX /opt/tgbots/utils /opt/tgbots/bots/support

4) Неправильный ExecStart / рабочая директория
   — systemd запускает не тот файл/окружение.
   Проверка:
     systemctl cat tgbot@support.service
     systemctl show -p ExecStart -p WorkingDirectory tgbot@support.service

БЫСТРЫЕ РУТИНЫ
- Сбор полной диагностики:
  /opt/tgbots/utils/diag_collect.sh

- Применить патч с автотрейсом и автокатом:
  /opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/patch_*.py

- Быстрое применение (повторяемый патч):
  /opt/tgbots/utils/app_quick_apply.sh python3 /opt/tgbots/utils/patch_*.py

- Ручной откат на последний бэкап:
  cp -a /opt/tgbots/bots/support/app.bak.*.py /opt/tgbots/bots/support/app.py --backup=t
  systemctl restart tgbot@support.service

ПОЛЕЗНЫЕ МЕЛОЧИ
- Проверка версии aiogram в venv:
  /opt/tgbots/.venv/bin/pip show aiogram

- Пинг DM тест-юзеру (через вспомогательный скрипт, если есть):
  /opt/tgbots/utils/probe_dm.sh

- Проверка статуса участника (через getChatMember):
  /opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env

===============================================================================
```

### SNAPSHOTS_BASELINE.txt

```text
=== Снимки и бэкапы (baseline / snapshots / safe-apply) ==========================

ЦЕЛЬ
- Иметь эталон приложения (baseline), быстрые снимки перед правками (snapshots),
  атомарный откат при ошибке и чёткий след правок.

РАСПОЛОЖЕНИЯ
- app.py боевой:            /opt/tgbots/bots/support/app.py
- бэкапы app.py:            /opt/tgbots/bots/support/app.bak.YYYYMMDD-HHMMSSZ.py
- снапшоты метаданных:      /opt/tgbots/utils/snapshots/ (txt с sha256, head, py_compile)
- baseline-описание:        /opt/tgbots/utils/app.baseline.json
- диагностические трейсы:   /opt/tgbots/utils/trace-YYYYMMDD-HHMMSSZ.txt
- вспомогательные скрипты:  /opt/tgbots/utils/*.sh, *.py

ОСНОВНЫЕ СКРИПТЫ
- app_baseline.sh
  Обновляет baseline под ТЕКУЩИЙ app.py.
  Выводит app.baseline.json и снапшот-сводку в snapshots/.
  Используется, когда вы признали текущий app.py “эталоном” (после ручного отката/фикса).

- snapshot_app.sh
  Делает быстрый текстовый снимок app.py (размер, sha256, первые N строк, py_compile=OK/FAIL).
  Полезно перед любым риском.

- app_safe_apply.sh
  Швейцарский нож для безопасного применения патча:
   1) делает baseline-проверку (сверяет sha/size с app.baseline.json, если оно есть),
   2) сохраняет бэкап app.bak.TIMESTAMP.py,
   3) вызывает указанный патч-командный файл, отдавая путь временного TMP-файла,
   4) компилирует TMP (python -m py_compile),
   5) если всё ок — подменяет боевой app.py, рестартует сервис и снимает трейс журналов;
      если нет — откатывает на бэкап.
  Все артефакты складывает в snapshots/ и trace-*.txt.

- app_quick_apply.sh
  Облегчённый режим: быстро делает SNAPSHOT -> APPLY -> рестарт -> TRACE.
  Используется для мелких патчей, когда baseline уже актуален.
  При фатальных паттернах в журнале — откатывает.

- diag_collect.sh
  Собирает сводную диагностику (пути, sha, head, py_compile, env, sqlite pragma/tables,
  systemd status, журналные ошибки, права/пермишены) в /opt/tgbots/utils/diag/diag-*.txt

СТАНДАРТНЫЙ ЦИКЛ РАБОТЫ
1) Перед любыми правками — снимок:
   /opt/tgbots/utils/snapshot_app.sh

2) Признать текущее состояние эталоном (если нужно):
   /opt/tgbots/utils/app_baseline.sh
   → появится /opt/tgbots/utils/app.baseline.json и baseline-снимок

3) Применить патч безопасно:
   # Пример: патч-питон принимает TMP-путь
   /opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/patch_something.py

   Что произойдёт:
   - будет сделан бэкап app.bak.TIMESTAMP.py
   - патч отредактирует временный TMP-файл
   - проверка py_compile
   - установка нового app.py и рестарт сервиса
   - сбор трейса: /opt/tgbots/utils/trace-*.txt
   - при ошибках → автоматический откат на бэкап

4) Быстрые правки для повторяющихся операций:
   /opt/tgbots/utils/app_quick_apply.sh python3 /opt/tgbots/utils/patch_foo.py

ОТКАТЫ
- Быстрый ручной откат на последний бэкап:
  cp -a /opt/tgbots/bots/support/app.bak.*.py /opt/tgbots/bots/support/app.py --backup=t
  systemctl restart tgbot@support.service

- Если патч-скрипт вернул ошибку, app_safe_apply.sh сам откатит и сохранит TRACE-файл.

ПРОЧНОСТЬ/ГИГИЕНА
- Никогда не редактируйте app.py “влоб”. Только через снапшот/патч-скрипт:
  это обеспечивает бэкап, компиляцию и единый журнал.
- Если baseline “не совпал” (Mismatch), сначала сделайте app_baseline.sh, чтобы зафиксировать
  ваше текущее состояние как эталон, или откатитесь к тому состоянию, которое считаете эталонным.
- Включайте в патч-скрипты минимально инвазивные изменения, чёткие якоря (регэкспы на строки),
  и обязательно проверяйте наличие нужных импортов/маркерных строк.
- Всегда проверяйте журнал после рестарта (трейс сохраняется автосборщиком):
  tail -n 200 /opt/tgbots/utils/trace-*.txt
  или
  journalctl -u tgbot@support.service -n 300 --no-pager | egrep -i 'Traceback|Error|SNAPSHOT' || true

ТИПОВЫЕ ПРИЧИНЫ СБОЕВ
- Read-only FS / отсутствие прав на /opt/tgbots/utils/snapshots/ или /opt/tgbots/bots/support/
  → проверьте монтирование, chown/chmod на tgbot:tgbot.
- Mismatch baseline: вы отредактировали app.py вручную или baseline устарел
  → app_baseline.sh или откат на нужный бэкап.
- py_compile FAIL: синтаксическая ошибка в патче
  → исправьте патч, повторите.
- Сервис не подменился: unit использует другой WorkingDirectory/ExecStart
  → systemctl cat tgbot@support.service и убедитесь, что запускаете файл, который вы правили.

ПРИМЕРЫ
- Сделать baseline:
  /opt/tgbots/utils/app_baseline.sh

- Применить патч с автосейвом трейса:
  /opt/tgbots/utils/app_safe_apply.sh python3 /opt/tgbots/utils/patch_newcomer_step1_log_safe.py

- Быстро применить минимальный патч:
  /opt/tgbots/utils/app_quick_apply.sh python3 /opt/tgbots/utils/patch_fix_newcomer_step1.py

- Собрать диагностику:
  /opt/tgbots/utils/diag_collect.sh

===============================================================================
```

### SQLITE_STORAGE.txt

```text
=== SQLite / Хранилище состояния =================================================

1) Где лежит БД и что там хранится
- Путь задаётся ENV-переменной SQLITE_PATH (для инстанса "support" обычно):
  /opt/tgbots/bots/support/join_guard_state.db
- Таблицы (типовой набор):
  • pending_requests  — входящие запросы на вступление, TTL, кто ожидал проверку
  • approvals         — факты одобрений/отклонений (аудит)
  • newcomer_seen     — фиксация "новичка": когда замечен, когда окно истекает
- Вспомогательные состояния вне SQLite (файловые):
  • /var/lib/tgbots/testwatch/testuser.status — простой key=value для сайдкара наблюдателя тест-юзера (не БД).

2) Права и владельцы
- Рекомендуется: владелец и группа tgbot, права 664 (файл), директории — 775:
  chown tgbot:tgbot /opt/tgbots/bots/support/join_guard_state.db
  chmod 664 /opt/tgbots/bots/support/join_guard_state.db
- Директория должна быть доступна на запись пользователю сервиса (обычно tgbot).

3) Проверка состояния и быстрая диагностика
- Мини-проверка (pragma + список таблиц):
  sqlite3 "$SQLITE_PATH" "PRAGMA journal_mode; PRAGMA busy_timeout; PRAGMA integrity_check; .tables;"
- Расширенная диагностика (журнал, env, head app.py, таблицы):
  /opt/tgbots/utils/diag_collect.sh

4) Типовая схема (DDL-подсказка, если таблиц не хватает)
- Создать newcomer_seen, если отсутствует:
  sqlite3 "$SQLITE_PATH" <<'SQL'
  CREATE TABLE IF NOT EXISTS newcomer_seen (
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    first_seen  INTEGER NOT NULL,   -- unix time (UTC)
    window_sec  INTEGER NOT NULL,   -- окно "новичка" в секундах
    PRIMARY KEY (chat_id, user_id)
  );
  CREATE INDEX IF NOT EXISTS idx_newcomer_seen_expire
    ON newcomer_seen (first_seen, window_sec);
  SQL
- pending_requests (примерная структура, может отличаться от вашей реальной):
  CREATE TABLE IF NOT EXISTS pending_requests (
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    requested   INTEGER NOT NULL,
    ttl_sec     INTEGER NOT NULL,
    PRIMARY KEY (chat_id, user_id)
  );
  CREATE INDEX IF NOT EXISTS idx_pending_expire
    ON pending_requests (requested, ttl_sec);
- approvals (аудит):
  CREATE TABLE IF NOT EXISTS approvals (
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    action      TEXT    NOT NULL,   -- approved / rejected / expired
    ts          INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_approvals_ts
    ON approvals (ts);

5) Режим журналирования и конкуренция
- Рекомендуется WAL (write-ahead logging) для одновременного чтения/записи:
  sqlite3 "$SQLITE_PATH" "PRAGMA journal_mode=WAL;"
- Таймаут на блокировки:
  sqlite3 "$SQLITE_PATH" "PRAGMA busy_timeout=3000;"   -- 3 сек
- В коде бота тоже устанавливайте busy_timeout (если библиотека позволяет).
- Важно: избегать одновременных записей в одну и ту же таблицу из разных процессов,
  если у вас нет дисциплины транзакций. Один процесс-автор — безопаснее.

6) Полезные запросы и операции
- Кто сейчас в pending:
  sqlite3 "$SQLITE_PATH" "SELECT chat_id,user_id,requested,ttl_sec FROM pending_requests ORDER BY requested DESC LIMIT 20;"
- Последние approvals:
  sqlite3 "$SQLITE_PATH" "SELECT chat_id,user_id,action,ts FROM approvals ORDER BY ts DESC LIMIT 20;"
- Список новичков, у кого не истекло окно:
  sqlite3 "$SQLITE_PATH" "
    SELECT chat_id,user_id,first_seen,window_sec
    FROM newcomer_seen
    WHERE (strftime('%s','now') - first_seen) < window_sec
    ORDER BY first_seen DESC LIMIT 50;"
- Очистка протухших записей (пример — newcomer_seen):
  sqlite3 "$SQLITE_PATH" "
    DELETE FROM newcomer_seen
    WHERE (strftime('%s','now') - first_seen) >= window_sec;"
- VACUUM (только когда сервис не пишет!):
  systemctl stop tgbot@support.service
  sqlite3 "$SQLITE_PATH" "VACUUM; ANALYZE;"
  systemctl start tgbot@support.service

7) Бэкап и восстановление
- Горячий бэкап (через .backup в sqlite3, можно при работающем сервисе):
  sqlite3 "$SQLITE_PATH" ".backup /opt/tgbots/bots/support/join_guard_state.db.bak.$(date -u +%Y%m%d-%H%M%SZ)"
- Восстановить:
  systemctl stop tgbot@support.service
  cp -a /opt/tgbots/bots/support/join_guard_state.db.bak.YYYYMMDD-HHMMSSZ \
        /opt/tgbots/bots/support/join_guard_state.db
  chown tgbot:tgbot /opt/tgbots/bots/support/join_guard_state.db
  chmod 664 /opt/tgbots/bots/support/join_guard_state.db
  systemctl start tgbot@support.service

8) Частые ошибки и их разруливание
- "database is locked":
  • увеличьте busy_timeout
  • проверьте, нет ли параллельного писателя (второй процесс/скрипт)
  • на время тяжёлых операций останавливайте сервис (или делайте их транзакционно)
- "no such table: newcomer_seen":
  • примените DDL из п.4
  • проверьте, что приложение читает тот же SQLITE_PATH, что и вы
- "readonly database":
  • права/владение файла и директории
  • монтирование тома в RO-режиме (убедитесь, что /opt RW)
- Шифрование/сжатие:
  • Не используется штатно. Если понадобится — оценивайте совместимость с SQLite и python-водителем.

9) Связь с ENV и сервисом
- Путь контролируется ENV SQLITE_PATH в /etc/tgbots/support.env
- После правок ENV → перезапуск systemd:
  sudo systemctl restart tgbot@support.service
- Проверить, что приложение стартовало и увидело БД:
  journalctl -u tgbot@support.service -n 200 --no-pager | egrep -i 'SQLITE_PATH|SNAPSHOT|Traceback|Error' || true

10) Практика изменений (best practice)
- Любые миграции (DDL) — отдельным шагом, с бэкапом:
  • .backup → применить DDL → smoke-test → журнал
- Индексы — только под реальные запросы. Избыточные индексы ≈ лишние записи/IO.
- Даты в Unix time (UTC). Не хранить локальные строки времени.
- Транзакции на пачки изменений (BEGIN/COMMIT), не писать по одной строке/коммиту в цикле.

===============================================================================
```

### ENV_CONFIG.txt

```text
=== Конфигурация через ENV (.env) ============================================

1) Назначение
- Все параметры бота задаются через файл окружения, без правок кода.
- Для инстанса "support" используется: /etc/tgbots/support.env

2) Где используется
- systemd unit читает EnvironmentFile=/etc/tgbots/%i.env
- Скрипты утилит также подгружают этот файл.

3) Быстрый просмотр безопасных переменных
/opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env
# (скрипт скрывает секреты, показывает ключевые флаги и пути)

4) Ключевые переменные (без секретов)
- TEST_CHAT_ID              : ID тестового чата (например: -1002099408662)
- TEST_USER_ID              : ID тестового пользователя для экспериментов
- TRACE_TEST_CHAT           : "1/true/yes/on" — расширенный логинг для тест-чата
- NEWCOMER_WINDOW_SECONDS   : окно "новичка" в секундах (по умолчанию 86400)
- NEWCOMER_TEST_ONLY        : "1/true/yes/on" — ограничить функционал новичка только на TEST_* (для безопасного теста)
- SQLITE_PATH               : путь к SQLite (обычно /opt/tgbots/bots/support/join_guard_state.db)
- UTILS_DIR                 : директория утилит (обычно /opt/tgbots/utils)
- TARGET_CHAT_ID(S)         : целевой чат/чаты для обработки запросов на вступление (через запятую)
- ADMIN_IDS                 : список админов (через запятую) для служебных уведомлений
- DELETE_SYSTEM_MESSAGES    : "1/true/yes/on" — удалять системные сообщения
- LOCKDOWN_NONADMIN_BOTS    : "1/true/yes/on" — ограничивать ботов без прав
- AGGRESSIVE_CHANNEL_ANTILINK : "1/true/yes/on" — агрессивный анти-линк каналов

5) Секреты
- BOT_TOKEN                 : токен Telegram-бота (секрет!)
- VERIFY_SECRET             : внутренний секрет (если используется)
Эти переменные не выводим в логи. Не коммитим в репозиторий.

6) Пример минимального /etc/tgbots/support.env
# === обязательные ===
BOT_TOKEN=123456:ABC...        # не печатать в логах
SQLITE_PATH=/opt/tgbots/bots/support/join_guard_state.db
UTILS_DIR=/opt/tgbots/utils

# === тестовый стенд ===
TEST_CHAT_ID=-1002099408662
TEST_USER_ID=6700029291
TRACE_TEST_CHAT=1
NEWCOMER_WINDOW_SECONDS=86400
NEWCOMER_TEST_ONLY=1

# === поведение ===
DELETE_SYSTEM_MESSAGES=true
LOCKDOWN_NONADMIN_BOTS=true
AGGRESSIVE_CHANNEL_ANTILINK=true

# === таргет-чаты / админы ===
TARGET_CHAT_IDS=-1002099408662,-1001878435829
ADMIN_IDS=11111111,22222222

7) Валидация ENV
- Снимок ключевых переменных:
  /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env
- Проверка читаемости файла:
  test -r /etc/tgbots/support.env && echo OK || echo FAIL
- Проверка json/строк в списках:
  # список через запятую без пробелов (или обрабатывайте пробелы осознанно)

8) Типовые ошибки
- Пробелы и неэкранированные спецсимволы справа от "="
- Неверный ID (строка вместо числа) → приводите к int
- Пустые TARGET_CHAT_IDS → бот принимает запросы от всех чатов
- Выставили NEWCOMER_TEST_ONLY=1, но забыли TEST_* → функционал не сработает

9) Процедура изменения
1) Отредактировать /etc/tgbots/support.env (sudo nano/vi)
2) Быстро проверить:
   /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env
3) Перезапустить сервис:
   sudo systemctl restart tgbot@support.service
4) Проверить журнал:
   journalctl -u tgbot@support.service -n 200 --no-pager

10) Диагностика
- Сбор расширенной диагностики:
  /opt/tgbots/utils/diag_collect.sh
- Проверка членства тест-пары:
  /opt/tgbots/utils/probe_membership.sh /etc/tgbots/support.env
- Проверка DM связи:
  /opt/tgbots/utils/probe_dm.sh

===============================================================================
```

### SYSTEMD_SERVICE.txt

```text
=== Сервисный запуск (systemd) ================================================

1) Назначение
- Управление инстансом бота через systemd: старт/стоп/рестарт, логи, автозапуск.

2) Ключевые пути
- Unit-шаблон:          /etc/systemd/system/tgbot@.service
- Инстанс:              tgbot@support.service
- Раб. директория:      /opt/tgbots/bots/support
- Главный файл:         /opt/tgbots/bots/support/app.py
- Вирт. окружение:      /opt/tgbots/.venv
- ENV-файл:             /etc/tgbots/support.env
- База SQLite:          /opt/tgbots/bots/support/join_guard_state.db
- Утилиты:              /opt/tgbots/utils/

3) Текущий ExecStart (прямой запуск без обёрток)
ExecStart=/opt/tgbots/.venv/bin/python /opt/tgbots/bots/support/app.py --instance support

Проверка фактического ExecStart:
systemctl show -p ExecStart --value tgbot@support.service

4) Полезные опции сервиса
- Restart=always, RestartSec=3 — авто-рестарт.
- WorkingDirectory=/opt/tgbots/bots/%i
- EnvironmentFile=/etc/tgbots/%i.env
- ReadWritePaths=/opt/tgbots/bots/%i
- Безопасность: NoNewPrivileges, PrivateTmp, ProtectSystem=strict, ProtectHome=true,
  RestrictSUIDSGID, SystemCallFilter=@system-service.
- Ограничения: MemoryMax=256M, CPUQuota=30%, LimitNOFILE=16000.

5) Управление
- Включить автозапуск:     sudo systemctl enable tgbot@support.service
- Старт/стоп/рестарт:      sudo systemctl start|stop|restart tgbot@support.service
- Статус:                  systemctl status tgbot@support.service --no-pager
- Логи (последние N):      journalctl -u tgbot@support.service -n 200 --no-pager
- Логи текущей загрузки:   journalctl -u tgbot@support.service -b --no-pager
- Перечитать unit’ы:       sudo systemctl daemon-reload

6) Где править
- Основной шаблон: /etc/systemd/system/tgbot@.service
- Пер-инстансные оверрайды: /etc/systemd/system/tgbot@support.service.d/override.conf
  (после правок → daemon-reload → restart)

7) Быстрая диагностика
journalctl -u tgbot@support.service -b -n 200 --no-pager \
 | egrep -i "Traceback|SyntaxError|IndentationError|NameError|aiogram|database is locked" || true

8) Чек-лист перед релизом
(a) Компиляция:
    /opt/tgbots/.venv/bin/python -m py_compile /opt/tgbots/bots/support/app.py
(b) ENV корректен (без секретов в логах):
    /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env
(c) Зависимости:
    /opt/tgbots/.venv/bin/pip show aiogram
(d) Целостность БД:
    sqlite3 /opt/tgbots/bots/support/join_guard_state.db "PRAGMA integrity_check;"
(e) Рестарт + просмотр журнала без ошибок.

9) Референс минимального unit-шаблона
[Unit]
Description=Telegram bot instance %i
After=network-online.target
Wants=network-online.target

[Service]
User=tgbot
Group=tgbot
WorkingDirectory=/opt/tgbots/bots/%i
EnvironmentFile=/etc/tgbots/%i.env
Environment=SQLITE_PATH=/opt/tgbots/bots/%i/join_guard_state.db
ExecStart=/opt/tgbots/.venv/bin/python /opt/tgbots/bots/%i/app.py --instance %i
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/tgbots/bots/%i
RestrictSUIDSGID=true
CapabilityBoundingSet=
SystemCallFilter=@system-service
AmbientCapabilities=
LimitNOFILE=16000
MemoryMax=256M
CPUQuota=30%

[Install]
WantedBy=multi-user.target

10) Полезные команды для сверки
- Полный unit с оверрайдами: systemctl cat tgbot@support.service
- Итоговый ExecStart:         systemctl show -p ExecStart --value tgbot@support.service

===============================================================================
```

### SNAPSHOT_SYSTEM_README.txt

```text
SNAPSHOT / SAFE-PATCH СИСТЕМА — КРАТКИЙ ГАЙД
============================================

Цель
----
- Делать правки в `app.py` только через безопасные скрипты.
- Иметь быстрый откат и воспроизводимые снапшоты.
- Получать автоматическую диагностику при неудачных применениях.

Ключевые пути
-------------
- Боевое приложение:
  /opt/tgbots/bots/support/app.py
- Юнит systemd:
  tgbot@support.service
- Переменные окружения (бот):
  /etc/tgbots/support.env
- Утилиты и патчи:
  /opt/tgbots/utils/
- Снапшоты:
  /opt/tgbots/utils/snapshots/
- Бэкапы app.py (авто-перед правкой):
  /opt/tgbots/bots/support/app.bak.YYYYmmdd-HHMMSSZ.py
- Диагностика:
  /opt/tgbots/utils/diag/
  и /opt/tgbots/utils/trace-*.txt

Главные скрипты
---------------
1) Снимок текущего app.py (хэш, head, компиляция)
   /opt/tgbots/utils/snapshot_app.sh /opt/tgbots/bots/support/app.py
   → snapshots/app.YYYYmmdd-HHMMSSZ.txt

2) Обновить baseline под текущее состояние
   /opt/tgbots/utils/app_baseline.sh
   → /opt/tgbots/utils/app.baseline.json
     /opt/tgbots/utils/app.baseline.YYYYmmdd-HHMMSSZ.txt

3) Безопасное применение патча (с бэкапом, компиляцией, рестартом, авто-диагностикой)
   /opt/tgbots/utils/app_quick_apply.sh  python3 /opt/tgbots/utils/<patch_script>.py
   Внутри:
     - Создаётся снапшот и TMP-копия
     - Патч правит TMP
     - py_compile проверка
     - Если ОК → установка как app.py + restart
       Иначе → автооткат на свежий бэкап и trace-* лог

4) Быстрый ручной откат к последнему бэкапу
   cp -v /opt/tgbots/bots/support/app.bak.*.py  /opt/tgbots/bots/support/app.py --backup=t
   systemctl restart tgbot@support.service
   (или вспомогательный /opt/tgbots/utils/rollback_last_backup.sh, если есть)

5) Сбор расширенной диагностики
   /opt/tgbots/utils/diag_collect.sh
   → diag/diag-YYYYmmdd-HHMMSSZ.txt

Рабочий процесс (рекомендуемый)
-------------------------------
1. Зафиксировать состояние:
   - snapshot_app.sh
   - app_baseline.sh (если текущее — новый эталон)

2. Применить небольшую атомарную правку:
   - app_quick_apply.sh python3 .../patch_xxx.py
   - Проверить журнал:
     journalctl -u tgbot@support.service -n 120 --no-pager

3. Если рестарт неудачный:
   - Смотреть TRACE_SAVED: /opt/tgbots/utils/trace-*.txt
   - Автооткат уже сделан; при нужде откатить вручную (см. выше)

4. После подтверждения успеха:
   - Обновить baseline: app_baseline.sh
   - Сохранить финальный снапшот: snapshot_app.sh

Правила и запреты
-----------------
- Не править app.py в проде напрямую — только через app_quick_apply.sh + патч.
- Патчи должны быть минимальными и обратимыми.
- После успешного апдейта обновлять baseline (app_baseline.sh).
- Убедиться, что /opt доступен на запись (иначе всё ляжет).
- Изменения окружения — в /etc/tgbots/support.env.
  Быстрая проверка: /opt/tgbots/utils/echo_env.sh /etc/tgbots/support.env

Подсказки по поиску ошибок
--------------------------
- Компиляция Python:
  python3 -m py_compile /opt/tgbots/bots/support/app.py
- Журналы сервиса:
  journalctl -u tgbot@support.service -n 200 --no-pager | egrep -i "Traceback|SyntaxError|IndentationError|NameError|database is locked"
- Полная диагностика:
  /opt/tgbots/utils/diag_collect.sh

Чек-лист перед релизом
----------------------
- [ ] /opt доступен на запись
- [ ] Снимок сделан (snapshot_app.sh)
- [ ] Патч применён через app_quick_apply.sh
- [ ] Журналы чистые, бот отвечает
- [ ] Обновлён baseline (app_baseline.sh)
- [ ] Финальный снапшот и diag-лог сохранены

История изменений (где искать)
------------------------------
- Снапшоты: /opt/tgbots/utils/snapshots/
- Бэкапы:   /opt/tgbots/bots/support/app.bak.*.py
- Трейсы:   /opt/tgbots/utils/trace-*.txt
- Диагностика: /opt/tgbots/utils/diag/diag-*.txt
```