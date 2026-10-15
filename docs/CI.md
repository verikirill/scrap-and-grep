# CI/CD

Каждая проверка записана один раз, скриптом в `ci/`. Эти скрипты вызывают GitLab (`.gitlab-ci.yml`) и GitHub Actions (`.github/workflows/ci.yml`) в одних и тех же образах, и их же можно запустить на своей машине. GitLab вдобавок собирает образы стенда, кладёт их в реестр проекта и выкатывает стенд из `main`. GitHub Actions собирает те же образы без публикации.

Прогон GitHub Actions всего кода 15 октября 2026 года прошёл целиком: 932 теста бэкенда с покрытием строк 86%, 819 тестов фронтенда с покрытием строк 98%, 20 тестов сервиса рендера, сборка образов `backend`, `web`, `browser`, `shorts` и `egress`.

## Что проверяется

Задания называются одинаково в обеих системах.

| Задание | Скрипт | Что делает | Когда |
|---|---|---|---|
| `backend:lint` | `backend-lint.sh` | `ruff check`, `ruff format --check`, `mypy --strict` | всегда |
| `backend:test` | `backend-test.sh` | весь `pytest` на PostgreSQL с pgvector, Valkey и ClickHouse тех же версий, что в `docker-compose.yml`; JUnit и покрытие в Cobertura | всегда |
| `frontend:lint` | `frontend-lint.sh` | `oxlint`, `oxfmt --check`, `tsc -b` | всегда |
| `frontend:test` | `frontend-test.sh` | `vitest` с покрытием по всем файлам `src`, настройки покрытия в `vite.config.ts` | всегда |
| `frontend:build` | `frontend-build.sh` | `vite build`, сборка хранится в артефактах неделю | всегда |
| `shorts:test` | `shorts-test.sh` | `tsc` и `node --test` сервиса рендера | всегда |
| `browser:test` | `browser-test.sh` | `ruff`, `mypy` и `pytest` браузера стека: он ходит только на публичные адреса, в том числе после редиректов и через прокси | всегда |
| `python:services` | `python-services.sh` | `ruff` для `tts` и `docparser`, lock-файлы совпадают с `pyproject.toml` | всегда |
| `compose:config` | `compose-config.sh` | `docker compose config` для каждого override из документации, все профили включены | всегда |
| `dockerfiles:lint` | `dockerfiles-lint.sh` | hadolint по всем Dockerfile, исключения в `.hadolint.yaml` | всегда |
| `shell:lint` | `shell-lint.sh` | shellcheck по всем `*.sh` | всегда |
| `secrets:scan` | `secrets-scan.sh` | gitleaks: в merge request и pull request коммиты ветки, в остальных прогонах вся история; известные тестовые значения в `.gitleaksignore` | всегда |
| `deps:audit` | `deps-audit.sh` | osv-scanner по lock-файлам; находка даёт предупреждение и не останавливает остальное | всегда |
| `commits:lint` | `commits-lint.sh` | сообщения коммитов в виде `тип(область): что изменилось` | merge request, pull request |
| `images` | `images.sh` | сборка образов `backend`, `web`, `browser`, `shorts`, `egress`; в GitLab на `main` и в тегах push в реестр | после проверок; в merge request и pull request, когда меняется то, что попадает в образы |
| `deploy:stand` | `deploy-stand.sh` | выкатка стенда | GitLab, `main`, когда стенд настроен |
| `verify:stand` | `verify-stand.sh` | путь жюри на стенде, `scripts/smoke.py` | GitLab, после выкатки |

Бэкенд проверяется на настоящих сервисах. Адреса тесты берут из `RADAR_TEST_ADMIN_DSN`, `RADAR_TEST_CACHE_URL`, `RADAR_TEST_BROKER_URL` и `RADAR_TEST_CLICKHOUSE_URL`, без них идут на `127.0.0.1`. На ноутбуке без Docker интеграционные тесты пропускаются сами. `backend-test.sh` такой пропуск считает ошибкой: если сервис не ответил, задание красное.

GitLab показывает результаты тестов во вкладке «Tests» (тесты) пайплайна и в виджете merge request, покрытие строк бэкенда и фронтенда подсвечивает в диффе. Замечания ruff, oxlint и hadolint попадают в виджет «Code Quality» (качество кода): для него GitLab передаёт скриптам путь отчёта в `CODE_QUALITY_REPORT`. GitHub Actions выкладывает те же JUnit и Cobertura в артефакты на 14 дней и пишет в сводку задания таблицу: сколько тестов, сколько упало и пропущено, покрытие строк.

Уязвимости в зависимостях появляются и без коммитов. Ночной прогон проверок по `main` заводится в GitLab на странице «Build» → «Pipeline schedules» → «New schedule» (сборка, расписания пайплайнов, новое расписание), это доступно и роли Developer. По расписанию идут все проверки, без образов и стенда.

## Как запустить у себя

Скрипты запускаются из любой папки и сами переходят в корень репозитория:

