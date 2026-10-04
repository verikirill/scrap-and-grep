# Презентация

[scrapgrep.pdf](scrapgrep.pdf) - 14 слайдов 1920×1080, по критериям жюри: задача заказчика и ответ на неё; репрезентативность материалов (каталог источников, прогон по датасету организаторов); техническая реализация (лестница чтения защищённых сайтов, проверка записей, две аудитории, смена интересов, замена модели, закрытый контур); бизнес (экономика, модули сверх задания); пилот.

Исходник - [slides.html](slides.html): обычная страница, шрифты Roboto Flex и Source Serif 4 (OFL) лежат в `fonts/`, скриншоты стенда в `img/`. Графики рисует скрипт внизу страницы из чисел, записанных в нём же. Каждая цифра на слайдах взята из документов репозитория, источник подписан на слайде: экономика из [BUSINESS](../BUSINESS.md), сбор из [DECISIONS](../DECISIONS.md), модели из [examples/models](../../examples/models/README.md), прогон датасета из [examples/dataset](../../examples/dataset/README.md), железо и закрытый контур из README.

Скриншоты сняты 4 октября 2026 года со стенда на `gpt-oss:120b` в облаке Ollama.

PDF собирается печатью в Chromium с размером страницы из CSS. Из Playwright:

```js
await page.goto('file:///…/docs/presentation/slides.html')
await page.pdf({ path: 'scrapgrep.pdf', preferCSSPageSize: true, printBackground: true })
```

Вручную: открыть `slides.html` в Chrome или Edge, «Печать» → «Сохранить как PDF», поля «Нет», «Фон» включён.
