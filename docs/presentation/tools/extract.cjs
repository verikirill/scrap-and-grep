// Reads docs/presentation/slides.html and writes, per slide, what the PPTX builder needs:
// text blocks with runs and boxes, tables cell by cell, and a transparent PNG for every
// picture-like element (charts, schemes, browser and phone frames, card backgrounds).
// Writes <outDir>/deck.json, <outDir>/img/*.png at 2x and <outDir>/ref/slide-NN.png for comparison.
//   node extract.cjs <slides.html> <outDir>
// playwright-core and the browser are found as in deck_pdf.cjs.
const { chromium } = require(process.env.PLAYWRIGHT_CORE || 'playwright-core')
const fs = require('fs')
const path = require('path')
const { pathToFileURL } = require('url')

const [HTML, OUT] = process.argv.slice(2)

// The PPTX uses Georgia and Segoe UI, so the layout is measured with them too.
const CSS = `
:root { --serif: Georgia, serif; --sans: 'Segoe UI', sans-serif; --mono: Consolas, monospace; }
html, body { background: transparent !important; }
section.slide { margin: 0 !important; }
section.slide.pp-hide { display: none !important; }
section.slide.pp-iso { background: transparent !important; }
.pp-iso, .pp-iso * { visibility: hidden !important; }
.pp-iso .pp-target, .pp-iso .pp-target * { visibility: visible !important; }
.pp-iso .pp-notext, .pp-iso .pp-notext * { color: transparent !important; }
/* The stack slide runs ~35px taller in Segoe UI than in Roboto Flex: tighter spacing keeps
   its source line clear of the footer. */
section.slide:has(.arch .lane) .arch { margin-top: 24px; }
section.slide:has(.arch .lane) .lane { padding: 14px 16px; }
section.slide:has(.arch .lane) > p.muted { margin-top: 20px !important; }
section.slide:has(.arch .lane) .flow .box { padding: 18px 18px; }
`

// Elements that go into the PPTX as pictures. Card-like boxes are pictures without their text.
// The stack scheme (.arch with lanes) is a picture; standalone .node boxes are text on a background.
const PICTURES = '.chart, .browser, .phone, .stair, .arch:has(.lane), .flow, .step, .card, .note, .cmd, .node'
const NO_TEXT = ['step', 'card', 'note', 'cmd', 'node']
const SHADOW_MARGIN = 44