```bash
sh ci/backend-lint.sh
sh ci/frontend-test.sh
COMMIT_RANGE=origin/main..HEAD sh ci/commits-lint.sh
```

Для них нужны те же инструменты, что для разработки: uv, Node.js 24, Docker; для `secrets-scan.sh`, `deps-audit.sh`, `dockerfiles-lint.sh` и `shell-lint.sh` ещё gitleaks, osv-scanner, hadolint и shellcheck. Тестам бэкенда нужны сервисы на `127.0.0.1`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres valkey clickhouse
sh ci/backend-test.sh
```

Задания GitLab целиком, в тех же образах и с теми же сервисами, запускает [gitlab-ci-local](https://github.com/firecow/gitlab-ci-local):

```bash
npx gitlab-ci-local --variable PIPELINES=on backend:test frontend:test
```

Ему нужен `rsync`, а в Git Bash его нет, поэтому на Windows gitlab-ci-local запускают в Linux-контейнере с сокетом Docker. Файлы проекта он копирует в тома Docker, так что пути Windows ему не мешают.

Отдельные задания workflow GitHub Actions запускает [act](https://github.com/nektos/act):

```bash
act pull_request -e event.json -j commits-lint -P ubuntu-latest=node:24.21.0-alpine
```

`event.json` задаёт `pull_request.base.sha` и `pull_request.head.sha`, из них `commits-lint` и `secrets-scan` берут диапазон коммитов. Шаги `actions/cache` и `actions/upload-artifact` act выполняет по-своему: Node.js берёт из образа задания, артефакты принимает своим сервером. Задания без этих шагов (`commits-lint`, `shell-lint`, `dockerfiles-lint`, `deps-audit`) проходят под act так же, как на GitHub, остальные удобнее проверять самими скриптами или через gitlab-ci-local.

## Образы и стенд

`images` на `main` и в тегах публикует образы в реестр проекта с двумя тегами: короткий хеш коммита и `main` или имя тега. Имена образов `docker-compose.yml` берёт из `RADAR_IMAGE_PREFIX` и `RADAR_IMAGE_TAG`; без них остаются локальные `radar-<имя>:local`.

`deploy:stand` и `verify:stand` появляются в пайплайнах `main`, когда заданы `STAND_URL` и `STAND_DEPLOY`. Выкатка берёт из коммита `docker-compose.yml`, `clickhouse/` и `data/samples/`, тянет из реестра образы этого коммита и поднимает стек `docker compose up --wait`: compose ждёт миграции и здоровые healthcheck. `.env` стенда со всеми секретами остаётся на сервере. Скрипт меняет в нём только `RADAR_IMAGE_PREFIX`, `RADAR_IMAGE_TAG` и `COMPOSE_PROFILES`, поэтому `docker compose ps` или `logs` на сервере потом работают с тем же стеком.

| Переменная | Значение |
|---|---|
| `STAND_URL` | адрес стенда, например `http://stand.example.org:8080`; по нему `verify:stand` проходит путь жюри |
| `STAND_DEPLOY` | `ssh` или `local` |
| `STAND_DIR` | каталог стека на сервере, по умолчанию `/opt/scrapgrep` |
| `STAND_PROFILES` | профили сверх ядра через запятую, например `video`; сервисы профиля, убранного из списка, скрипт останавливает; стенд работает без `voice` и `docling` |
| `STAND_SSH_HOST`, `STAND_SSH_USER`, `STAND_SSH_PORT` | для `ssh`; порт по умолчанию 22 |
| `STAND_SSH_KEY` | для `ssh`: закрытый ключ, тип File, Protected |
| `STAND_SSH_KNOWN_HOSTS` | для `ssh`: вывод `ssh-keyscan -p <порт> <хост>`, тип File |

Переменные проекта задаёт Maintainer на той же странице «Variables». `STAND_SSH_KEY` отмечают «Protected» (защищённая): ключ попадает только в пайплайны защищённых веток, то есть в `main`. Тип File кладёт в переменную путь к файлу, а не сам ключ, а в конце ключа нужна пустая строка, иначе ssh ответит `error in libcrypto`.

На сервере нужен Docker с плагином Compose (выкатка проверена на Compose 2.36.2 и 5.6.0), пользователь из `STAND_SSH_USER` в группе `docker` и его открытый ключ в `~/.ssh/authorized_keys`. Пароль от реестра серверу не нужен: выкатка входит в реестр токеном задания и выходит после `pull`.

В режиме `local` задания выкатки идут на самой машине стенда, им доступны сокет Docker и каталог стека по тому же пути, например `/opt/scrapgrep`. Секретов этому режиму не нужно, поэтому `STAND_DEPLOY: local` и `STAND_URL` можно вписать прямо в `variables:` в `.gitlab-ci.yml`.

Откат делается кнопкой «Rollback» (откатить) на странице «Operate» → «Environments» → `stand`. GitLab перезапускает старое задание выкатки, и оно поднимает образы своего коммита: в реестре они лежат под коротким хешем.
