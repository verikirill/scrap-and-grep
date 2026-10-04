# Презентация

[scrapgrep.pdf](scrapgrep.pdf) - 12 слайдов 1920×1080: проблема, гипотеза жюри и ответ на неё, две аудитории, как устроена сборка, сбор с защищённых сайтов и по любому адресу, отбор и приоритет, модели, закрытый контур, экономика, пилот.

Исходник - [slides.html](slides.html): обычная страница, шрифты Roboto Flex и Source Serif 4 (OFL) лежат в `fonts/`, скриншоты стенда в `img/`. Каждая цифра на слайдах взята из документов репозитория: экономика из [BUSINESS](../BUSINESS.md), сбор из [DECISIONS](../DECISIONS.md), модели из [examples/models](../../examples/models/README.md), железо и закрытый контур из README.

Скриншоты сняты 3 октября 2026 года с аккаунта показа после `scripts/demo_prep.py`, модель `gpt-oss:120b` в облаке Ollama.

PDF собирается печатью в Chromium с размером страницы из CSS. Из Playwright:

```js
await page.goto('file:///…/docs/presentation/slides.html')
await page.pdf({ path: 'scrapgrep.pdf', preferCSSPageSize: true, printBackground: true })
```

Вручную: открыть `slides.html` в Chrome или Edge, «Печать» → «Сохранить как PDF», поля «Нет», «Фон» включён.