function collect() {
  const EXCL = '.chart, .browser, .phone, .stair, .arch:has(.lane), .flow, svg, table'
  const slide = document.querySelector('section.slide:not(.pp-hide)')
  const base = slide.getBoundingClientRect()
  const rel = (r) => ({ x: r.left - base.left, y: r.top - base.top, w: r.width, h: r.height })
  const st = (e) => {
    const cs = getComputedStyle(e)
    return {
      color: cs.color, weight: cs.fontWeight, italic: cs.fontStyle === 'italic', size: parseFloat(cs.fontSize),
      family: cs.fontFamily, transform: cs.textTransform, ls: cs.letterSpacing, bg: cs.backgroundColor,
      ws: cs.whiteSpace, code: e.tagName === 'CODE',
    }
  }
  const isInline = (e) => getComputedStyle(e).display === 'inline'
  const runs = (node, out = []) => {
    for (const c of node.childNodes) {
      if (c.nodeType === 3) out.push({ text: c.data, style: st(c.parentElement) })
      else if (c.nodeType === 1 && c.tagName === 'BR') out.push({ br: true })
      else if (c.nodeType === 1 && isInline(c)) runs(c, out)
    }
    return out
  }
  const ownInline = (e) => [...e.childNodes].some((c) =>
    (c.nodeType === 3 && c.data.replace(/[ \t\n\r\f]/g, '') !== '') ||
    (c.nodeType === 1 && isInline(c) && c.textContent.trim() !== ''))
  // A block that also holds block children (.node title + span) gets the box of its own text only.
  const ownRect = (e, cs) => {
    const own = [...e.childNodes].filter((c) => c.nodeType === 3 || (c.nodeType === 1 && isInline(c)))
    const mixed = [...e.children].some((c) => !isInline(c))
    if (!mixed || !own.length) return null
    const r = document.createRange()
    r.setStartBefore(own[0])
    r.setEndAfter(own[own.length - 1])
    const t = r.getBoundingClientRect()
    const b = e.getBoundingClientRect()
    const pl = parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth)
    const pr = parseFloat(cs.paddingRight) + parseFloat(cs.borderRightWidth)
    return { x: b.left + pl - base.left, y: t.top - base.top, w: b.width - pl - pr, h: t.height }
  }
  const box = (e) => {
    const cs = getComputedStyle(e)
    const lh = cs.lineHeight === 'normal' ? parseFloat(cs.fontSize) * 1.33 : parseFloat(cs.lineHeight)
    const own = ownRect(e, cs)
    return {
      rect: own || rel(e.getBoundingClientRect()),
      pad: own ? [0, 0, 0, 0] : [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(parseFloat),
      align: cs.textAlign, valign: cs.verticalAlign, lineHeight: lh, style: st(e),
    }
  }
  const lineTexts = (e) => {
    const walker = document.createTreeWalker(e, NodeFilter.SHOW_TEXT)
    const lines = []
    let cur = ''
    let top = null
    let n
    while ((n = walker.nextNode())) {
      for (let k = 0; k < n.data.length; k++) {
        const ch = n.data[k]
        const r = document.createRange()
        r.setStart(n, k)
        r.setEnd(n, k + 1)
        const rects = r.getClientRects()
        if (/[ \t\n\r\f]/.test(ch) || !rects.length) { cur += ch; continue }
        const t = rects[0].top
        if (top !== null && t > top + 5) { lines.push(cur); cur = '' }
        if (top === null || t > top + 5) top = t
        cur += ch
      }
    }
    lines.push(cur)
    return lines
  }

  const texts = []
  for (const e of slide.querySelectorAll('*')) {
    if (e.closest(EXCL)) continue
    const d = getComputedStyle(e).display
    if (d === 'inline' || d === 'none' || !ownInline(e)) continue
    const foot = e.parentElement.classList.contains('foot')
    texts.push({
      ...box(e), tag: e.tagName.toLowerCase(), cls: e.className || '', runs: runs(e),
      lines: /^H[12]$/.test(e.tagName) ? lineTexts(e) : null,
      slideNumber: foot && e === e.parentElement.lastElementChild,
    })
  }

  const tables = [...slide.querySelectorAll('table')].map((t) => ({
    rect: rel(t.getBoundingClientRect()),
    rows: [...t.rows].map((tr) => ({
      rect: rel(tr.getBoundingClientRect()),
      cells: [...tr.cells].map((c) => {
        const cs = getComputedStyle(c)
        return {
          ...box(c), tag: c.tagName.toLowerCase(), colspan: c.colSpan, runs: runs(c),
          borderBottom: { w: parseFloat(cs.borderBottomWidth), color: cs.borderBottomColor, style: cs.borderBottomStyle },
        }
      }),
    })),
  }))

  const pictures = []
  for (const e of slide.querySelectorAll('${PICTURES}')) {
    if (e.parentElement.closest('${PICTURES}')) continue
    const target = e.classList.contains('chart') && e.querySelector('svg') ? e.querySelector('svg') : e
    const kind = ['chart', 'browser', 'phone', 'stair', 'arch', 'flow', 'step', 'card', 'note', 'cmd', 'node'].find((k) => e.classList.contains(k))
    const img = e.querySelector('img')
    const bar = e.querySelector('.bar span')
    pictures.push({
      kind, id: e.id || '', rect: rel(target.getBoundingClientRect()),
      shadow: getComputedStyle(e).boxShadow !== 'none',
      alt: img ? img.alt : (e.id || kind), label: bar ? bar.textContent : '', src: img ? img.getAttribute('src') : '',
    })
  }
  // Each slide is one field of colour: ultramarine, black or yellow.
  const bg = getComputedStyle(slide).backgroundColor
  return { texts, tables, pictures, bg }
}

