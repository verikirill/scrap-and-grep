# Презентация

[scrapgrep.pdf](scrapgrep.pdf) - 24 слайда 1920×1080 по критериям жюри: задача заказчика и ответ на неё; сравнение с аналитиком ИБ на одной неделе; репрезентативность материалов (каталог из 104 источников, прогон по датасету организаторов); техническая реализация (стек и граф сборки, лестница чтения защищённых сайтов, сверка записей и совет до выхода исправления, две аудитории, правка профиля и блоки выпуска, модели Yandex AI Studio, тот же выпуск на пяти моделях, закрытый контур, тесты и CI); персонализация (резюме и лента, рекомендательная модель, подстройка профиля, вход одной кнопкой, знакомство и перевод в читалке); бизнес (расписание, Telegram и MCP, ролики и брифинг голосом SpeechKit, аналитика, экономика); пилот.

Исходник - [slides.html](slides.html): обычная страница, шрифты Roboto Flex и Source Serif 4 (OFL) лежат в `fonts/`. Графики рисует скрипт внизу страницы из чисел, записанных в нём же. Каждая цифра на слайдах взята из документов репозитория, источник подписан на слайде: экономика из [BUSINESS](../BUSINESS.md), сбор из [DECISIONS](../DECISIONS.md), модели из [examples/models](../../examples/models/README.md) и [INSTALL](../INSTALL.md#модели-яндекса), тесты из [QUALITY](../QUALITY.md), сравнение с аналитиком из [eval/vs-analyst](../eval/vs-analyst.md).

Скриншоты интерфейса сняты 15 октября 2026 года: слайды берут их из [docs/screenshots](../screenshots), а в `img/` лежат вырезанные из них кадры. У ключей MCP на кадре `img/mcp-keys.png` начало ключа размыто. Пост в канале показан окном мока Bot API (`telegram-mock.png`).

[scrapgrep.pptx](scrapgrep.pptx) - та же презентация для правки в PowerPoint: текст в редактируемых полях (заголовки Georgia, остальное Segoe UI), таблицы нативные, а графики, схемы, скриншоты в рамках и подложки карточек лежат отдельными картинками PNG в двойном разрешении, их можно двигать и менять размер. Из-за других шрифтов строки переносятся чуть иначе, чем в PDF.

## Сборка

Скрипты лежат в [tools/](tools). Нужны Node с пакетом `playwright-core` (путь к пакету можно задать переменной `PLAYWRIGHT_CORE`), установленный Edge или Chrome и `uv`.

PDF печатает Chromium с размером страницы из CSS (`preferCSSPageSize`, `printBackground`). Скрипт заодно сохраняет PNG каждого слайда и предупреждает, если что-то вышло за нижний край слайда:

```bash
node docs/presentation/tools/deck_pdf.cjs docs/presentation/slides.html docs/presentation/scrapgrep.pdf tmp/deck
```

PPTX собирается в два шага. `extract.cjs` открывает страницу со шрифтами Georgia и Segoe UI, записывает положение каждого текста и таблицы в `deck.json` и вырезает картинки в двойном разрешении. `build_pptx.py` (python-pptx 1.0.2) раскладывает это по слайдам:

```bash
node docs/presentation/tools/extract.cjs docs/presentation/slides.html tmp/pptx
uv run --no-project --with python-pptx --with pillow python docs/presentation/tools/build_pptx.py tmp/pptx docs/presentation/scrapgrep.pptx
```

Вручную PDF получается так: открыть `slides.html` в Chrome или Edge, «Печать» → «Сохранить как PDF», поля «Нет», «Фон» включён.
