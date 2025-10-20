# Support Bot (Telegram) — код, автодеплой и Git‑операции

Этот репозиторий хранит **рабочий код бота** (`app.py`). Пуш в серверный bare‑репозиторий запускает **автодеплой**: снапшот → бэкап → `py_compile` → установка нового `app.py` → `systemctl restart tgbot@support.service` → сбор журнала и автодоков в ветку `state` (создаются **на сервере**).

- Боевой код: `/opt/tgbots/bots/support/app.py`
- Сервис: `tgbot@support.service`
- ENV: `/etc/tgbots/support.env` (секреты **не коммитим**)
- Venv: `/opt/tgbots/.venv`
- БД (SQLite, WAL): `/opt/tgbots/bots/support/join_guard_state.db`
- Bare‑repo (куда пушим): `/opt/tgbots/git/support.git`
- Worktree хуков: `/opt/tgbots/repos/support`
- Утилиты/скрипты: `/opt/tgbots/utils/`
- Безопасный применитель из хука: `/opt/tgbots/utils/patch_apply_from_repo.sh`

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

## 2) Windows: SSH‑ключи и «правильный» SSH для Git

### 2.1 Создать ключ (PowerShell)
```powershell
ssh-keygen --% -t ed25519 -C "ivan@support-bot" -f "$env:USERPROFILE\.ssh\id_ed25519" -N ""
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

### 2.2 Добавить публичный ключ на сервер
```powershell
ssh root@82.146.35.169 "mkdir -p ~/.ssh && chmod 700 ~/.ssh"
scp "$env:USERPROFILE\.ssh\id_ed25519.pub" root@82.146.35.169:/root/.ssh/id_ed25519.pub
ssh root@82.146.35.169 "cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && rm ~/.ssh/id_ed25519.pub"
ssh root@82.146.35.169 "echo OK"   # должно вывести OK без пароля
```

### 2.3 Заставить Git использовать системный OpenSSH (обход проблем с путями)
```powershell
# разово на сессию
$env:GIT_SSH = 'C:/Windows/System32/OpenSSH/ssh.exe'
# или навсегда для текущего пользователя
[Environment]::SetEnvironmentVariable('GIT_SSH','C:/Windows/System32/OpenSSH/ssh.exe','User')
```

### 2.4 CRLF/LF: единые правила в репо
В корне репозитория держим `.gitattributes`:
```
*           text=auto
*.py        text eol=lf
*.sh        text eol=lf
*.service   text eol=lf
*.unit      text eol=lf
*.timer     text eol=lf
*.md        text eol=lf
*.txt       text eol=lf
*.conf      text eol=lf
*.env       text eol=lf
*.sql       text eol=lf
*.png *.jpg *.jpeg *.gif *.pdf *.db *.sqlite* binary
```
Рекомендуемая глобальная настройка Windows:
```powershell
git config --global core.autocrlf true
git add --renormalize .
git commit -m "normalize line endings"
```

---

## 3) Что деплоится и как работает хук

- Серверный хук `post-receive` делает `checkout` ветки `main` в `/opt/tgbots/repos/support` и вызывает **безопасный применитель**:
  ```bash
  /opt/tgbots/utils/patch_apply_from_repo.sh /opt/tgbots/repos/support/app.py
  ```
- Применитель:
  1) делает бэкап текущего `/opt/tgbots/bots/support/app.py`;
  2) прогоняет `py_compile` на новой версии;
  3) ставит файл на место;
  4) перезапускает `tgbot@support.service`;
  5) пишет хвост `journalctl` в `/opt/tgbots/utils/diag_logs/`;
  6) при ошибке — откатывает на бэкап.

- После успешного деплоя скрипт **генерирует автодокументацию** в `docs_state/*` и коммитит её в ветку `state` (обновляет ref в bare‑репозитории).

Посмотреть автодоки локально:
```bash
git fetch origin state:state
git checkout state
ls -l docs_state/
```

---

## 4) Структура проекта в репозитории

Минимум:
```
app.py
README.md
.gitignore
.gitattributes
```
В этом варианте деплоится только `app.py`. Если потребуется деплоить ещё файлы/папки (модули, ресурсы), расширим логику применителя и/или хука — через PR.

`.gitignore` (короткая версия):
```
__pycache__/
*.pyc
*.log
*.db
*.sqlite*
/docs_state/
/snapshots/
/diag_logs/
/.venv/ /venv/ /env/
/dist/ /build/
/.idea/ /.vscode/
*.bak.* *.swp *.swo *.tmp *.trace
*.env
```

---

## 5) Окружение, сервис, БД, диагностика (шпаргалка)

Окружение (секреты):
```
/etc/tgbots/support.env      # не коммитим
```
Сервис/логи:
```bash
systemctl status tgbot@support.service --no-pager
journalctl -u tgbot@support.service -n 300 --no-pager
```
SQLite (WAL):
```bash
sqlite3 "$SQLITE_PATH" "PRAGMA journal_mode; PRAGMA integrity_check; .tables;"
sqlite3 "$SQLITE_PATH" ".backup /opt/tgbots/bots/support/join_guard_state.db.bak.$(date -u +%Y%m%d-%H%M%SZ)"
```
Диагностика:
```bash
/opt/tgbots/utils/diag_collect.sh && tail -n 100 /opt/tgbots/utils/diag/diag-*.txt
```

---

## 6) Ветки и политика коммитов

- `main` — единственный источник деплоя на сервере.
- `state` — «серверная» ветка с автодоками. Её **не редактируем вручную** — только читаем.
- Коммиты должны быть атомарные и воспроизводимые; для правок кода используем PR или коммиты из локальной ветки с merge/rebase в `main`.

---

## 7) (Опционально) Не root‑пользователь для пушей

Рекомендуется завести `gitdeploy`:
```bash
sudo adduser --system --group --home /opt/tgbots/gitdeploy --shell /bin/bash gitdeploy
sudo chown -R gitdeploy:gitdeploy /opt/tgbots/git /opt/tgbots/repos
```
Дать право перезапуска сервиса:
```bash
sudo bash -c 'cat > /etc/sudoers.d/gitdeploy-tgbot <<EOF
gitdeploy ALL=NOPASSWD: /bin/systemctl restart tgbot@support.service, /bin/systemctl status tgbot@support.service, /bin/journalctl -u tgbot@support.service -n *
EOF'
sudo visudo -c
```
Правка хука (если требуется `sudo`):
```bash
sudo sed -i 's|systemctl |sudo systemctl |g; s|journalctl |sudo journalctl |g' /opt/tgbots/git/support.git/hooks/post-receive
```
URL для пушей станет:
```
ssh://gitdeploy@82.146.35.169/opt/tgbots/git/support.git
```

---

## 8) Зеркало на GitHub (опционально)

Добавить второй remote и пушить «в обе стороны» (сервер для деплоя, GitHub — для хранения кода):
```bash
git remote add github https://github.com/<user>/support-bot.git
git push -u github main
# затем обычно
git push origin main && git push github main
```

---

## 9) Частые проблемы и решения

- **`Permission denied (publickey)` при push** — сервер не видит твой публичный ключ. Проверь `~/.ssh/authorized_keys` на сервере и права `700/600`.
- **Git на Windows просит пароль/не видит ключ** — задай `GIT_SSH='C:/Windows/System32/OpenSSH/ssh.exe'` и убери кривые `core.sshCommand`.
- **Предупреждения про CRLF/LF** — добавь `.gitattributes` (см. выше) и сделай `git add --renormalize .`.
- **В логах SNAPSHOT MISMATCH / отказ старта** — обнови baseline, если текущее состояние верное, или откати `app.py` на бэкап, потом перезапуск сервиса.
- **`database is locked`** — увеличь busy_timeout, убери конкурирующие записи, для миграций останавливай сервис.

---

## 10) Безопасность и запреты

- Не коммитим секреты (`/etc/tgbots/support.env`, токены).
- Не редактируем `app.py` на сервере «горячо» — только через пуш/применитель или безопасные скрипты из `/opt/tgbots/utils/`.
- Перед чистками и обновлениями — свежий снапшот и наличие нескольких бэкапов.