async function main() {
  fs.mkdirSync(path.join(OUT, 'img'), { recursive: true })
  fs.mkdirSync(path.join(OUT, 'ref'), { recursive: true })
  const browser = await chromium.launch({ channel: 'msedge', headless: true }).catch(() => chromium.launch({ channel: 'chrome', headless: true }))
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 })
  await page.goto(pathToFileURL(path.resolve(HTML)).href, { waitUntil: 'load' })
  await page.addStyleTag({ content: CSS })
  await page.evaluate(() => document.fonts.ready)
  const count = await page.locator('section.slide').count()
  const deck = []
  const collectSrc = `(${collect.toString().replaceAll('${PICTURES}', PICTURES)})()`
  for (let i = 0; i < count; i++) {
    await page.evaluate((i) => document.querySelectorAll('section.slide').forEach((s, j) => s.classList.toggle('pp-hide', j !== i)), i)
    await page.evaluate(() => window.scrollTo(0, 0))
    const num = String(i + 1).padStart(2, '0')
    await page.screenshot({ path: path.join(OUT, 'ref', `slide-${num}.png`), clip: { x: 0, y: 0, width: 1920, height: 1080 }, scale: 'css' })
    const data = await page.evaluate(collectSrc)
    const overflow = await page.evaluate(() => {
      const s = document.querySelector('section.slide:not(.pp-hide)')
      const b = s.getBoundingClientRect().bottom
      return [...s.querySelectorAll('*')].filter((c) => c.getBoundingClientRect().bottom > b + 1).map((c) => c.tagName + '.' + c.className)
    })
    if (overflow.length) console.log(`slide ${i + 1}: below the slide: ${overflow.join(', ')}`)
    for (const [k, p] of data.pictures.entries()) {
      const m = p.shadow ? SHADOW_MARGIN : 0
      const x0 = Math.max(0, Math.floor(p.rect.x - m)), y0 = Math.max(0, Math.floor(p.rect.y - m))
      const x1 = Math.min(1920, Math.ceil(p.rect.x + p.rect.w + m)), y1 = Math.min(1080, Math.ceil(p.rect.y + p.rect.h + m))
      p.clip = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
      // Nothing of it is on the slide: no picture to cut.
      if (p.clip.w < 1 || p.clip.h < 1) { console.log(`slide ${i + 1}: ${p.kind} ${p.alt} is off the slide`); p.skip = true; continue }
      p.file = `img/s${num}-${String(k + 1).padStart(2, '0')}-${p.kind}.png`
      await page.evaluate(({ k, notext, selector }) => {
        const s = document.querySelector('section.slide:not(.pp-hide)')
        const els = [...s.querySelectorAll(selector)].filter((e) => !e.parentElement.closest(selector))
        s.classList.add('pp-iso')
        els[k].classList.add('pp-target')
        if (notext) els[k].classList.add('pp-notext')
      }, { k, notext: NO_TEXT.includes(p.kind), selector: PICTURES })
      await page.screenshot({ path: path.join(OUT, p.file), clip: { x: x0, y: y0, width: x1 - x0, height: y1 - y0 }, omitBackground: true })
      await page.evaluate(() => {
        document.querySelectorAll('.pp-iso, .pp-target, .pp-notext').forEach((e) => e.classList.remove('pp-iso', 'pp-target', 'pp-notext'))
      })
    }
    data.pictures = data.pictures.filter((p) => !p.skip)
    deck.push(data)
  }
  fs.writeFileSync(path.join(OUT, 'deck.json'), JSON.stringify(deck, null, 1))
  console.log(`${count} slides`)
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
