# Презентация

[scrapgrep.pdf](scrapgrep.pdf) - 23 слайда 1920×1080 для жюри и для слушателей без подготовки в ИБ. Порядок: что даёт ассистент в минутах и рублях, как он работает, два выпуска, проверка фактов, пространство компании с командами, ролями и приглашениями, лента и резюме, доставка и медиа, выбор моделей, варианты установки, тесты, экономика и пилот.

Слайды свёрстаны как полосы печатного выпуска: поля ультрамарина, чёрного и жёлтого, заголовки гротеском Golos Text, текст антиквой Source Serif 4 (оба шрифта OFL, лежат в `fonts/`). Слова стоят слева от одной оси на 42% ширины, справа идут экраны продукта встык, без рамок браузера. Направление выбрано по taste-skill («The printed annual»): Libre Franklin из него заменён на Golos Text, потому что у Libre Franklin нет кириллицы.

Каждая цифра взята из документов репозитория, источник подписан на слайде: сравнение с аналитиком из [eval/vs-analyst](../eval/vs-analyst.md), экономика из [BUSINESS](../BUSINESS.md), модели из [INSTALL](../INSTALL.md#модели-яндекса) и [examples/models](../../examples/models/README.md), тесты и CI из [CI](../CI.md). Экраны взяты из [docs/screenshots](../screenshots), кадры раздела «Компания» сняты 16 октября 2026 года на стенде с моделями Yandex AI Studio.

[scrapgrep.pptx](scrapgrep.pptx) - та же презентация для правки в PowerPoint: текст в редактируемых полях (заголовки Segoe UI, текст Georgia), таблица моделей нативная, у каждого слайда свой цвет фона, экраны и плашки лежат картинками PNG в двойном разрешении. Из-за других шрифтов строки переносятся чуть иначе, чем в PDF.

## Сборка

Скрипты лежат в [tools/](tools). Нужны Node с пакетом `playwright-core` (путь к пакету можно задать переменной `PLAYWRIGHT_CORE`), установленный Edge или Chrome и `uv`.

PDF печатает Chromium с размером страницы из CSS (`preferCSSPageSize`, `printBackground`). Скрипт заодно сохраняет PNG каждого слайда и предупреждает, если что-то вышло за нижний край слайда:

```bash
node docs/presentation/tools/deck_pdf.cjs docs/presentation/slides.html docs/presentation/scrapgrep.pdf tmp/deck
```

PPTX собирается в два шага. `extract.cjs` открывает страницу со шрифтами Georgia и Segoe UI, записывает положение каждого текста и таблицы и цвет фона слайда в `deck.json` и вырезает картинки в двойном разрешении. `build_pptx.py` (python-pptx 1.0.2) раскладывает это по слайдам:

```bash
node docs/presentation/tools/extract.cjs docs/presentation/slides.html tmp/pptx
uv run --no-project --with python-pptx --with pillow python docs/presentation/tools/build_pptx.py tmp/pptx docs/presentation/scrapgrep.pptx
```

Вручную PDF получается так: открыть `slides.html` в Chrome или Edge, «Печать» → «Сохранить как PDF», поля «Нет», «Фон» включён.
