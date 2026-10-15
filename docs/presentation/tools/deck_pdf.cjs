// Prints docs/presentation/slides.html to PDF with Chromium and writes a PNG per slide for review.
// Warns about any element that ends below its slide.
//   node deck_pdf.cjs <slides.html> <out.pdf> [previewDir]
// playwright-core comes from PLAYWRIGHT_CORE (a path) or from node_modules; the browser is the
// installed Edge, or Chrome when Edge is missing.
const { chromium } = require(process.env.PLAYWRIGHT_CORE || 'playwright-core')
const fs = require('fs')
const path = require('path')
const { pathToFileURL } = require('url')

const [HTML, PDF, PREVIEW] = process.argv.slice(2)

async function launch() {
  try {
    return await chromium.launch({ channel: 'msedge', headless: true })
  } catch {
    return chromium.launch({ channel: 'chrome', headless: true })
  }
}

async function main() {
  const browser = await launch()
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
  await page.goto(pathToFileURL(path.resolve(HTML)).href, { waitUntil: 'load' })
  await page.evaluate(() => document.fonts.ready)
  if (PREVIEW) fs.mkdirSync(PREVIEW, { recursive: true })
  const slides = await page.locator('section.slide').all()
  for (const [i, slide] of slides.entries()) {
    const below = await slide.evaluate((el) => {
      const bottom = el.getBoundingClientRect().bottom
      return [...el.querySelectorAll('*')].filter((c) => c.getBoundingClientRect().bottom > bottom + 1).length
    })
    if (below) console.log(`slide ${i + 1}: ${below} element(s) below the slide`)
    if (PREVIEW) await slide.screenshot({ path: path.join(PREVIEW, `slide-${String(i + 1).padStart(2, '0')}.png`) })
  }
  await page.emulateMedia({ media: 'print' })
  await page.pdf({ path: PDF, preferCSSPageSize: true, printBackground: true })
  console.log(`${slides.length} slides`)
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
